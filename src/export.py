import json
import sqlite3

import matplotlib
import numpy as np
import pandas as pd
import xlsxwriter

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from config import EXCEL_DIR, OUTPUTS_DIR, PROCESSED_DIR, REPORTS_DIR, ROOT  # noqa: E402
from dictionary import COLUMNS as DICT_COLUMNS, FIELDS, dictionary_markdown  # noqa: E402
from transform import add_rolling  # noqa: E402
from validate import DATASET_NAME, SINGLE_SOURCE_NOTE, SOURCE_URL  # noqa: E402


def write_csvs(fact, dim_date, dim_country, dq_table):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = {"index": False, "date_format": "%Y-%m-%d", "encoding": "utf-8"}
    fact.to_csv(PROCESSED_DIR / "Fact_Covid.csv", **kwargs)
    dim_date.to_csv(PROCESSED_DIR / "Dim_Date.csv", **kwargs)
    dim_country.to_csv(PROCESSED_DIR / "Dim_Country.csv", **kwargs)
    dq_table.to_csv(PROCESSED_DIR / "DQ_Checks.csv", **kwargs)


def write_sqlite(fact, dim_date, dim_country):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUTS_DIR / "covid.db"
    path.unlink(missing_ok=True)
    tables = {"Fact_Covid": fact, "Dim_Date": dim_date, "Dim_Country": dim_country}
    with sqlite3.connect(path) as conn:
        for name, df in tables.items():
            out = df.copy()
            for col in out.select_dtypes(include=["datetime"]).columns:
                out[col] = out[col].dt.strftime("%Y-%m-%d")
            out.to_sql(name, conn, index=False)
        conn.execute("CREATE UNIQUE INDEX ix_fact ON Fact_Covid (ISO_Code, Date)")
        conn.execute("CREATE UNIQUE INDEX ix_country ON Dim_Country (ISO_Code)")
        conn.execute("CREATE UNIQUE INDEX ix_date ON Dim_Date (Date)")


def write_docs():
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "data_dictionary.md").write_text(dictionary_markdown(), encoding="utf-8")


def fmt_int(value):
    return f"{int(round(value)):,}"


