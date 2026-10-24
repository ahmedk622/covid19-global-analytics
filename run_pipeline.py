import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from clean import clean  # noqa: E402
from export import export_all  # noqa: E402
from ingest import ingest  # noqa: E402
from transform import (  # noqa: E402
    build_dim_country,
    build_dim_date,
    build_fact,
    compute_findings,
    country_summary,
    monthly_table,
)
from validate import overall_status, run_checks, summary_table, write_report  # noqa: E402


def main():
    force = "--refresh" in sys.argv
    print("1/5 ingest")
    ingest(force=force)

    print("2/5 clean")
    data, country_map, log = clean()

    print("3/5 transform")
    fact = build_fact(data)
    dim_date = build_dim_date(fact)
    dim_country = build_dim_country(country_map)
    summary = country_summary(fact, dim_country)
    monthly = monthly_table(fact, dim_country)
    findings = compute_findings(fact, dim_country, summary, log)

    print("4/5 validate")
    checks = run_checks(fact, dim_date, dim_country, country_map, log)
    run_date = write_report(fact, dim_country, checks, log)
    dq_table = summary_table(fact, dim_country, checks, run_date)
    print(f"    status: {overall_status(checks)}")
    if overall_status(checks) == "FAIL":
        sys.exit("validation failed, see reports/data_quality_report.md")

    print("5/5 export")
    export_all(fact, dim_date, dim_country, summary, monthly, dq_table, findings)
    print(f"done: {len(fact):,} fact rows, {fact['ISO_Code'].nunique()} countries")


if __name__ == "__main__":
    main()
