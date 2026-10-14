"""
TalentPulse AI

Module:
Data Validation

Description:
Validates raw job data before cleaning.
"""

import pandas as pd
class DataValidator:
    """Validates raw job dataset."""

    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe

    def check_missing_values(self):
        """Returns missing values for each column."""
        return self.df.isnull().sum()

    def check_duplicates(self):
        """Returns duplicate rows."""
        return self.df.duplicated().sum()

    def check_empty_strings(self):
        """Checks empty string values."""

        empty_counts = {}

        for column in self.df.columns:
            empty_counts[column] = (
                self.df[column]
                .astype(str)
                .str.strip()
                .eq("")
                .sum()
            )

        return empty_counts

    def generate_report(self):
        """Generates data quality report."""

        report = {
            "rows": len(self.df),
            "missing_values": self.check_missing_values(),
            "duplicates": self.check_duplicates(),
            "empty_strings": self.check_empty_strings()
        }

        return report
