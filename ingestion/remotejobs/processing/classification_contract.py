"""Shared schema and CSV boundaries for classification, transformation and loading."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

ROOT = Path(__file__).resolve().parents[3]
VERSION = "talentpulse-classification-v1"
ROLE_CATEGORY = {
    "Data Engineer": "Data Engineering", "Analytics Engineer": "Data Engineering",
    "Data Scientist": "Data Science", "Data Analyst": "Data Analytics",
    "Machine Learning Engineer": "Artificial Intelligence", "AI Engineer": "Artificial Intelligence",
    "Software Engineer": "Software Engineering", "DevOps / Cloud Engineer": "Cloud & DevOps",
    "Database Engineer": "Database", "Cybersecurity": "Cybersecurity",
    "Product / Project Manager": "Product & Project Management",
    "QA / Test Engineer": "Software Engineering", "IT / Technical Support": "IT Operations",
    "UX / UI Designer": "Design", "Hardware / Embedded Engineer": "Hardware & Embedded",
    "Other": "Other",
}
SOURCE_FIELDS = ["job_id", "job_title", "company", "location", "salary_min", "salary_max", "date_posted", "tags", "url"]


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    is_tech_job: bool
    role: Literal["Data Engineer", "Analytics Engineer", "Data Scientist", "Data Analyst",
                  "Machine Learning Engineer", "AI Engineer", "Software Engineer",
                  "DevOps / Cloud Engineer", "Database Engineer", "Cybersecurity",
                  "Product / Project Manager", "QA / Test Engineer", "IT / Technical Support",
                  "UX / UI Designer", "Hardware / Embedded Engineer", "Other"]
    category: Literal["Data Engineering", "Data Science", "Data Analytics", "Artificial Intelligence",
                      "Software Engineering", "Cloud & DevOps", "Database", "Cybersecurity",
                      "Product & Project Management", "IT Operations", "Design", "Hardware & Embedded", "Other"]
    experience_level: Literal["Intern", "Junior", "Mid", "Senior", "Lead", "Principal", "Other"]
    ai_confidence: float
    reason: str

    @model_validator(mode="after")
    def consistent(self):
        if not math.isfinite(self.ai_confidence) or not 0 <= self.ai_confidence <= 1:
            raise ValueError("Confidence must be finite and between 0 and 1")
        if ROLE_CATEGORY[self.role] != self.category:
            raise ValueError("Role/category mismatch")
        if not self.is_tech_job and self.role != "Other":
            raise ValueError("Non-tech jobs must use Other role/category")
        if not self.reason.strip() or len(self.reason) > 1000:
            raise ValueError("A short evidence-based reason is required")
        return self


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if not fields or len(fields) != len(set(fields)):
            raise ValueError("Missing or duplicate CSV headers")
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("Malformed CSV row")
    return rows, fields


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_hash(row):
    return digest({field: row.get(field, "") for field in SOURCE_FIELDS})


def prepare_source(rows):
    seen = set()
    prepared = []
    for original in rows:
        row = dict(original)
        for field in SOURCE_FIELDS:
            row.setdefault(field, "")
        if any(not row[field].strip() for field in ["job_title", "company", "location"]):
            raise ValueError("Missing essential source values; run cleaning first")
        # Older handoff CSVs omitted the API ID. A URL hash is stable across reruns.
        if not row["job_id"].strip():
            if not row["url"].strip():
                raise ValueError("A source job_id or URL is required")
            row["job_id"] = "remoteok:url:" + digest(row["url"].strip())
        if row["job_id"] != row["job_id"].strip() or row["job_id"] in seen:
            raise ValueError("Duplicate or untrimmed source job_id: " + row["job_id"])
        seen.add(row["job_id"])
        prepared.append(row)
    return prepared


def parse_bool(value):
    if type(value) is bool:
        return value
    if value not in ("True", "False", "true", "false"):
        raise ValueError("Expected a literal true/false boolean")
    return value.lower() == "true"


def classification_from_row(row):
    data = {field: row[field] for field in Classification.model_fields}
    data["is_tech_job"] = parse_bool(data["is_tech_job"])
    data["ai_confidence"] = float(data["ai_confidence"])
    return Classification.model_validate(data)
