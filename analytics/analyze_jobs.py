import pandas as pd

df = pd.read_csv(
    "ingestion/remotejobs/output/jobs.csv"
)

print(df.head())

print("\nTotal Jobs:")
print(len(df))

print("\nTop Companies:")
print(df["company"].value_counts().head(10))

# """
# Remote Jobs Analysis Script
# ----------------------------
# Analyzes a jobs.csv file produced by a remote-jobs ingestion pipeline.
# Auto-detects common column-name variants, prints console summaries,
# saves charts as PNGs, and writes a markdown summary report.

# Usage:
#     python analyze_jobs.py
#     python analyze_jobs.py path/to/other_jobs.csv
# """

# import re
# import sys
# from collections import Counter
# from pathlib import Path

# import matplotlib.pyplot as plt
# import pandas as pd
# import seaborn as sns

# # ----------------------------------------------------------------------------
# # Config
# # ----------------------------------------------------------------------------
# CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "ingestion/remotejobs/output/jobs.csv"
# OUTPUT_DIR = Path("ingestion/remotejobs/output/analysis")
# OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# sns.set_theme(style="whitegrid")
# plt.rcParams["figure.dpi"] = 110
# TOP_N = 10

# # The scraper output isn't always consistent across sources, so for each
# # logical field we try a list of common real-world column-name aliases.
# COLUMN_ALIASES = {
#     "title": ["title", "job_title", "position"],
#     "company": ["company", "company_name", "employer"],
#     "location": ["location", "job_location", "city"],
#     "date": ["date_posted", "posted_date", "date", "created_at", "scraped_at"],
#     "salary": ["salary", "salary_range", "compensation"],
#     "salary_min": ["salary_min", "min_salary"],
#     "salary_max": ["salary_max", "max_salary"],
#     "job_type": ["job_type", "employment_type", "type"],
#     "source": ["source", "site", "board"],
#     "tags": ["tags", "skills", "category", "categories"],
# }


# def resolve_column(df, logical_name):
#     """Return the first matching real column name for a logical field, or None."""
#     for candidate in COLUMN_ALIASES.get(logical_name, []):
#         if candidate in df.columns:
#             return candidate
#     return None


# def load_data(path):
#     df = pd.read_csv(path)
#     print(f"Loaded {len(df):,} rows from {path}")
#     print(f"Columns: {list(df.columns)}\n")
#     return df


# def basic_overview(df):
#     print("=" * 60)
#     print("BASIC OVERVIEW")
#     print("=" * 60)
#     print(df.head(), "\n")
#     print(f"Total jobs: {len(df):,}")
#     print(f"Total columns: {df.shape[1]}\n")

#     missing = df.isna().sum()
#     missing = missing[missing > 0].sort_values(ascending=False)
#     print("Missing values per column:")
#     print("  None — clean dataset." if missing.empty else missing.to_string())

#     dupes = df.duplicated().sum()
#     print(f"\nExact duplicate rows: {dupes:,}\n")


# def plot_top_categorical(series, title, filename, top_n=TOP_N):
#     counts = series.value_counts().head(top_n)
#     fig, ax = plt.subplots(figsize=(8, 5))
#     colors = sns.color_palette("viridis", len(counts))
#     ax.barh(counts.index[::-1], counts.values[::-1], color=list(reversed(colors)))
#     ax.set_title(title)
#     ax.set_xlabel("Number of jobs")
#     fig.tight_layout()
#     fig.savefig(OUTPUT_DIR / filename)
#     plt.close(fig)
#     return counts


# def analyze_companies(df, col):
#     print("=" * 60)
#     print("TOP COMPANIES")
#     print("=" * 60)
#     counts = plot_top_categorical(df[col], f"Top {TOP_N} Hiring Companies", "top_companies.png")
#     print(counts.to_string())
#     print(f"\nUnique companies: {df[col].nunique():,}\n")
#     return counts


# def analyze_locations(df, col):
#     print("=" * 60)
#     print("TOP LOCATIONS")
#     print("=" * 60)
#     # Some scrapers (e.g. RemoteOK) leave trailing commas like "Madison, "
#     cleaned = df[col].astype(str).str.strip().str.rstrip(",").str.strip()
#     cleaned = cleaned.replace("", "Remote / Unspecified")
#     counts = plot_top_categorical(cleaned, f"Top {TOP_N} Locations", "top_locations.png")
#     print(counts.to_string())

