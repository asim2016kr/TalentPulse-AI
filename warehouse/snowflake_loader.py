"""
TalentPulse AI
Snowflake Data Loader

Loads transformed job data into the TalentPulse Snowflake warehouse.

Warehouse:
    TALENTPULSE.JOB_ANALYTICS

Tables:
    DIM_COMPANY
    DIM_LOCATION
    DIM_ROLE
    DIM_SKILL
    FACT_JOBS
    FACT_JOB_SKILLS
"""

import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "ingestion" / "output" / "transformed_jobs.csv"

load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------
# Snowflake Connection
# ---------------------------------------------------------

def create_connection():

    required_variables = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
        "SNOWFLAKE_ROLE",
    ]

    missing = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing)}"
        )

    connection = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        login_timeout=30, network_timeout=180,
        session_parameters={"STATEMENT_TIMEOUT_IN_SECONDS": 300},
    )

    return connection


# ---------------------------------------------------------
# Load CSV
# ---------------------------------------------------------

def load_dataframe():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Transformed dataset not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    print(f"Loaded dataset: {INPUT_FILE}")
    print(f"Records found: {len(df)}")

    return df


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def clean_value(value):

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


# ---------------------------------------------------------
# DIM_COMPANY
# ---------------------------------------------------------

def load_companies(cursor, df):

    companies = (
        df["company"]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
    )

    for company in companies:

        cursor.execute(
            """
            MERGE INTO DIM_COMPANY target
            USING (
                SELECT %s AS COMPANY_NAME
            ) source
            ON target.COMPANY_NAME = source.COMPANY_NAME

            WHEN NOT MATCHED THEN
                INSERT (COMPANY_NAME)
                VALUES (source.COMPANY_NAME)
            """,
            (company,)
        )

    print(f"DIM_COMPANY processed: {len(companies)}")


# ---------------------------------------------------------
# DIM_LOCATION
# ---------------------------------------------------------

def load_locations(cursor, df):

    locations = (
        df["location"]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
    )

    for location in locations:

        cursor.execute(
            """
            MERGE INTO DIM_LOCATION target
            USING (
                SELECT %s AS LOCATION_NAME
            ) source
            ON target.LOCATION_NAME = source.LOCATION_NAME

            WHEN NOT MATCHED THEN
                INSERT (LOCATION_NAME)
                VALUES (source.LOCATION_NAME)
            """,
            (location,)
        )

    print(f"DIM_LOCATION processed: {len(locations)}")


# ---------------------------------------------------------
# DIM_ROLE
# ---------------------------------------------------------

def load_roles(cursor, df):

    role_columns = [
        "role",
        "category",
        "experience_level"
    ]

    roles = (
        df[role_columns]
        .drop_duplicates()
    )

    for _, row in roles.iterrows():

        cursor.execute(
            """
            MERGE INTO DIM_ROLE target
            USING (
                SELECT
                    %s AS ROLE_NAME,
                    %s AS CATEGORY,
                    %s AS EXPERIENCE_LEVEL
            ) source

            ON target.ROLE_NAME = source.ROLE_NAME
               AND COALESCE(target.CATEGORY, '') =
                   COALESCE(source.CATEGORY, '')
               AND COALESCE(target.EXPERIENCE_LEVEL, '') =
                   COALESCE(source.EXPERIENCE_LEVEL, '')

            WHEN NOT MATCHED THEN
                INSERT (
                    ROLE_NAME,
                    CATEGORY,
                    EXPERIENCE_LEVEL
                )
                VALUES (
                    source.ROLE_NAME,
                    source.CATEGORY,
                    source.EXPERIENCE_LEVEL
                )
            """,
            (
                clean_value(row["role"]),
                clean_value(row["category"]),
                clean_value(row["experience_level"])
            )
        )

    print(f"DIM_ROLE processed: {len(roles)}")


# ---------------------------------------------------------
# DIM_SKILL
# ---------------------------------------------------------

