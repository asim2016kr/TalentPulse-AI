"""
TalentPulse AI

Module:
Data Cleaning

Description:
Cleans and standardizes the raw job dataset after ingestion
and validation.
"""

import pandas as pd
import html
import re
from ftfy import fix_encoding
from pathlib import Path


class DataCleaner:
    """Cleans and standardizes raw job data."""

    def __init__(self, input_file: str):
        self.input_file = input_file
        self.df = pd.read_csv(
            input_file,
            encoding="utf-8-sig",
            dtype={"job_id": str},
        )

    # ----------------------------
    # Remove Duplicates
    # ----------------------------
    def remove_duplicates(self):
        """Remove completely duplicate rows."""

        before = len(self.df)

        self.df.drop_duplicates(
            inplace=True
        )

        after = len(self.df)

        print(
            f"Duplicates Removed : {before - after}"
        )

    # ----------------------------
    # Remove Missing Values
    # ----------------------------
    def remove_missing_values(self):
        """Remove rows missing essential job information."""

        before = len(self.df)

        self.df.dropna(
            subset=[
                "job_title",
                "company",
            ],
            inplace=True
        )

        after = len(self.df)

        print(
            f"Rows Removed (Missing Values): {before - after}"
        )

    # ----------------------------
    # Clean Text
    # ----------------------------
    def clean_text(self):
        """
        Clean text fields while preserving
        legitimate Unicode characters.
        """

        text_columns = [
            "job_title",
            "company",
            "location"
        ]

        for column in text_columns:

            self.df[column] = (
                self.df[column]
                .astype(str)

                # Decode HTML entities
                .apply(html.unescape)
                .apply(fix_encoding)

                # Convert literal escape sequences
                # such as \\n and \\r into spaces
                .str.replace(
                    r"\\n|\\r|\\t",
                    " ",
                    regex=True
                )

                # Remove actual line breaks/tabs
                .str.replace(
                    r"[\r\n\t]+",
                    " ",
                    regex=True
                )

                # Normalize repeated whitespace
                .str.replace(
                    r"\s+",
                    " ",
                    regex=True
                )

                # Remove leading/trailing whitespace
                .str.strip()
            )

    # ----------------------------
    # Clean Skills
    # ----------------------------
    def clean_skills(self):
        """Clean and standardize the skills/tags column."""

        if "tags" not in self.df.columns:
            return

        self.df["tags"] = (
            self.df["tags"]
            .fillna("")
            .astype(str)

            # Decode HTML entities
            .apply(html.unescape)
            .apply(fix_encoding)

            # Remove literal escape sequences
            .str.replace(
                r"\\n|\\r|\\t",
                " ",
                regex=True
            )

            # Remove actual line breaks
            .str.replace(
                r"[\r\n\t]+",
                " ",
                regex=True
            )

            # Normalize spaces
            .str.replace(
                r"\s+",
                " ",
                regex=True
            )

            .str.strip()
        )

    # ----------------------------
    # Clean URLs
    # ----------------------------
    def clean_urls(self):
        """Clean URL values."""

        if "url" not in self.df.columns:
            return

        self.df["url"] = (
            self.df["url"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    def preserve_missing_locations(self):
        """Location absence is a coverage limitation, not an invalid posting."""
        self.df["location"] = self.df["location"].astype("string")
        missing = self.df["location"].isna() | self.df["location"].fillna("").str.strip().eq("")
        self.df["location_missing"] = missing
        self.df.loc[missing, "location"] = "Unknown"

    # ----------------------------
    # Standardize Dates
    # ----------------------------
    def standardize_dates(self):
        """Convert posted dates into a consistent format."""

        if "date_posted" not in self.df.columns:
            return

        self.df["date_posted"] = pd.to_datetime(
            self.df["date_posted"],
            errors="coerce"
        )

    # ----------------------------
    # Remove Empty Strings
    # ----------------------------
    def remove_empty_strings(self):
        """Remove rows where essential fields are empty."""

        essential_columns = [
            "job_title",
            "company",
        ]

        for column in essential_columns:

            self.df[column] = (
                self.df[column]
                .replace("", pd.NA)
            )

        before = len(self.df)

        self.df.dropna(
            subset=essential_columns,
            inplace=True
        )

        after = len(self.df)

        print(
            f"Rows Removed (Empty Values): {before - after}"
        )

    # ----------------------------
    # Generate Summary
    # ----------------------------
    def generate_summary(self):
        """Display data quality summary."""

        print(
            "\n========== DATA SUMMARY =========="
        )

        print(
            f"Total Records : {len(self.df)}"
        )

        print(
            f"Columns       : {len(self.df.columns)}"
        )

        print(
            "\nMissing Values:"
        )

        print(
            self.df.isnull().sum()
        )

        print(
            "\n=================================="
        )

    # ----------------------------
    # Save Data
    # ----------------------------
    def save_data(self):
        """Save cleaned dataset."""

        output_path = Path(
            "ingestion/output"
        )

        output_path.mkdir(
            parents=True,
            exist_ok=True
        )

        output_file = (
            output_path / "clean_jobs.csv"
        )

        self.df.to_csv(
            output_file,
            index=False,
            encoding="utf-8-sig"
        )

        print(
            "\nCleaned dataset saved successfully!"
        )

        print(
            f"Saved to: {output_file}"
        )

    # ----------------------------
    # Run Pipeline
    # ----------------------------
    def run(self):
        """Execute complete cleaning pipeline."""

        print(
            "Cleaning Started...\n"
        )

        self.remove_duplicates()

        self.remove_missing_values()

        self.preserve_missing_locations()

        self.clean_text()

        self.clean_skills()

        self.clean_urls()

        self.standardize_dates()

        self.remove_empty_strings()

        self.generate_summary()

        self.save_data()

        print(
            "\nCleaning Completed Successfully!"
        )


# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":

    cleaner = DataCleaner(
        "ingestion/remotejobs/output/jobs.csv"
    )

    cleaner.run()
