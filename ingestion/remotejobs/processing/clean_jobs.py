"""
TalentPulse AI

Module:
Data Cleaning

Description:
Cleans the raw job dataset after validation.
"""

import pandas as pd
from pathlib import Path


class DataCleaner:
    """Cleans and standardizes raw job data."""

    def __init__(self, input_file: str):
        self.input_file = input_file
        self.df = pd.read_csv(input_file)

    def remove_duplicates(self):
        """Remove duplicate rows."""
        before = len(self.df)
        self.df.drop_duplicates(inplace=True)
        after = len(self.df)

        print(f"Duplicates Removed : {before - after}")

    def remove_missing_values(self):
        """Remove rows having missing important fields."""
        before = len(self.df)

        self.df.dropna(
            subset=["job_title", "company", "location"],
            inplace=True
        )

        after = len(self.df)

        print(f"Rows Removed (Missing Values): {before - after}")

    def clean_text(self):
        """Standardize text columns."""

        text_columns = ["job_title", "company", "location"]

        for column in text_columns:
            self.df[column] = (
                self.df[column]
                .astype(str)
                .str.strip()
                .str.title()
            )

    def remove_empty_strings(self):
        """Remove rows containing empty strings."""

        self.df = self.df[
            (self.df["job_title"] != "")
            & (self.df["company"] != "")
            & (self.df["location"] != "")
        ]

    def save_data(self):
        """Save cleaned data."""

        output_path = Path("ingestion/output")
        output_path.mkdir(parents=True, exist_ok=True)

        self.df.to_csv(
            output_path / "clean_jobs.csv",
            index=False
        )

        print("\nCleaned dataset saved successfully!")

    def generate_summary(self):
        """Display cleaning summary."""

        print("\n========== DATA SUMMARY ==========")
        print(f"Total Records : {len(self.df)}")
        print(f"Columns       : {len(self.df.columns)}")
        print("\nMissing Values")
        print(self.df.isnull().sum())
        print("==================================")

    def run(self):
        """Execute complete cleaning pipeline."""

        print("Cleaning Started...\n")

        self.remove_duplicates()
        self.remove_missing_values()
        self.clean_text()
        self.remove_empty_strings()

        self.generate_summary()

        self.save_data()

        print("\nCleaning Completed Successfully!")


if __name__ == "__main__":
    cleaner = DataCleaner(
        "ingestion/remotejobs/output/jobs.csv"
    )

    cleaner.run()