def load_skills(cursor, df):

    skills = set()

    for tags in df["tags"].dropna():

        tag_list = str(tags).split(",")

        for skill in tag_list:

            skill = skill.strip()

            if skill:
                skills.add(skill)

    for skill in sorted(skills):

        cursor.execute(
            """
            MERGE INTO DIM_SKILL target
            USING (
                SELECT %s AS SKILL_NAME
            ) source

            ON target.SKILL_NAME = source.SKILL_NAME

            WHEN NOT MATCHED THEN
                INSERT (SKILL_NAME)
                VALUES (source.SKILL_NAME)
            """,
            (skill,)
        )

    print(f"DIM_SKILL processed: {len(skills)}")


# ---------------------------------------------------------
# Create Lookup Dictionaries
# ---------------------------------------------------------

def get_lookup_tables(cursor):

    cursor.execute(
        """
        SELECT COMPANY_ID, COMPANY_NAME
        FROM DIM_COMPANY
        """
    )

    company_lookup = {
        name: company_id
        for company_id, name in cursor.fetchall()
    }

    cursor.execute(
        """
        SELECT LOCATION_ID, LOCATION_NAME
        FROM DIM_LOCATION
        """
    )

    location_lookup = {
        name: location_id
        for location_id, name in cursor.fetchall()
    }

    cursor.execute(
        """
        SELECT
            ROLE_ID,
            ROLE_NAME,
            CATEGORY,
            EXPERIENCE_LEVEL
        FROM DIM_ROLE
        """
    )

    role_lookup = {}

    for role_id, role, category, experience in cursor.fetchall():

        key = (
            role,
            category,
            experience
        )

        role_lookup[key] = role_id

    cursor.execute(
        """
        SELECT SKILL_ID, SKILL_NAME
        FROM DIM_SKILL
        """
    )

    skill_lookup = {
        name: skill_id
        for skill_id, name in cursor.fetchall()
    }

    return (
        company_lookup,
        location_lookup,
        role_lookup,
        skill_lookup
    )


# ---------------------------------------------------------
# FACT_JOBS
# ---------------------------------------------------------

def load_jobs(
    cursor,
    df,
    company_lookup,
    location_lookup,
    role_lookup
):

    for _, row in df.iterrows():

        source_job_id = clean_value(row["job_id"])

        company = clean_value(row["company"])
        location = clean_value(row["location"])

        role = clean_value(row["role"])
        category = clean_value(row["category"])
        experience = clean_value(row["experience_level"])

        company_id = company_lookup.get(company)

        location_id = location_lookup.get(location)

        role_id = role_lookup.get(
            (
                role,
                category,
                experience
            )
        )

        if company_id is None:
            print(
                f"Skipping job {source_job_id}: "
                f"company not found."
            )
            continue

        if location_id is None:
            print(
                f"Skipping job {source_job_id}: "
                f"location not found."
            )
            continue

        if role_id is None:
            print(
                f"Skipping job {source_job_id}: "
                f"role not found."
            )
            continue

        cursor.execute(
            """
            MERGE INTO FACT_JOBS target

            USING (
                SELECT
                    %s AS SOURCE_JOB_ID,
                    %s AS COMPANY_ID,
                    %s AS LOCATION_ID,
                    %s AS ROLE_ID,
                    %s AS JOB_TITLE,
                    %s AS JOB_TYPE,
                    %s AS WORK_MODE,
                    %s AS SALARY_MIN,
                    %s AS SALARY_MAX,
                    %s AS JOB_URL,
                    %s AS POSTED_DATE
            ) source

            ON target.SOURCE_JOB_ID = source.SOURCE_JOB_ID
            WHEN MATCHED THEN UPDATE SET
                COMPANY_ID = source.COMPANY_ID, LOCATION_ID = source.LOCATION_ID,
                ROLE_ID = source.ROLE_ID, JOB_TITLE = source.JOB_TITLE,
                JOB_TYPE = source.JOB_TYPE, WORK_MODE = source.WORK_MODE,
                SALARY_MIN = source.SALARY_MIN, SALARY_MAX = source.SALARY_MAX,
                JOB_URL = source.JOB_URL, POSTED_DATE = source.POSTED_DATE


            WHEN NOT MATCHED THEN

                INSERT (
                    SOURCE_JOB_ID,
                    COMPANY_ID,
                    LOCATION_ID,
                    ROLE_ID,
                    JOB_TITLE,
                    JOB_TYPE,
                    WORK_MODE,
                    SALARY_MIN,
                    SALARY_MAX,
                    JOB_URL,
                    POSTED_DATE
                )

                VALUES (
                    source.SOURCE_JOB_ID,
                    source.COMPANY_ID,
                    source.LOCATION_ID,
                    source.ROLE_ID,
                    source.JOB_TITLE,
                    source.JOB_TYPE,
                    source.WORK_MODE,
                    source.SALARY_MIN,
                    source.SALARY_MAX,
                    source.JOB_URL,
                    source.POSTED_DATE
                )
            """,
            (
                source_job_id,
                company_id,
                location_id,
                role_id,
                clean_value(row["job_title"]),
                clean_value(row["job_type"]),
                clean_value(row["work_mode"]),
                row["salary_min"]
                if pd.notna(row["salary_min"])
                else None,
                row["salary_max"]
                if pd.notna(row["salary_max"])
                else None,
                clean_value(row["url"]),
                clean_value(row["date_posted"])
            )
        )

    print(f"FACT_JOBS processed: {len(df)}")