def write_findings(findings):
    f = findings
    peaks_c = ", ".join(f"{p['date']} ({fmt_int(p['avg_7d'])}/day)" for p in f["global_peaks_cases"])
    peaks_d = ", ".join(f"{p['date']} ({fmt_int(p['avg_7d'])}/day)" for p in f["global_peaks_deaths"])
    year_lines = [
        f"  - {y['year']}{' (to ' + f['last_date'] + ')' if y['days'] < 365 and y['year'] == int(f['last_date'][:4]) else ''}: "
        f"{fmt_int(y['cases'])} cases ({y['cases_share']:.1f}% of total), {fmt_int(y['deaths'])} deaths ({y['deaths_share']:.1f}% of total)"
        for y in f["by_year"]
    ]
    rank = lambda rows, unit="": "; ".join(f"{r['country']} ({fmt_int(r['value'])}{unit})" for r in rows)
    rank_share = lambda rows: "; ".join(f"{r['country']} ({fmt_int(r['value'])}, {r['share_of_total']:.1f}%)" for r in rows)
    rev = f["revisions"]
    lines = [
        "# Key Findings",
        "",
        f"Calculated from the analytical dataset: {f['countries']} countries, {f['first_date']} to {f['last_date']}. "
        "All figures are cases and deaths as reported to JHU; see the limitations in the README before comparing countries.",
        "",
        f"- **Totals at {f['last_date']}:** {fmt_int(f['total_cases'])} reported cases and {fmt_int(f['total_deaths'])} "
        f"reported deaths across the {f['countries']} countries (reported deaths / reported cases = {f['global_cfr_pct']:.2f}%).",
        f"- **Most reported cases:** {rank_share(f['top_cases'])}.",
        f"- **Most reported deaths:** {rank_share(f['top_deaths'])}.",
        f"- **Highest reported cases per 100K** (countries with population of at least {fmt_int(f['ranking_population_floor'])}; "
        f"{f['ranking_countries']} countries): {rank(f['top_cases_per_100k'])}.",
        f"- **Highest reported deaths per 100K** (same population floor): {rank(f['top_deaths_per_100k'])}.",
        f"- **Largest single-day values:** {fmt_int(f['max_daily_cases']['value'])} cases in {f['max_daily_cases']['country']} "
        f"on {f['max_daily_cases']['date']}; {fmt_int(f['max_daily_deaths']['value'])} deaths in {f['max_daily_deaths']['country']} "
        f"on {f['max_daily_deaths']['date']}.",
        f"- **Largest peaks in the global 7-day average of daily cases** (peaks at least 120 days apart): {peaks_c}.",
        f"- **Largest peaks in the global 7-day average of daily deaths** (same rule): {peaks_d}.",
        "- **Reported cases and deaths by calendar year:**",
    ] + year_lines + [
        f"- **Recoveries:** the source recovery series ends {f['recovered']['last_date']}. On that date "
        f"{f['recovered']['countries_reporting']} countries had a recovery figure, totalling {fmt_int(f['recovered']['total'])}.",
        f"- **Reported revisions:** {rev['negative_daily_cases_records']} country-days have negative daily cases "
        f"({rev['negative_daily_cases_countries']} countries) and {rev['negative_daily_deaths_records']} have negative daily deaths. "
        f"The largest downward revision of cases is {fmt_int(abs(rev['largest_negative_cases']['value']))} in "
        f"{rev['largest_negative_cases']['country']} on {rev['largest_negative_cases']['date']}.",
        "",
        "## Reading these results",
        "",
        f"- The largest single-day death value ({f['max_daily_deaths']['country']}, {f['max_daily_deaths']['date']}) "
        f"is surrounded by days with at most {fmt_int(f['max_daily_deaths']['neighbour_max'])} reported deaths "
        "(three days either side), which is consistent with a batch addition to the cumulative series "
        "rather than deaths on a single day.",
        "- Per-100K rankings use a single population figure per country and depend on how much testing each country did.",
        "- Rankings by reported cases are influenced by population size as well as testing and reporting capacity.",
        "",
    ]
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "key_findings.md").write_text("\n".join(lines), encoding="utf-8")
    OUTPUTS_DIR.mkdir(exist_ok=True)
    (OUTPUTS_DIR / "key_findings.json").write_text(json.dumps(findings, indent=2, default=str) + "\n")


def write_charts(fact, summary, findings):
    daily = fact.groupby("Date")[["Daily_Cases", "Daily_Deaths"]].sum()
    avg = daily.rolling(7).mean()
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    for ax, col, label in ((axes[0], "Daily_Cases", "cases"), (axes[1], "Daily_Deaths", "deaths")):
        ax.bar(daily.index, daily[col], width=1.0, color="#c9ced6", label=f"Daily {label}")
        ax.plot(avg.index, avg[col], color="#1f3a5f", linewidth=1.4, label="7-day average")
        ax.set_ylabel(f"Reported {label} per day")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.legend(loc="upper left", frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_title(f"Reported daily cases and deaths, sum of {fact['ISO_Code'].nunique()} countries", loc="left", fontsize=11)
    fig.text(0.01, 0.005, f"Source: JHU CSSE, {findings['first_date']} to {findings['last_date']}. "
             "Reporting frequency varies by country and date.", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUTPUTS_DIR / "global_trend.png", dpi=130)
    plt.close(fig)

    ranked = summary[summary["Population"].astype("float64") >= findings["ranking_population_floor"]]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, col, title in ((axes[0], "Cases_Per_100K", "Reported cases per 100K"),
                           (axes[1], "Deaths_Per_100K", "Reported deaths per 100K")):
        top = ranked.nlargest(10, col).iloc[::-1]
        ax.barh(top["Country"], top[col], color="#1f3a5f")
        ax.set_title(title, loc="left", fontsize=11)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, f"Top 10, countries with population of at least {findings['ranking_population_floor']:,}. "
             f"Cumulative to {findings['last_date']}. Source: JHU CSSE.", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUTS_DIR / "top_countries_per_100k.png", dpi=130)
    plt.close(fig)


