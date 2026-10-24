RECOVERY_NOTE = "Blank after 2021-08-04 (source series ends) and for countries that never reported recoveries."

FIELDS = [
    # table, field, type, description, derivation, unit, aggregation, caveat
    ("Fact_Covid", "Date", "date", "Reporting date.", "JHU column header (m/d/yy) parsed to a date.", "date", "Group by / filter", "Reporting date, not the date of infection or death."),
    ("Fact_Covid", "ISO_Code", "text", "ISO 3166-1 alpha-3 country key. Joins to Dim_Country.", "JHU UID lookup table, matched on JHU country name.", "key", "Do not aggregate", "Kosovo uses XKS (JHU's code; not an official ISO code)."),
    ("Fact_Covid", "Confirmed", "integer", "Cumulative reported confirmed cases up to and including Date.", "JHU confirmed file; provinces summed to country.", "cases", "Non-additive over time: use the value on the last date in the period. Additive across countries on one date.", "Reported cases depend on testing and case definitions. Can decrease when a country revises its series."),
    ("Fact_Covid", "Deaths", "integer", "Cumulative reported deaths up to and including Date.", "JHU deaths file; provinces summed to country.", "deaths", "Same as Confirmed.", "Death definitions differ between countries (with COVID vs from COVID)."),
    ("Fact_Covid", "Recovered", "integer (nullable)", "Cumulative reported recoveries.", "JHU recovered file; provinces summed to country.", "people", "Same as Confirmed.", RECOVERY_NOTE),
    ("Fact_Covid", "Active", "integer (nullable)", "Confirmed minus Deaths minus Recovered.", "Calculated where Recovered is available and the result is not negative.", "cases", "Same as Confirmed.", "Blank where Recovered is blank or where the result would be negative (inconsistent source values)."),
    ("Fact_Covid", "Daily_Cases", "integer", "Change in Confirmed since the previous date.", "Confirmed(t) - Confirmed(t-1). On the first date it equals Confirmed.", "cases per day", "Sum over any period.", "Negative when a country revised its cumulative total downward. Negative values are kept, not zeroed, so daily values add back to the cumulative total. Many countries moved to weekly reporting in 2022-23, so daily values are lumpy."),
    ("Fact_Covid", "Daily_Deaths", "integer", "Change in Deaths since the previous date.", "Deaths(t) - Deaths(t-1). On the first date it equals Deaths.", "deaths per day", "Sum over any period.", "Same revision and batch-reporting caveats as Daily_Cases. A single-day value can be a backlog release."),
    ("Fact_Covid", "Daily_Recoveries", "integer (nullable)", "Change in Recovered since the previous date.", "Recovered(t) - Recovered(t-1) where both exist.", "people per day", "Sum over any period.", RECOVERY_NOTE),
    ("Fact_Covid", "Revision_Flag", "integer (0/1)", "1 when Daily_Cases, Daily_Deaths or Daily_Recoveries is negative.", "Calculated.", "flag", "Sum to count records.", "Marks a reported historical revision (cumulative total went down), not necessarily an error."),
    ("Fact_Covid", "Inconsistency_Flag", "integer (0/1)", "1 when Deaths + Recovered exceeds Confirmed.", "Calculated.", "flag", "Sum to count records.", "Marks values that cannot all be true at the same time. Values are kept as reported."),
    ("Dim_Date", "Date", "date", "One row per calendar day from the first to the last date in the data.", "Continuous date range.", "date", "Key", "Mark as date table in Power BI."),
    ("Dim_Date", "Year", "integer", "Calendar year.", "From Date.", "year", "", ""),
    ("Dim_Date", "Quarter", "integer", "Calendar quarter (1-4).", "From Date.", "quarter", "", ""),
    ("Dim_Date", "Year_Quarter", "text", "Year and quarter, e.g. 2021-Q3.", "From Date.", "label", "", ""),
    ("Dim_Date", "Month_Number", "integer", "Month of year (1-12). Use to sort Month_Name.", "From Date.", "month", "", ""),
    ("Dim_Date", "Month_Name", "text", "English month name.", "From Date.", "label", "", ""),
    ("Dim_Date", "Year_Month", "text", "Year and month, e.g. 2021-07. Sorts chronologically as text.", "From Date.", "label", "", "The last month (2023-03) is partial."),
    ("Dim_Date", "Week_Start", "date", "Monday of the week containing Date.", "From Date.", "date", "", ""),
    ("Dim_Date", "Weekday_Number", "integer", "Day of week, Monday = 1.", "From Date.", "day", "", ""),
    ("Dim_Date", "Weekday_Name", "text", "English weekday name.", "From Date.", "label", "", ""),
    ("Dim_Date", "Is_Weekend", "integer (0/1)", "1 for Saturday and Sunday.", "From Date.", "flag", "", "Many countries report less on weekends."),
    ("Dim_Country", "ISO_Code", "text", "ISO 3166-1 alpha-3 country key.", "JHU UID lookup table.", "key", "Key", ""),
    ("Dim_Country", "Country", "text", "Standard country name used in reports.", "JHU name, with 9 explicit renames (see data_quality_report.md).", "label", "", ""),
    ("Dim_Country", "JHU_Name", "text", "Country name exactly as written in the JHU files.", "JHU files.", "label", "", "Kept for traceability."),
    ("Dim_Country", "ISO2_Code", "text", "ISO 3166-1 alpha-2 code.", "JHU UID lookup table.", "label", "", ""),
    ("Dim_Country", "Region", "text", "UN continental region (Africa, Americas, Asia, Europe, Oceania).", "datasets/country-codes table; Kosovo and Antarctica assigned manually.", "label", "", ""),
    ("Dim_Country", "Sub_Region", "text", "UN sub-region.", "datasets/country-codes table; Kosovo and Antarctica assigned manually.", "label", "", ""),
    ("Dim_Country", "Population", "integer (nullable)", "Population used as the denominator for per-100K rates.", "JHU UID lookup table. For countries made of several JHU rows (e.g. France with overseas territories) the populations of the rows included in the case counts are summed.", "people", "Do not sum over time. Sum across selected countries only when the same countries are in the numerator.", "Single reference value, not time-varying. Reference year is not stated in the source file. Blank for Antarctica."),
    ("Dim_Country", "Latitude", "decimal", "Country centre point from the JHU lookup table.", "JHU UID lookup table.", "degrees", "", "Not a precise centroid."),
    ("Dim_Country", "Longitude", "decimal", "Country centre point from the JHU lookup table.", "JHU UID lookup table.", "degrees", "", "Not a precise centroid."),
]