# ---------------------------------------------------------
# FACT_JOB_SKILLS
# ---------------------------------------------------------

def load_job_skills(cursor, df, skill_lookup):

    cursor.execute(
        """
        SELECT SOURCE_JOB_ID, JOB_ID
        FROM FACT_JOBS
        """
    )

    job_lookup = {
        source_job_id: job_id
        for source_job_id, job_id in cursor.fetchall()
    }

    relationship_count = 0

    for _, row in df.iterrows():

        source_job_id = clean_value(row["job_id"])

        job_id = job_lookup.get(source_job_id)

        if job_id is None:
            continue

        tags = row["tags"]

        if pd.isna(tags):
            continue

        skills = str(tags).split(",")

        for skill in skills:

            skill = skill.strip()

            if not skill:
                continue

            skill_id = skill_lookup.get(skill)

            if skill_id is None:
                continue

            cursor.execute(
                """
                MERGE INTO FACT_JOB_SKILLS target

                USING (
                    SELECT
                        %s AS JOB_ID,
                        %s AS SKILL_ID
                ) source

                ON target.JOB_ID = source.JOB_ID
                   AND target.SKILL_ID = source.SKILL_ID

                WHEN NOT MATCHED THEN

                    INSERT (
                        JOB_ID,
                        SKILL_ID
                    )

                    VALUES (
                        source.JOB_ID,
                        source.SKILL_ID
                    )
                """,
                (
                    job_id,
                    skill_id
                )
            )

            relationship_count += 1

    print(
        f"FACT_JOB_SKILLS processed: "
        f"{relationship_count}"
    )


# ---------------------------------------------------------
# Verification
# ---------------------------------------------------------

def verify_tables(cursor):

    tables = [
        "DIM_COMPANY",
        "DIM_LOCATION",
        "DIM_ROLE",
        "DIM_SKILL",
        "FACT_JOBS",
        "FACT_JOB_SKILLS"
    ]

    print("\n========== WAREHOUSE SUMMARY ==========")

    for table in tables:

        cursor.execute(
            f"SELECT COUNT(*) FROM {table}"
        )

        count = cursor.fetchone()[0]

        print(
            f"{table:<20} : {count}"
        )

    print("========================================")


# ---------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------

def main():
    import sys
    try:
        from .reload_validation import main as reload_main
    except ImportError:
        from reload_validation import main as reload_main
    reload_main(sys.modules[__name__])


if __name__ == "__main__":
    main()
