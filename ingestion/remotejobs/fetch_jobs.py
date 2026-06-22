import requests
import pandas as pd

url = "https://remoteok.com/api"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)

data = response.json()

jobs = []

for item in data[1:]:
    jobs.append({
        "job_title": item.get("position"),
        "company": item.get("company"),
        "location": item.get("location"),
        "salary_min": item.get("salary_min"),
        "salary_max": item.get("salary_max"),
        "date_posted": item.get("date"),
        "tags": ", ".join(item.get("tags", []))
    })

df = pd.DataFrame(jobs)

df.to_csv(
    "ingestion/remotejobs/output/jobs.csv",
    index=False
)

print(f"Collected {len(df)} jobs")

# """
# RemoteOK Job Scraper
# ---------------------
# Pulls live job listings from the RemoteOK public API and saves them
# to a clean, structured CSV for downstream analysis.

# Usage:
#     python scrape_remoteok.py
# """

# import logging
# import re
# import time
# from pathlib import Path

# import pandas as pd
# import requests

# API_URL = "https://remoteok.com/api"
# OUTPUT_PATH = Path("ingestion/remotejobs/output/jobs.csv")

# # A single "User-Agent" header is often enough, but some endpoints behind
# # Cloudflare/anti-bot rules want a fuller, browser-like header set.
# HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
#         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
#     ),
#     "Accept": "application/json",
#     "Accept-Language": "en-US,en;q=0.9",
# }

# MAX_RETRIES = 3
# RETRY_DELAY_SECONDS = 5
# REQUEST_TIMEOUT_SECONDS = 15

# logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
# logger = logging.getLogger(__name__)


# def fetch_raw_jobs(url=API_URL, headers=HEADERS, max_retries=MAX_RETRIES):
#     """Fetch raw job listings from the RemoteOK API, retrying on transient failures."""
#     for attempt in range(1, max_retries + 1):
#         try:
#             response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
#             response.raise_for_status()
#             data = response.json()
#             if not isinstance(data, list) or len(data) < 2:
#                 logger.warning("Unexpected response shape — got %r", type(data))
#                 return []
#             # The first element is always a legal/metadata notice, not a job.
#             return data[1:]
#         except (requests.RequestException, ValueError) as exc:
#             logger.warning("Attempt %d/%d failed: %s", attempt, max_retries, exc)
#             if attempt < max_retries:
#                 time.sleep(RETRY_DELAY_SECONDS * attempt)
#     logger.error("All retry attempts failed — returning no data.")
#     return []


# def _clean_text(value):
#     """Trim whitespace and strip trailing/leading commas left over from RemoteOK's
#     'City, ' style location strings. Returns None for empty results."""
#     if value is None:
#         return None
#     text = str(value).strip().strip(",").strip()
#     return text or None


# def normalize_job(item):
#     """Convert a single raw API record into a clean, flat dict."""
#     tags = item.get("tags") or []
#     if not isinstance(tags, list):
#         tags = [str(tags)]

#     salary_min = pd.to_numeric(item.get("salary_min"), errors="coerce")
#     salary_max = pd.to_numeric(item.get("salary_max"), errors="coerce")
#     # RemoteOK uses 0/0 as a "not disclosed" sentinel, not a literal $0 salary.
#     if salary_min == 0 and salary_max == 0:
#         salary_min, salary_max = pd.NA, pd.NA

#     return {
#         "job_id": item.get("id"),
#         "job_title": _clean_text(item.get("position")),
#         "company": _clean_text(item.get("company")),
#         "location": _clean_text(item.get("location")) or "Remote",
#         "salary_min": salary_min,
#         "salary_max": salary_max,
#         "date_posted": item.get("date"),
#         "tags": ", ".join(t.strip() for t in tags if str(t).strip()),
#         "url": item.get("url") or item.get("apply_url"),
#     }


# def build_dataframe(raw_jobs):
#     jobs = [normalize_job(item) for item in raw_jobs]
#     df = pd.DataFrame(jobs)

#     if df.empty:
#         return df

#     # A record with no title or no company isn't a usable job row.
#     df = df[df["job_title"].notna() & df["company"].notna()]

#     # Parse dates up front so downstream analysis never has to guess the format.
#     df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce", utc=True)

#     # The API can return repeats across calls/pagination — dedupe on job_id.
#     if "job_id" in df.columns and df["job_id"].notna().any():
#         df = df.drop_duplicates(subset="job_id")
#     else:
#         df = df.drop_duplicates()

#     return df.sort_values("date_posted", ascending=False).reset_index(drop=True)


# def save_jobs(df, path=OUTPUT_PATH):
#     path.parent.mkdir(parents=True, exist_ok=True)
#     df.to_csv(path, index=False)
#     logger.info("Saved %d jobs to %s", len(df), path)


# def main():
#     logger.info("Fetching jobs from RemoteOK...")
#     raw_jobs = fetch_raw_jobs()

#     if not raw_jobs:
#         logger.warning("No jobs retrieved — exiting without writing a CSV.")
#         return

#     df = build_dataframe(raw_jobs)
#     save_jobs(df)
#     print(f"Collected {len(df)} jobs")


# if __name__ == "__main__":
#     main()