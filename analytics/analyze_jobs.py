"""Generate validated, read-only analytics from the existing Snowflake warehouse."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from analytics.warehouse_analytics import collect, save
from warehouse.snowflake_loader import create_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'ingestion/output/transformed_jobs.csv')
    parser.add_argument('--output', type=Path, default=ROOT/'analytics/output')
    args = parser.parse_args()
    connection = create_connection()
    try:
        report = collect(connection, args.input)
    finally:
        connection.close()
    save(report, args.output)
    print(json.dumps({'total_jobs': report['total_jobs'], 'unique_companies': report['unique_companies'],
                      'coverage': report['coverage'], 'salary': report['salary'],
                      'report_directory': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