def blank(value):
    return "" if pd.isna(value) else value


def write_excel(fact, summary, monthly, dq_table, findings):
    EXCEL_DIR.mkdir(exist_ok=True)
    wb = xlsxwriter.Workbook(EXCEL_DIR / "covid_analysis.xlsx", {"nan_inf_to_errors": False})
    base = {"font_name": "Calibri", "font_size": 10}
    f_title = wb.add_format({**base, "bold": True, "font_size": 16, "font_color": "#1f3a5f"})
    f_head = wb.add_format({**base, "bold": True, "font_color": "#1f3a5f"})
    f_wrap = wb.add_format({**base, "text_wrap": True, "valign": "top"})
    f_text = wb.add_format(base)
    f_int = wb.add_format({**base, "num_format": "#,##0"})
    f_dec = wb.add_format({**base, "num_format": "#,##0.0"})
    f_pct = wb.add_format({**base, "num_format": "0.0%"})
    f_pct2 = wb.add_format({**base, "num_format": "0.00"})
    f_date = wb.add_format({**base, "num_format": "yyyy-mm-dd"})
    f_note = wb.add_format({**base, "italic": True, "font_color": "#666666"})
    f_bold_int = wb.add_format({**base, "bold": True, "num_format": "#,##0", "top": 1})
    f_bold = wb.add_format({**base, "bold": True, "top": 1})

    # Overview
    ws = wb.add_worksheet("Overview")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 28)
    ws.set_column("B:B", 100)
    ws.write("A1", "COVID-19 Reported Cases and Deaths: Analysis Workbook", f_title)
    info = [
        ("Dataset", DATASET_NAME),
        ("Source", SOURCE_URL),
        ("Coverage", f"{findings['first_date']} to {findings['last_date']}, {findings['countries']} countries"),
        ("Values", "Reported (not estimated) cumulative cases, deaths and recoveries; daily values are differences of the cumulative series."),
        ("Reconciliation", SINGLE_SOURCE_NOTE),
        ("Full daily data", "data/processed/Fact_Covid.csv (too large for a worksheet). This workbook holds summaries and a country-by-month table."),
        ("Google Sheets", "Formulas use plain A1 ranges and standard functions (SUMIFS, RANK, EOMONTH). The workbook has not been deployed to Google Sheets."),
    ]
    for i, (k, v) in enumerate(info, start=3):
        ws.write(i, 0, k, f_head)
        ws.write(i, 1, v, f_wrap)
    start = 3 + len(info) + 1
    ws.write(start, 0, "Sheets", f_head)
    guide = [
        ("Data_Dictionary", "Every field in the analytical tables."),
        ("Data_Quality", "Validation results from the pipeline."),
        ("Country_Summary", "One row per country: totals, CFR, per-100K rates, peaks. Rates are formulas."),
        ("Monthly_Global", "Monthly global cases and deaths (SUMIFS over Analytical_Data) with a chart."),
        ("Pivot_Analysis", "Region x year cross-tabs built with SUMIFS. For a native PivotTable use Insert > PivotTable on Analytical_Data."),
        ("Analytical_Data", "Country x month table (cases, deaths, cumulative values)."),
    ]
    for i, (k, v) in enumerate(guide, start=start + 1):
        ws.write(i, 0, k, f_text)
        ws.write(i, 1, v, f_wrap)

    # Data dictionary
    ws = wb.add_worksheet("Data_Dictionary")
    widths = [14, 20, 16, 48, 48, 14, 40, 60]
    for i, w in enumerate(widths):
        ws.set_column(i, i, w)
    ws.add_table(0, 0, len(FIELDS), len(DICT_COLUMNS) - 1, {
        "columns": [{"header": c} for c in DICT_COLUMNS], "style": "Table Style Light 1"})
    for r, row in enumerate(FIELDS, start=1):
        for c, value in enumerate(row):
            ws.write(r, c, value, f_wrap)
    ws.freeze_panes(1, 0)

    # Data quality
    ws = wb.add_worksheet("Data_Quality")
    ws.set_column("A:A", 16)
    ws.set_column("B:B", 62)
    ws.set_column("C:C", 46)
    ws.set_column("D:D", 12)
    ws.set_column("E:E", 70)
    cols = ["Section", "Item", "Value", "Status", "Note"]
    ws.add_table(0, 0, len(dq_table), 4, {"columns": [{"header": c} for c in cols], "style": "Table Style Light 1"})
    for r, row in enumerate(dq_table[cols].itertuples(index=False), start=1):
        for c, value in enumerate(row):
            ws.write(r, c, value, f_wrap)
    last = len(dq_table)
    for status, colour in (("PASS", "#d9ead3"), ("WARNING", "#fce8b2"), ("FAIL", "#f4c7c3")):
        ws.conditional_format(1, 3, last, 3, {"type": "cell", "criteria": "==", "value": f'"{status}"',
                                              "format": wb.add_format({"bg_color": colour})})
    ws.freeze_panes(1, 0)

    # Analytical data (country x month), written first so other sheets can reference it
    ad = wb.add_worksheet("Analytical_Data")
    n = len(monthly)
    ad_cols = list(monthly.columns)
    ad.add_table(0, 0, n, len(ad_cols) - 1, {
        "columns": [{"header": c} for c in ad_cols], "style": "Table Style Light 1"})
    for r, row in enumerate(monthly.itertuples(index=False), start=1):
        for c, value in enumerate(row):
            ad.write(r, c, value, f_int if isinstance(value, (int, np.integer)) and c > 1 else f_text)
    ad.set_column("A:B", 11)
    ad.set_column("C:C", 9)
    ad.set_column("D:E", 28)
    ad.set_column("F:J", 16)
    ad.freeze_panes(1, 0)
    last_ad = n + 1  # last worksheet row (1-based)
    rng = lambda col: f"Analytical_Data!${col}$2:${col}${last_ad}"

    # Country summary
    ws = wb.add_worksheet("Country_Summary")
    heads = ["Rank_Cases", "Country", "Region", "Population", "Confirmed", "Deaths", "CFR_Pct",
             "Cases_Per_100K", "Deaths_Per_100K", "Peak_Daily_Cases", "Peak_Daily_Cases_Date",
             "Peak_7d_Avg_Cases", "Peak_7d_Avg_Date"]
    m = len(summary)
    ws.add_table(0, 0, m, len(heads) - 1, {"columns": [{"header": h} for h in heads], "style": "Table Style Light 1"})
    for i, row in enumerate(summary.itertuples(index=False), start=1):
        xl = i + 1
        pop, conf, deaths = row.Population, row.Confirmed, row.Deaths
        has_pop = pd.notna(pop)
        ws.write_formula(i, 0, f"=RANK(E{xl},$E$2:$E${m + 1})", f_int, int(row.Rank_Cases))
        ws.write(i, 1, row.Country, f_text)
        ws.write(i, 2, row.Region, f_text)
        if has_pop:
            ws.write_number(i, 3, float(pop), f_int)
        ws.write_number(i, 4, float(conf), f_int)
        ws.write_number(i, 5, float(deaths), f_int)
        ws.write_formula(i, 6, f'=IF(E{xl}>0,F{xl}/E{xl}*100,"")', f_pct2,
                         blank(row.CFR_Pct) if pd.isna(row.CFR_Pct) else float(row.CFR_Pct))
        ws.write_formula(i, 7, f'=IF(AND(ISNUMBER(D{xl}),D{xl}>0),E{xl}/D{xl}*100000,"")', f_dec,
                         "" if not has_pop else float(row.Cases_Per_100K))
        ws.write_formula(i, 8, f'=IF(AND(ISNUMBER(D{xl}),D{xl}>0),F{xl}/D{xl}*100000,"")', f_dec,
                         "" if not has_pop else float(row.Deaths_Per_100K))
        ws.write_number(i, 9, float(row.Peak_Daily_Cases), f_int)
        ws.write_datetime(i, 10, row.Peak_Daily_Cases_Date.to_pydatetime(), f_date)
        ws.write_number(i, 11, float(row.Peak_7d_Avg_Cases), f_int)
        ws.write_datetime(i, 12, row.Peak_7d_Avg_Date.to_pydatetime(), f_date)
    ws.set_column("A:A", 11)
    ws.set_column("B:B", 30)
    ws.set_column("C:C", 12)
    ws.set_column("D:J", 16)
    ws.set_column("K:M", 20)
    ws.freeze_panes(1, 2)
    ws.conditional_format(1, 4, m, 4, {"type": "data_bar", "bar_color": "#9db4d3", "bar_solid": True})
    ws.conditional_format(1, 6, m, 6, {"type": "2_color_scale", "min_color": "#ffffff", "max_color": "#e8a09a"})
    ws.write(m + 2, 1, "Peak columns use the reported daily series, which can include batch updates and revisions. "
                       "Rates are blank where population is not available.", f_note)

    # Monthly global
    ws = wb.add_worksheet("Monthly_Global")
    months = monthly.groupby("Year_Month").agg(Cases=("Cases", "sum"), Deaths=("Deaths", "sum"),
                                                Days=("Days_In_Data", "max")).reset_index()
    heads = ["Year_Month", "Cases", "Deaths", "Cumulative_Cases", "Cumulative_Deaths",
             "Cases_MoM_Pct", "Deaths_MoM_Pct", "Days_In_Data", "Partial_Month"]
    k = len(months)
    ws.add_table(0, 0, k, len(heads) - 1, {"columns": [{"header": h} for h in heads], "style": "Table Style Light 1"})
    cum_c = cum_d = 0
    prev = None
    for i, row in enumerate(months.itertuples(index=False), start=1):
        xl = i + 1
        cum_c += row.Cases
        cum_d += row.Deaths
        ws.write(i, 0, row.Year_Month, f_text)
        ws.write_formula(i, 1, f"=SUMIFS({rng('F')},{rng('A')},A{xl})", f_int, int(row.Cases))
        ws.write_formula(i, 2, f"=SUMIFS({rng('G')},{rng('A')},A{xl})", f_int, int(row.Deaths))
        ws.write_formula(i, 3, f"=SUM($B$2:B{xl})", f_int, int(cum_c))
        ws.write_formula(i, 4, f"=SUM($C$2:C{xl})", f_int, int(cum_d))
        if i == 1:
            ws.write(i, 5, "", f_pct)
            ws.write(i, 6, "", f_pct)
        else:
            pc, pd_ = prev
            ws.write_formula(i, 5, f'=IF(B{xl - 1}>0,B{xl}/B{xl - 1}-1,"")', f_pct, (row.Cases / pc - 1) if pc > 0 else "")
            ws.write_formula(i, 6, f'=IF(C{xl - 1}>0,C{xl}/C{xl - 1}-1,"")', f_pct, (row.Deaths / pd_ - 1) if pd_ > 0 else "")
        ws.write_formula(i, 7, f"=MAXIFS({rng('J')},{rng('A')},A{xl})", f_int, int(row.Days))
        y, mo = int(row.Year_Month[:4]), int(row.Year_Month[5:])
        dim_days = (pd.Timestamp(y, mo, 1) + pd.offsets.MonthEnd(0)).day
        ws.write_formula(i, 8,
                         f'=IF(H{xl}<DAY(EOMONTH(DATE(VALUE(LEFT(A{xl},4)),VALUE(MID(A{xl},6,2)),1),0)),"Yes","")',
                         f_text, "Yes" if row.Days < dim_days else "")
        prev = (row.Cases, row.Deaths)
    ws.set_column("A:A", 12)
    ws.set_column("B:I", 17)
    ws.freeze_panes(1, 1)
    ws.conditional_format(1, 8, k, 8, {"type": "cell", "criteria": "==", "value": '"Yes"',
                                       "format": wb.add_format({"font_color": "#999999", "italic": True})})
    chart = wb.add_chart({"type": "column"})
    chart.add_series({"name": "Cases", "categories": ["Monthly_Global", 1, 0, k, 0],
                      "values": ["Monthly_Global", 1, 1, k, 1], "fill": {"color": "#9db4d3"}})
    line = wb.add_chart({"type": "line"})
    line.add_series({"name": "Deaths (right axis)", "categories": ["Monthly_Global", 1, 0, k, 0],
                     "values": ["Monthly_Global", 1, 2, k, 2], "y2_axis": True, "line": {"color": "#a33b32", "width": 1.75}})
    chart.combine(line)
    chart.set_title({"name": "Reported cases and deaths per month, all countries", "name_font": {"size": 11}})
    chart.set_x_axis({"num_font": {"rotation": -60, "size": 8}, "interval_unit": 3})
    chart.set_y_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#e5e5e5"}}})
    line.set_y2_axis({"num_format": "#,##0"})
    chart.set_legend({"position": "bottom"})
    chart.set_size({"width": 860, "height": 340})
    ws.insert_chart("K2", chart)
    ws.write(k + 3, 0, "First month starts on the first date in the data and the last month ends on the last date; "
                       "both are partial.", f_note)

    # Pivot analysis
    ws = wb.add_worksheet("Pivot_Analysis")
    ws.set_column("A:A", 18)
    ws.set_column("B:G", 16)
    regions = sorted(monthly["Region"].dropna().unique())
    years = sorted(monthly["Year"].unique())
    year_labels = [str(y) for y in years]
    row0 = 0
    for title, col_letter, value_col in (("Reported cases by region and year", "F", "Cases"),
                                         ("Reported deaths by region and year", "G", "Deaths")):
        ws.write(row0, 0, title, f_head)
        ws.write(row0 + 1, 0, "Region", f_head)
        for j, y in enumerate(years):
            ws.write_number(row0 + 1, 1 + j, int(y), f_head)
        ws.write(row0 + 1, 1 + len(years), "Total", f_head)
        for i, region in enumerate(regions):
            r = row0 + 2 + i
            xl = r + 1
            ws.write(r, 0, region, f_text)
            for j, y in enumerate(years):
                value = int(monthly.loc[(monthly["Region"] == region) & (monthly["Year"] == y), value_col].sum())
                col_ref = chr(ord("B") + j)
                ws.write_formula(r, 1 + j, f"=SUMIFS({rng(col_letter)},{rng('E')},$A{xl},{rng('B')},{col_ref}${row0 + 2})",
                                 f_int, value)
            total = int(monthly.loc[monthly["Region"] == region, value_col].sum())
            last_col = chr(ord("B") + len(years) - 1)
            ws.write_formula(r, 1 + len(years), f"=SUM(B{xl}:{last_col}{xl})", f_int, total)
        r = row0 + 2 + len(regions)
        xl = r + 1
        ws.write(r, 0, "Total", f_bold)
        for j in range(len(years) + 1):
            col_ref = chr(ord("B") + j)
            if j < len(years):
                total = int(monthly.loc[monthly["Year"] == years[j], value_col].sum())
            else:
                total = int(monthly[value_col].sum())
            ws.write_formula(r, 1 + j, f"=SUM({col_ref}{row0 + 3}:{col_ref}{r})", f_bold_int, total)
        row0 = r + 3
    ws.write(row0, 0, f"{years[-1]} covers {findings['last_date'][:4]}-01-01 to {findings['last_date']} only; "
                      f"{years[0]} starts on {findings['first_date']}.", f_note)

    wb.worksheets_objs.sort(key=lambda s: ["Overview", "Data_Dictionary", "Data_Quality", "Country_Summary",
                                           "Monthly_Global", "Pivot_Analysis", "Analytical_Data"].index(s.name))
    wb.close()


def export_all(fact, dim_date, dim_country, summary, monthly, dq_table, findings):
    write_csvs(fact, dim_date, dim_country, dq_table)
    write_sqlite(fact, dim_date, dim_country)
    write_docs()
    write_findings(findings)
    write_charts(fact, summary, findings)
    write_excel(fact, summary, monthly, dq_table, findings)
