import json
import math
import os
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import requests


def configure_console_encoding():
    """Use UTF-8 where supported without failing in redirected environments."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass


configure_console_encoding()


class RemoteJobsIngestion:
    BASE_URL = "https://remoteok.com/api"

    TECH_TAGS = [
        "developer",
        "software",
        "engineer",
        "backend",
        "frontend",
        "data",
        "python",
        "javascript",
        "java",
        "react",
        "node",
        "devops",
        "cloud",
        "ai",
        "machine-learning",
        "cybersecurity",
    ]

    TECH_WORDS = [
        "developer",
        "software engineer",
        "data engineer",
        "data scientist",
        "machine learning",
        "ai engineer",
        "devops",
        "backend",
        "frontend",
        "full stack",
        "cloud engineer",
        "cybersecurity",
        "programmer",
    ]

    OUTPUT_COLUMNS = [
        "job_id",
        "job_title",
        "company",
        "location",
        "salary_min",
        "salary_max",
        "date_posted",
        "tags",
        "url",
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }

    @staticmethod
    def _clean_text(value):
        """Return normalized, single-line Unicode text for CSV fields."""
        if value is None:
            return ""

        if isinstance(value, (dict, list, tuple, set)):
            return ""

        text = unicodedata.normalize("NFC", str(value))
        text = text.replace("\x00", "")
        return " ".join(text.split())

    @staticmethod
    def _match_text(value):
        """Normalize text for case-insensitive technology matching."""
        if value is None:
            return ""
        return unicodedata.normalize("NFKC", str(value)).casefold().strip()

    @staticmethod
    def _clean_salary(value):
        """Keep finite, non-negative numeric salaries; otherwise mark missing."""
        if value is None or isinstance(value, bool):
            return pd.NA

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return pd.NA

        try:
            salary = float(value)
        except (TypeError, ValueError, OverflowError):
            return pd.NA

        if not math.isfinite(salary) or salary < 0:
            return pd.NA

        return int(salary) if salary.is_integer() else salary

    @classmethod
    def _clean_tags(cls, value):
        if not isinstance(value, list):
            return ""

        tags = []
        for tag in value:
            cleaned = cls._clean_text(tag)
            if cleaned:
                tags.append(cleaned)
        return ", ".join(tags)

    @classmethod
    def _clean_url(cls, value):
        url = cls._clean_text(value)
        if not url:
            return ""

        try:
            parsed = urlsplit(url)
        except ValueError:
            return ""

        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
            return ""
        return url

    def fetch_jobs(self):
        print("Fetching jobs from RemoteOK API...")

        try:
            response = requests.get(
                self.BASE_URL,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"RemoteOK API request failed: {exc}") from exc

        try:
            data = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("RemoteOK API returned invalid JSON.") from exc

        if not isinstance(data, list):
            raise RuntimeError("RemoteOK API returned an unexpected payload type.")

        if not data:
            raise RuntimeError("RemoteOK API returned an empty payload.")

        if not isinstance(data[0], dict):
            raise RuntimeError("RemoteOK API metadata record is malformed.")

        raw_jobs = data[1:]
        print(f"API response received: {len(raw_jobs)} jobs")

        jobs = [job for job in raw_jobs if isinstance(job, dict)]
        malformed_count = len(raw_jobs) - len(jobs)
        if malformed_count:
            print(f"Warning: skipped {malformed_count} malformed job record(s).")

        return jobs

    def filter_technology_jobs(self, jobs):
        tech_jobs = []
        tech_tags = {self._match_text(tag) for tag in self.TECH_TAGS}

        for job in jobs:
            if not isinstance(job, dict):
                continue

            tags = job.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            tags_lower = {
                self._match_text(tag)
                for tag in tags
                if self._match_text(tag)
            }
            position = self._match_text(job.get("position"))

            is_tech = any(tag in tags_lower for tag in tech_tags)

            if not is_tech:
                is_tech = any(word in position for word in self.TECH_WORDS)

            if is_tech:
                tech_jobs.append(job)

        return tech_jobs

    def transform_jobs(self, jobs):
        records = []

        for item in jobs:
            if not isinstance(item, dict):
                continue

            records.append(
                {
                    "job_id": self._clean_text(item.get("id")),
                    "job_title": self._clean_text(item.get("position")),
                    "company": self._clean_text(item.get("company")),
                    "location": self._clean_text(item.get("location")),
                    "salary_min": self._clean_salary(item.get("salary_min")),
                    "salary_max": self._clean_salary(item.get("salary_max")),
                    "date_posted": self._clean_text(item.get("date")),
                    "tags": self._clean_tags(item.get("tags")),
                    "url": self._clean_url(item.get("url")),
                }
            )

        return pd.DataFrame.from_records(records, columns=self.OUTPUT_COLUMNS)

    def save(self, df):
        output_path = Path("ingestion/remotejobs/output")
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / "jobs.csv"
        temporary_file = output_path / "jobs.csv.tmp"

        try:
            df.to_csv(
                temporary_file,
                index=False,
                encoding="utf-8-sig",
                lineterminator="\n",
            )
            os.replace(temporary_file, output_file)
        finally:
            temporary_file.unlink(missing_ok=True)

        print(f"Saved to: {output_file}")

    def run(self):
        print("=" * 45)
        print("TalentPulse AI - Job Ingestion")
        print("=" * 45)

        jobs = self.fetch_jobs()
        # Persist every posting; semantic filtering belongs after cleaning.
        df = self.transform_jobs(jobs)
        self.save(df)

        print("\nSample data:")
        print(
            df[["job_title", "company", "location"]]
            .head(10)
            .to_string(index=False)
        )

        print("\nIngestion completed successfully!")


if __name__ == "__main__":
    ingestion = RemoteJobsIngestion()
    ingestion.run()