#     remote_mask = df[col].astype(str).str.contains("remote", case=False, na=False)
#     if remote_mask.any():
#         print(f"\nShare of postings mentioning 'remote': {remote_mask.mean():.1%}")
#     print()
#     return counts


# TITLE_STOPWORDS = {"and", "or", "the", "a", "for", "of", "in", "to", "with", "on", "ii", "iii", "i"}


# def analyze_titles(df, col):
#     print("=" * 60)
#     print("JOB TITLE KEYWORDS")
#     print("=" * 60)
#     words = []
#     for title in df[col].dropna():
#         tokens = re.findall(r"[a-zA-Z+#]+", str(title).lower())
#         words.extend(t for t in tokens if t not in TITLE_STOPWORDS and len(t) > 1)

#     common = Counter(words).most_common(20)
#     for word, count in common:
#         print(f"  {word:<20} {count}")
#     print()

#     if common:
#         top_words = dict(common[:15])
#         fig, ax = plt.subplots(figsize=(8, 6))
#         ax.barh(list(top_words.keys())[::-1], list(top_words.values())[::-1], color="teal")
#         ax.set_title("Most Common Words in Job Titles")
#         ax.set_xlabel("Frequency")
#         fig.tight_layout()
#         fig.savefig(OUTPUT_DIR / "title_keywords.png")
#         plt.close(fig)


# def analyze_trend(df, col):
#     print("=" * 60)
#     print("POSTING TREND OVER TIME")
#     print("=" * 60)
#     dates = pd.to_datetime(df[col], errors="coerce")
#     valid = dates.dropna()
#     if valid.empty:
#         print("Could not parse any dates — skipping trend analysis.\n")
#         return

#     daily = valid.dt.date.value_counts().sort_index()
#     print(f"Date range: {daily.index.min()} to {daily.index.max()}")
#     print(f"Average postings/day: {daily.mean():.1f}\n")

#     fig, ax = plt.subplots(figsize=(10, 4))
#     daily.plot(ax=ax, marker="o", color="darkorange")
#     ax.set_title("Job Postings Over Time")
#     ax.set_ylabel("Jobs posted")
#     fig.tight_layout()
#     fig.savefig(OUTPUT_DIR / "postings_trend.png")
#     plt.close(fig)


# def analyze_job_type(df, col):
#     print("=" * 60)
#     print("JOB TYPE BREAKDOWN")
#     print("=" * 60)
#     counts = df[col].value_counts()
#     print(counts.to_string(), "\n")

#     fig, ax = plt.subplots(figsize=(6, 6))
#     ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%", startangle=90)
#     ax.set_title("Job Type Distribution")
#     fig.tight_layout()
#     fig.savefig(OUTPUT_DIR / "job_type_distribution.png")
#     plt.close(fig)


# def analyze_source(df, col):
#     print("=" * 60)
#     print("SOURCE BREAKDOWN")
#     print("=" * 60)
#     print(df[col].value_counts().to_string(), "\n")


# def analyze_tags(df, col):
#     print("=" * 60)
#     print("TOP SKILLS / TAGS")
#     print("=" * 60)
#     all_tags = []
#     for entry in df[col].dropna():
#         parts = re.split(r"[,;|]", str(entry))
#         all_tags.extend(p.strip().lower() for p in parts if p.strip())

#     for tag, count in Counter(all_tags).most_common(15):
#         print(f"  {tag:<25} {count}")
#     print()


# def analyze_salary_minmax(df, min_col, max_col, company_col=None):
#     print("=" * 60)
#     print("SALARY ANALYSIS")
#     print("=" * 60)
#     sal_min = pd.to_numeric(df[min_col], errors="coerce")
#     sal_max = pd.to_numeric(df[max_col], errors="coerce")
#     midpoint = (sal_min + sal_max) / 2
#     valid = midpoint[(midpoint > 0) & midpoint.notna()]

