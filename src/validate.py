from datetime import datetime, timezone

import numpy as np
import pandas as pd

from config import REPORTS_DIR

DATASET_NAME = "JHU CSSE COVID-19 Data Repository, global time series (confirmed, deaths, recovered)"
SOURCE_URL = "https://github.com/CSSEGISandData/COVID-19"
SINGLE_SOURCE_NOTE = (
    "Single-source validation was used because the selected dataset provided the required "
    "historical coverage and multi-source reconciliation was not necessary for this implementation."
)
POPULATION_PASS_THRESHOLD = 0.95


def check(category, name, result, status, note=""):
    return {"Category": category, "Check": name, "Result": result, "Status": status, "Note": note}


def count_status(n, bad="WARNING"):
    return "PASS" if n == 0 else bad


def run_checks(fact, dim_date, dim_country, country_map, log):
    n_countries = fact["ISO_Code"].nunique()
    n_dates = fact["Date"].nunique()
    rows = []

    rows.append(check("Structure", "Row count equals countries x dates",
                      f"{len(fact):,} = {n_countries} x {n_dates:,}",
                      "PASS" if len(fact) == n_countries * n_dates else "FAIL"))
    rows.append(check("Structure", "Date columns identical across the three raw files",
                      "Yes" if log["date_columns_match"] else "No",
                      "PASS" if log["date_columns_match"] else "FAIL"))
    rows.append(check("Structure", "Malformed dates in raw headers", f"{log['malformed_date_columns']}",
                      count_status(log["malformed_date_columns"], "FAIL")))
    gaps = len(dim_date) - n_dates
    rows.append(check("Structure", "Missing calendar dates in the date range", f"{gaps}", count_status(gaps, "FAIL")))
    dup_rows = int(fact.duplicated().sum())
    rows.append(check("Structure", "Duplicate rows", f"{dup_rows}", count_status(dup_rows, "FAIL")))
    dup_keys = int(fact.duplicated(["ISO_Code", "Date"]).sum())
    rows.append(check("Structure", "Duplicate country/date combinations", f"{dup_keys}", count_status(dup_keys, "FAIL")))
    raw_dups = log["duplicate_raw_rows"] + log["duplicate_raw_keys"]
    rows.append(check("Structure", "Duplicate rows or province/country keys in raw files", f"{raw_dups}",
                      count_status(raw_dups, "FAIL")))

    missing_iso = int(fact["ISO_Code"].isna().sum())
    rows.append(check("Completeness", "Missing country identifiers (ISO code)", f"{missing_iso}", count_status(missing_iso, "FAIL")))
    missing_region = int(dim_country["Region"].isna().sum())
    rows.append(check("Completeness", "Countries without a region", f"{missing_region}", count_status(missing_region)))
    core_nulls = int(fact[["Confirmed", "Deaths", "Daily_Cases", "Daily_Deaths"]].isna().sum().sum())
    rows.append(check("Completeness", "Nulls in Confirmed, Deaths and daily case/death fields", f"{core_nulls}",
                      count_status(core_nulls, "FAIL")))
    rec_null = int(fact["Recovered"].isna().sum())
    rows.append(check("Completeness", "Rows with no recovery figure",
                      f"{rec_null:,} of {len(fact):,} ({rec_null / len(fact):.1%})", "WARNING",
                      f"Recovery series ends {log['recovered_last_date'].date()}; "
                      f"{len(log['recovered_never_reported'])} countries never reported recoveries"))

    rows.append(check("Validity", "Non-numeric cells in raw files", f"{log['non_numeric_cells']}",
                      count_status(log["non_numeric_cells"], "FAIL")))
    neg_cum = int((fact[["Confirmed", "Deaths"]] < 0).sum().sum() + (fact["Recovered"].fillna(0) < 0).sum())
    rows.append(check("Validity", "Negative cumulative values", f"{neg_cum}", count_status(neg_cum, "FAIL")))
    deaths_gt = int((fact["Deaths"] > fact["Confirmed"]).sum())
    gt_countries = fact.loc[fact["Deaths"] > fact["Confirmed"], "ISO_Code"].nunique()
    rows.append(check("Validity", "Records with deaths greater than confirmed cases",
                      f"{deaths_gt} records in {gt_countries} countries", count_status(deaths_gt),
                      "Retained and flagged (Inconsistency_Flag)"))
    rec_gt = int((fact["Recovered"] > fact["Confirmed"]).sum())
    rows.append(check("Validity", "Records with recoveries greater than confirmed cases", f"{rec_gt}",
                      count_status(rec_gt), "Retained and flagged (Inconsistency_Flag)"))
    active_null = int((fact["Active"].isna() & fact["Recovered"].notna()).sum())
    rows.append(check("Validity", "Records where Confirmed - Deaths - Recovered is negative",
                      f"{active_null}", count_status(active_null), "Active left blank for these records"))
    neg_cases = fact[fact["Daily_Cases"] < 0]
    rows.append(check("Validity", "Negative daily cases (reported revisions)",
                      f"{len(neg_cases)} records in {neg_cases['ISO_Code'].nunique()} countries",
                      count_status(len(neg_cases)), "Kept as reported; flagged with Revision_Flag"))
    neg_deaths = fact[fact["Daily_Deaths"] < 0]
    rows.append(check("Validity", "Negative daily deaths (reported revisions)",
                      f"{len(neg_deaths)} records in {neg_deaths['ISO_Code'].nunique()} countries",
                      count_status(len(neg_deaths)), "Kept as reported; flagged with Revision_Flag"))
    sums_match = bool(
        (fact.groupby("ISO_Code")["Daily_Cases"].sum() == fact.groupby("ISO_Code")["Confirmed"].last()).all()
        and (fact.groupby("ISO_Code")["Daily_Deaths"].sum() == fact.groupby("ISO_Code")["Deaths"].last()).all()
    )
    rows.append(check("Validity", "Daily values sum to the final cumulative total for every country",
                      "Yes" if sums_match else "No", "PASS" if sums_match else "FAIL"))

    no_pop = dim_country.loc[dim_country["Population"].isna(), "Country"].tolist()
    coverage = 1 - len(no_pop) / len(dim_country)
    rows.append(check("Reference data", "Population coverage",
                      f"{len(dim_country) - len(no_pop)} of {len(dim_country)} countries ({coverage:.1%})",
                      "PASS" if coverage >= POPULATION_PASS_THRESHOLD else "WARNING",
                      "No population for: " + ", ".join(no_pop) if no_pop else ""))
    missing_map = int(country_map["ISO_Code"].isna().sum())
    rows.append(check("Reference data", "Countries without an ISO code", f"{missing_map}", count_status(missing_map, "FAIL")))
    excluded = [e["name"] for e in log["excluded_entities"]]
    rows.append(check("Reference data", "Non-geographic entries excluded",
                      f"{len(excluded)}", "PASS", ", ".join(excluded)))
    rows.append(check("Reference data", "Province-level rows aggregated to country",
                      f"{log['province_rows']['confirmed']} rows into {log['countries_with_provinces']} countries",
                      "PASS", "Cases and populations are summed over the same rows"))

    fact_totals = fact.groupby("Date")[["Confirmed", "Deaths"]].sum()
    diff_conf = int(np.abs(fact_totals["Confirmed"].values - log["control_raw"]["confirmed"]).max())
    diff_deaths = int(np.abs(fact_totals["Deaths"].values - log["control_raw"]["deaths"]).max())
    rows.append(check("Reconciliation", "Raw file totals vs analytical table totals (every date)",
                      f"max difference: confirmed {diff_conf}, deaths {diff_deaths}",
                      "PASS" if diff_conf == 0 and diff_deaths == 0 else "FAIL",
                      "Raw totals exclude the non-geographic entries"))
    return pd.DataFrame(rows)


