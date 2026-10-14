"""Validate a reviewed full snapshot and replace six existing tables atomically.

No DDL or TRUNCATE is executed inside the transaction. Default CLI behavior is
an offline plan. --rehearse rolls back; --apply commits only after reconciliation.
"""
import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ingestion.remotejobs.processing.classification_contract import VERSION, read_csv
from ingestion.remotejobs.processing.transform_jobs import expected_counts, file_hash, skills, transform

TABLES = ["DIM_COMPANY", "DIM_LOCATION", "DIM_ROLE", "DIM_SKILL", "FACT_JOBS", "FACT_JOB_SKILLS"]


def preflight(path):
    path = Path(path)
    manifest = json.loads(Path(str(path) + ".manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != VERSION or manifest.get("output_sha256") != file_hash(path):
        raise ValueError("Missing/stale transformation manifest; rerun transformation")
    for kind in ["source", "reviewed"]:
        if file_hash(manifest[kind + "_path"]) != manifest[kind + "_sha256"]:
            raise ValueError("Source/review changed after transformation")
    source, _ = read_csv(manifest["source_path"])
    reviewed, _ = read_csv(manifest["reviewed_path"])
    expected = transform(reviewed, source)
    actual, _ = read_csv(path)
    # Recompute, so even a hand-edited manifest cannot bypass the review gate.
    serialized = [{k: str(v) for k, v in row.items()} for row in expected]
    if actual != serialized:
        raise ValueError("Transformed CSV does not match reviewed source")
    if not actual:
        raise ValueError("Refusing an empty replacement snapshot; investigate source/classifications")
    counts = expected_counts(actual)
    if counts != manifest["expected_counts"]:
        raise ValueError("Manifest row counts do not match dataset")
    return actual, manifest


def canonical(value):
    if value is None or value == "":
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def expected_facts(rows):
    result = []
    for row in rows:
        values = [row[k] for k in ["job_id", "company", "location", "role", "category", "experience_level",
                                  "job_title", "job_type", "work_mode"]]
        values += [Decimal(row[k]) if row[k] else None for k in ["salary_min", "salary_max"]]
        values += [row["url"], row["date_posted"]]
        result.append(tuple(canonical(v) for v in values))
    return Counter(result)


def verify_snapshot(cursor, rows):
    counts = expected_counts(rows)
    for table, expected in counts.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        actual = cursor.fetchone()[0]
        if actual != expected:
            raise ValueError(f"{table} count mismatch: expected {expected}, got {actual}")
    cursor.execute("""
        SELECT f.SOURCE_JOB_ID, c.COMPANY_NAME, l.LOCATION_NAME, r.ROLE_NAME,
               r.CATEGORY, r.EXPERIENCE_LEVEL, f.JOB_TITLE, f.JOB_TYPE, f.WORK_MODE,
               f.SALARY_MIN, f.SALARY_MAX, f.JOB_URL, f.POSTED_DATE
        FROM FACT_JOBS f
        JOIN DIM_COMPANY c ON c.COMPANY_ID = f.COMPANY_ID
        JOIN DIM_LOCATION l ON l.LOCATION_ID = f.LOCATION_ID
        JOIN DIM_ROLE r ON r.ROLE_ID = f.ROLE_ID
    """)
    actual = Counter(tuple(canonical(v) for v in row) for row in cursor.fetchall())
    if actual != expected_facts(rows):
        raise ValueError("Fact values, source identities or dimension references do not match")
    cursor.execute("""
        SELECT f.SOURCE_JOB_ID, s.SKILL_NAME FROM FACT_JOB_SKILLS b
        JOIN FACT_JOBS f ON f.JOB_ID = b.JOB_ID
        JOIN DIM_SKILL s ON s.SKILL_ID = b.SKILL_ID
    """)
    expected = Counter((r["job_id"], s) for r in rows for s in skills(r["tags"]))
    if Counter(cursor.fetchall()) != expected:
        raise ValueError("Skill links missing, duplicated, stale or orphaned")
    # Snowflake standard table PK/FK constraints are not enforcement; explicitly check keys.
    for table, key in [("DIM_COMPANY", "COMPANY_ID"), ("DIM_LOCATION", "LOCATION_ID"),
                       ("DIM_ROLE", "ROLE_ID"), ("DIM_SKILL", "SKILL_ID"), ("FACT_JOBS", "JOB_ID")]:
        cursor.execute(f"SELECT COUNT(*), COUNT(DISTINCT {key}) FROM {table}")
        total, unique = cursor.fetchone()
        if total != unique:
            raise ValueError(f"Null/duplicate surrogate key in {table}")
    return counts


def replace_snapshot(connection, rows, loader, apply=False):
    import pandas as pd
    if not rows:
        raise ValueError("Refusing an empty replacement snapshot")
    # Decimal/None avoids NaN conversion and numeric/string coercion of source IDs.
    df = pd.DataFrame(rows, dtype=object)
    for name in ["salary_min", "salary_max"]:
        df[name] = df[name].map(lambda v: Decimal(v) if v else None)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()")
        if tuple(cursor.fetchone()) != ("TALENTPULSE", "JOB_ANALYTICS"):
            raise ValueError("Refusing reload outside TALENTPULSE.JOB_ANALYTICS")
        # Fail on missing tables or columns before deleting anything.
        for table in TABLES:
            cursor.execute(f"SELECT * FROM {table} LIMIT 0")
        cursor.execute("SELECT SOURCE_JOB_ID FROM FACT_JOBS LIMIT 0")
        cursor.execute("BEGIN TRANSACTION")
        for table in ["FACT_JOB_SKILLS", "FACT_JOBS", "DIM_SKILL", "DIM_ROLE", "DIM_LOCATION", "DIM_COMPANY"]:
            cursor.execute(f"DELETE FROM {table}")
        loader.load_companies(cursor, df)
        loader.load_locations(cursor, df)
        loader.load_roles(cursor, df)
        loader.load_skills(cursor, df)
        company, location, role, skill = loader.get_lookup_tables(cursor)
        loader.load_jobs(cursor, df, company, location, role)
        loader.load_job_skills(cursor, df, skill)
        counts = verify_snapshot(cursor, rows)
        if apply:
            connection.commit()
        else:
            connection.rollback()
        return counts
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main(loader):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "ingestion/output/transformed_jobs.csv")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--rehearse", action="store_true")
    modes.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "ingestion/output/warehouse_reload_report.json")
    args = parser.parse_args()
    rows, manifest = preflight(args.input)
    print(json.dumps({"target": "TALENTPULSE.JOB_ANALYTICS", "strategy": "full snapshot replacement",
                      "sha256": manifest["output_sha256"], "expected_counts": expected_counts(rows)}, indent=2))
    if not (args.rehearse or args.apply):
        print("Offline plan only. --rehearse validates then rolls back; --apply validates then commits.")
        return
    connection = loader.create_connection()
    try:
        counts = replace_snapshot(connection, rows, loader, apply=args.apply)
    finally:
        connection.close()
    report = {"completed_at": datetime.now(timezone.utc).isoformat(), "committed": args.apply,
              "input_sha256": manifest["output_sha256"], "counts": counts,
              "validation": "exact fact reconciliation, skill links and surrogate keys passed"}
    # Print committed status before report I/O so a disk error cannot hide the commit outcome.
    print(json.dumps(report, indent=2))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
