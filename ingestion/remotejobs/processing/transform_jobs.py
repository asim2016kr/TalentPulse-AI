"""Transform reviewed semantic labels into the existing warehouse input contract."""
import argparse
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    from .classification_contract import (ROOT, VERSION, classification_from_row, prepare_source,
                                         read_csv, source_hash, write_csv)
except ImportError:
    from classification_contract import (ROOT, VERSION, classification_from_row, prepare_source,
                                        read_csv, source_hash, write_csv)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def skills(value):
    return sorted({s.strip() for s in value.split(",") if s.strip()})


def salary(value):
    if not value.strip():
        return ""
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid salary") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Salary must be finite and nonnegative")
    return str(number)


def transform(reviewed, source):
    source = prepare_source(source)
    expected = {r["job_id"]: source_hash(r) for r in source}
    ids = [r.get("job_id") for r in reviewed]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError("Reviewed dataset must contain every source ID exactly once")
    output = []
    for original in reviewed:
        row = dict(original)
        if row.get("input_hash") != expected[row["job_id"]] or source_hash(row) != row["input_hash"]:
            raise ValueError("Source content changed since classification; rerun classifier")
        if row.get("classification_status") != "ok" or row.get("classifier_version") != VERSION:
            raise ValueError("Failed or incompatible classifications cannot be loaded")
        if not row.get("reviewer", "").strip():
            raise ValueError("Every classification, including exclusions, must be reviewed")
        if row.get("review_status") == "quarantined":
            if not row.get("review_note", "").strip():
                raise ValueError("Quarantined rows require an explicit evidence limitation")
            # Retain the prediction in the review ledger without treating uncertainty as non-tech.
            continue
        if row.get("review_status") != "approved":
            raise ValueError("Every classification, including exclusions, must be reviewed")
        prediction = classification_from_row(row)
        if not prediction.is_tech_job:
            continue
        row.update(prediction.model_dump())
        for field in ["company", "location"]:
            row[field] = row[field].strip()
        row["tags"] = ", ".join(skills(row["tags"]))
        date = row["date_posted"].strip()
        row["date_posted"] = datetime.fromisoformat(date.replace("Z", "+00:00")).date().isoformat() if date else ""
        row["salary_min"], row["salary_max"] = salary(row["salary_min"]), salary(row["salary_max"])
        if row["salary_min"] and row["salary_max"] and Decimal(row["salary_min"]) > Decimal(row["salary_max"]):
            raise ValueError("Salary minimum exceeds maximum")
        location, title = row["location"].lower(), row["job_title"].lower()
        row["work_mode"] = "Hybrid" if re.search(r"\bhybrid\b", location) else (
            "Remote" if re.search(r"\bremote\b|\bwork from home\b", location) else "Unknown")
        row["job_type"] = "Unknown"
        for pattern, value in [(r"\bintern(?:ship)?\b", "Internship"), (r"\bcontract(?:or)?\b", "Contract"),
                               (r"\bpart[- ]time\b", "Part-Time"), (r"\bfreelanc(?:e|er)\b", "Freelance"),
                               (r"\bfull[- ]time\b", "Full-Time")]:
            if re.search(pattern, title):
                row["job_type"] = value
                break
        output.append(row)
    return output


def expected_counts(rows):
    return {
        "DIM_COMPANY": len({r["company"] for r in rows}),
        "DIM_LOCATION": len({r["location"] for r in rows}),
        "DIM_ROLE": len({(r["role"], r["category"], r["experience_level"]) for r in rows}),
        "DIM_SKILL": len({s for r in rows for s in skills(r["tags"])}),
        "FACT_JOBS": len(rows),
        "FACT_JOB_SKILLS": sum(len(skills(r["tags"])) for r in rows),
    }


def build(input_path, source_path, output_path):
    if Path(input_path).resolve() == Path(output_path).resolve() or Path(source_path).resolve() == Path(output_path).resolve():
        raise ValueError("Output must not overwrite source or reviewed input")
    reviewed, fields = read_csv(input_path)
    source, _ = read_csv(source_path)
    if not source:
        raise ValueError("Source snapshot is empty")
    rows = transform(reviewed, source)
    fields = list(dict.fromkeys(fields + ["work_mode", "job_type"]))
    write_csv(output_path, rows, fields)
    manifest = {
        "version": VERSION, "source_path": str(Path(source_path).resolve()),
        "reviewed_path": str(Path(input_path).resolve()),
        "source_sha256": file_hash(source_path), "reviewed_sha256": file_hash(input_path),
        "output_sha256": file_hash(output_path), "source_rows": len(source),
        "reviewed_rows": len(reviewed), "excluded_rows": len(source) - len(rows),
        "quarantined_rows": sum(r.get("review_status") == "quarantined" for r in reviewed),
        "approved_nontech_rows": sum(r.get("review_status") == "approved" and
                                     not classification_from_row(r).is_tech_job for r in reviewed),
        "expected_counts": expected_counts(rows),
    }
    Path(str(output_path) + ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "ingestion/output/reviewed_jobs.csv")
    parser.add_argument("--source", type=Path, default=ROOT / "ingestion/output/clean_jobs.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "ingestion/output/transformed_jobs.csv")
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