#     if valid.empty:
#         print("No usable salary data — skipping.\n")
#         return

#     print(f"Postings with salary disclosed: {len(valid):,} / {len(df):,} "
#           f"({len(valid) / len(df):.1%})")
#     print(valid.describe().to_string(), "\n")

#     fig, ax = plt.subplots(figsize=(8, 5))
#     sns.histplot(valid, bins=30, kde=True, ax=ax, color="slateblue")
#     ax.set_title("Salary Distribution (USD, midpoint of posted range)")
#     ax.set_xlabel("Salary")
#     fig.tight_layout()
#     fig.savefig(OUTPUT_DIR / "salary_distribution.png")
#     plt.close(fig)

#     if company_col:
#         temp = pd.DataFrame({company_col: df.loc[valid.index, company_col], "midpoint": valid})
#         top_paying = (
#             temp.groupby(company_col)["midpoint"]
#             .agg(["mean", "count"])
#             .query("count >= 2")
#             .sort_values("mean", ascending=False)
#             .head(TOP_N)
#         )
#         if not top_paying.empty:
#             print(f"Top {TOP_N} highest-paying companies (avg midpoint, min. 2 postings):")
#             print(top_paying.round(0).to_string(), "\n")


# def _extract_numbers(value):
#     return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(value).replace(",", ""))]


# def analyze_salary(df, col):
#     print("=" * 60)
#     print("SALARY ANALYSIS")
#     print("=" * 60)
#     parsed = df[col].dropna().apply(_extract_numbers)
#     midpoints = parsed.apply(lambda nums: sum(nums) / len(nums) if nums else None).dropna()

#     if midpoints.empty:
#         print("Could not parse numeric salary values — skipping.\n")
#         return

#     print(f"Postings with parsable salary: {len(midpoints):,} / {len(df):,}")
#     print(midpoints.describe().to_string(), "\n")

#     fig, ax = plt.subplots(figsize=(8, 5))
#     sns.histplot(midpoints, bins=30, kde=True, ax=ax, color="slateblue")
#     ax.set_title("Salary Distribution (parsed midpoint)")
#     ax.set_xlabel("Salary")
#     fig.tight_layout()
#     fig.savefig(OUTPUT_DIR / "salary_distribution.png")
#     plt.close(fig)


# def write_report(df, resolved):
#     lines = ["# Remote Jobs Analysis Report", "", f"- **Total jobs analyzed:** {len(df):,}"]
#     if resolved["company"]:
#         lines.append(f"- **Unique companies:** {df[resolved['company']].nunique():,}")
#     if resolved["location"]:
#         lines.append(f"- **Unique locations:** {df[resolved['location']].nunique():,}")
#     lines.append("")
#     lines.append("Charts saved in this folder:")
#     for f in sorted(OUTPUT_DIR.glob("*.png")):
#         lines.append(f"- {f.name}")

#     report_path = OUTPUT_DIR / "summary_report.md"
#     report_path.write_text("\n".join(lines))
#     print(f"Summary report written to: {report_path}")


# def main():
#     df = load_data(CSV_PATH)
#     basic_overview(df)

#     resolved = {name: resolve_column(df, name) for name in COLUMN_ALIASES}

#     if resolved["company"]:
#         analyze_companies(df, resolved["company"])
#     if resolved["location"]:
#         analyze_locations(df, resolved["location"])
#     if resolved["title"]:
#         analyze_titles(df, resolved["title"])
#     if resolved["date"]:
#         analyze_trend(df, resolved["date"])
#     if resolved["job_type"]:
#         analyze_job_type(df, resolved["job_type"])
#     if resolved["source"]:
#         analyze_source(df, resolved["source"])
#     if resolved["tags"]:
#         analyze_tags(df, resolved["tags"])
#     if resolved.get("salary_min") and resolved.get("salary_max"):
#         analyze_salary_minmax(df, resolved["salary_min"], resolved["salary_max"], resolved.get("company"))
#     elif resolved["salary"]:
#         analyze_salary(df, resolved["salary"])

#     write_report(df, resolved)
#     print(f"\nAll charts saved to: {OUTPUT_DIR.resolve()}")


# if __name__ == "__main__":
#     main()