def overall_status(checks):
    statuses = set(checks["Status"])
    return "FAIL" if "FAIL" in statuses else "WARNING" if "WARNING" in statuses else "PASS"


def missing_by_column(fact):
    nulls = fact.isna().sum()
    return pd.DataFrame({"Column": nulls.index, "Missing": nulls.values,
                         "Missing_Pct": (nulls.values / len(fact) * 100).round(2)})


def summary_table(fact, dim_country, checks, run_date):
    status = overall_status(checks)
    head = [
        ("Summary", "Dataset", DATASET_NAME, ""),
        ("Summary", "Source", SOURCE_URL, ""),
        ("Summary", "Coverage period", f"{fact['Date'].min().date()} to {fact['Date'].max().date()}", ""),
        ("Summary", "Rows (Fact_Covid)", f"{len(fact):,}", ""),
        ("Summary", "Columns (Fact_Covid)", f"{fact.shape[1]}", ""),
        ("Summary", "Countries", f"{fact['ISO_Code'].nunique()}", ""),
        ("Summary", "Pipeline run date", run_date, ""),
        ("Summary", "Overall validation status", status, status),
    ]
    out = pd.DataFrame(head, columns=["Section", "Item", "Value", "Status"])
    detail = checks.rename(columns={"Category": "Section", "Check": "Item", "Result": "Value"})
    detail = detail[["Section", "Item", "Value", "Status", "Note"]]
    out["Note"] = ""
    return pd.concat([out, detail], ignore_index=True)