COLUMNS = ["Table", "Field", "Data type", "Description", "Source / derivation", "Unit", "Aggregation guidance", "Caveat"]


def dictionary_markdown():
    lines = [
        "# Data Dictionary",
        "",
        "Tables in `data/processed/` (also loaded into `outputs/covid.db` for the SQL queries).",
        "Cases per 100K, CFR and rolling averages are not stored in the fact table: they depend on the "
        "slicer selection, so they are defined as measures (see `powerbi/measures.dax`, `sql/analysis.sql`).",
        "",
    ]
    for table in ("Fact_Covid", "Dim_Date", "Dim_Country"):
        lines += [f"## {table}", ""]
        lines.append("| Field | Type | Description | Source / derivation | Unit | Aggregation | Caveat |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in FIELDS:
            if row[0] == table:
                lines.append("| `{}` | {} | {} | {} | {} | {} | {} |".format(*row[1:]))
        lines.append("")
    lines += [
        "## Negative daily values",
        "",
        "A negative `Daily_Cases` or `Daily_Deaths` means the country's cumulative total went down from one day to the next. "
        "The pipeline keeps these values exactly as reported and sets `Revision_Flag = 1`, because the source gives no way to "
        "tell which earlier days the correction belongs to. Records that are impossible rather than revised "
        "(deaths above confirmed cases, recoveries above confirmed cases) are flagged with `Inconsistency_Flag`. "
        "Neither flag changes any value.",
        "",
    ]
    return "\n".join(lines)
