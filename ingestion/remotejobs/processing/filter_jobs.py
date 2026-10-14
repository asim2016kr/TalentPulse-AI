import pandas as pd


INPUT_FILE = "ingestion/output/clean_jobs.csv"
OUTPUT_FILE = "ingestion/output/filtered_jobs.csv"


df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig"
)


TECH_KEYWORDS = [
    "software",
    "developer",
    "engineer",
    "data",
    "machine learning",
    "artificial intelligence",
    "ai",
    "analyst",
    "analytics",
    "cloud",
    "devops",
    "database",
    "sql",
    "python",
    "java",
    "frontend",
    "backend",
    "full stack",
    "fullstack",
    "web",
    "mobile",
    "cyber",
    "security",
    "network",
    "systems",
    "qa",
    "quality assurance",
    "devsecops",
    "site reliability",
    "sre",
    "product manager",
    "technical",
    "technology"
]


def is_tech_job(title):

    title = str(title).lower()

    return any(
        keyword in title
        for keyword in TECH_KEYWORDS
    )


df["is_tech_job"] = df["job_title"].apply(is_tech_job)


filtered_df = df[
    df["is_tech_job"] == True
].copy()


filtered_df.drop(
    columns=["is_tech_job"],
    inplace=True
)


filtered_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print("========== JOB FILTERING ==========")
print(f"Original Records : {len(df)}")
print(f"Tech Jobs        : {len(filtered_df)}")
print(f"Removed          : {len(df) - len(filtered_df)}")
print(f"Saved to         : {OUTPUT_FILE}")
print("===================================")