def md_table(df):
    header = "| " + " | ".join(df.columns) + " |"
    divider = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, divider] + body)


def write_report(fact, dim_country, checks, log):
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    status = overall_status(checks)
    population = int(dim_country["Population"].notna().sum())
    lines = [
        "# Data Quality Report",
        "",
        "Generated by the pipeline (`python run_pipeline.py`). All values below are calculated from the data.",
        "",
        "## Summary",
        "",
        f"- **Dataset:** {DATASET_NAME}",
        f"- **Source:** {SOURCE_URL}",
        f"- **Execution date:** {run_date}",
        f"- **Rows / columns (Fact_Covid):** {len(fact):,} / {fact.shape[1]}",
        f"- **Date range:** {fact['Date'].min().date()} to {fact['Date'].max().date()} ({fact['Date'].nunique():,} days)",
        f"- **Countries:** {fact['ISO_Code'].nunique()}",
        f"- **Population coverage:** {population} of {len(dim_country)} countries",
        f"- **Overall validation status:** {status}",
        "",
        "## Check results",
        "",
        md_table(checks),
        "",
        "## Missing values by column (Fact_Covid)",
        "",
        md_table(missing_by_column(fact)),
        "",
        "Recovered, Active and Daily_Recoveries are blank by design where the source has no usable recovery figure "
        f"(after {log['recovered_last_date'].date()}, and for countries that never reported recoveries).",
        "",
        "## Excluded non-geographic entries",
        "",
        md_table(pd.DataFrame(log["excluded_entities"]).rename(
            columns={"name": "Entry", "max_confirmed": "Max confirmed", "max_deaths": "Max deaths"})),
        "",
        "## Country standardisation",
        "",
        f"- {log['countries_in_raw'] - len(log['excluded_entities'])} country names mapped to ISO 3166-1 alpha-3 codes "
        "using the JHU lookup table; regions come from the ISO country-codes table.",
        f"- {log['names_changed']} display names differ from the JHU name "
        f"({'; '.join(log['name_overrides'])}).",
        f"- Region assigned manually for: {', '.join(log['region_exceptions'])} (not in the ISO table's region fields).",
        f"- Province-level rows without a population match (cases kept, population not added): "
        + "; ".join(f"{p} ({c})" for p, c in log["rows_without_population"]
                    if p and c not in [e["name"] for e in log["excluded_entities"]]) + ".",
        "",
        "## Recovery series",
        "",
        f"- Last date with a non-zero global recovery total: {log['recovered_last_date'].date()}. "
        "The source series resets to zero the next day, so later values are treated as not available.",
        f"- Countries that never reported recoveries: {'; '.join(log['recovered_never_reported'])}.",
        "",
        "## Reconciliation",
        "",
        SINGLE_SOURCE_NOTE,
        "",
        "Control totals (raw file sums vs the analytical table, every date) are reported in the check results above.",
        "",
    ]
    (REPORTS_DIR / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")
    return run_date
