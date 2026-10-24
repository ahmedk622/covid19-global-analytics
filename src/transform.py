import numpy as np
import pandas as pd

FACT_COLUMNS = [
    "Date", "ISO_Code", "Confirmed", "Deaths", "Recovered", "Active",
    "Daily_Cases", "Daily_Deaths", "Daily_Recoveries",
    "Revision_Flag", "Inconsistency_Flag",
]
MIN_POPULATION_FOR_RANKING = 1_000_000


def build_fact(data):
    df = data.sort_values(["ISO_Code", "Date"]).reset_index(drop=True)
    by_country = df.groupby("ISO_Code")

    # first record of each series is treated as a change from zero, so daily values sum to the cumulative total
    df["Daily_Cases"] = by_country["Confirmed"].diff().fillna(df["Confirmed"]).astype("int64")
    df["Daily_Deaths"] = by_country["Deaths"].diff().fillna(df["Deaths"]).astype("int64")

    recovered = df["Recovered"].astype("float64")
    daily_recovered = recovered.groupby(df["ISO_Code"]).diff()
    daily_recovered = daily_recovered.fillna(recovered)
    df["Daily_Recoveries"] = daily_recovered.astype("Int64")

    active = df["Confirmed"] - df["Deaths"] - recovered
    df["Active"] = active.where(active >= 0).astype("Int64")

    df["Revision_Flag"] = (
        (df["Daily_Cases"] < 0) | (df["Daily_Deaths"] < 0) | (daily_recovered < 0)
    ).astype("int64")
    df["Inconsistency_Flag"] = (
        (df["Deaths"] + recovered.fillna(0) > df["Confirmed"]) | (recovered < 0)
    ).astype("int64")
    df["Recovered"] = df["Recovered"].astype("Int64")
    return df[FACT_COLUMNS]


def build_dim_date(fact):
    dates = pd.date_range(fact["Date"].min(), fact["Date"].max(), freq="D")
    dim = pd.DataFrame({"Date": dates})
    dim["Year"] = dim["Date"].dt.year
    dim["Quarter"] = dim["Date"].dt.quarter
    dim["Year_Quarter"] = dim["Year"].astype(str) + "-Q" + dim["Quarter"].astype(str)
    dim["Month_Number"] = dim["Date"].dt.month
    dim["Month_Name"] = dim["Date"].dt.strftime("%B")
    dim["Year_Month"] = dim["Date"].dt.strftime("%Y-%m")
    dim["Week_Start"] = dim["Date"] - pd.to_timedelta(dim["Date"].dt.weekday, unit="D")
    dim["Weekday_Number"] = dim["Date"].dt.weekday + 1
    dim["Weekday_Name"] = dim["Date"].dt.strftime("%A")
    dim["Is_Weekend"] = (dim["Weekday_Number"] >= 6).astype("int64")
    return dim


def build_dim_country(country_map):
    cols = ["ISO_Code", "Country", "JHU_Name", "ISO2_Code", "Region", "Sub_Region",
            "Population", "Latitude", "Longitude"]
    dim = country_map[cols].sort_values("Country").reset_index(drop=True)
    dim["Population"] = dim["Population"].round().astype("Int64")
    return dim


def add_rolling(fact):
    out = fact[["Date", "ISO_Code", "Daily_Cases", "Daily_Deaths"]].copy()
    grouped = out.groupby("ISO_Code")
    out["Cases_7d"] = grouped["Daily_Cases"].transform(lambda s: s.rolling(7).mean())
    out["Deaths_7d"] = grouped["Daily_Deaths"].transform(lambda s: s.rolling(7).mean())
    return out


def country_summary(fact, dim_country):
    latest = fact[fact["Date"] == fact["Date"].max()].set_index("ISO_Code")
    rolling = add_rolling(fact)

    summary = dim_country[["ISO_Code", "Country", "Region", "Population"]].set_index("ISO_Code")
    summary["Confirmed"] = latest["Confirmed"]
    summary["Deaths"] = latest["Deaths"]
    summary["CFR_Pct"] = (summary["Deaths"] / summary["Confirmed"].where(summary["Confirmed"] > 0) * 100)
    pop = summary["Population"].astype("float64")
    summary["Cases_Per_100K"] = summary["Confirmed"] / pop * 100_000
    summary["Deaths_Per_100K"] = summary["Deaths"] / pop * 100_000

    peak_cases = fact.loc[fact.groupby("ISO_Code")["Daily_Cases"].idxmax()].set_index("ISO_Code")
    summary["Peak_Daily_Cases"] = peak_cases["Daily_Cases"]
    summary["Peak_Daily_Cases_Date"] = peak_cases["Date"]
    peak_avg = rolling.loc[rolling.groupby("ISO_Code")["Cases_7d"].idxmax()].set_index("ISO_Code")
    summary["Peak_7d_Avg_Cases"] = peak_avg["Cases_7d"]
    summary["Peak_7d_Avg_Date"] = peak_avg["Date"]
    peak_deaths = fact.loc[fact.groupby("ISO_Code")["Daily_Deaths"].idxmax()].set_index("ISO_Code")
    summary["Peak_Daily_Deaths"] = peak_deaths["Daily_Deaths"]
    summary["Revision_Days"] = fact.groupby("ISO_Code")["Revision_Flag"].sum()
    summary = summary.reset_index().sort_values("Confirmed", ascending=False)
    summary["Rank_Cases"] = summary["Confirmed"].rank(ascending=False, method="min").astype(int)
    summary["Rank_Deaths"] = summary["Deaths"].rank(ascending=False, method="min").astype(int)
    return summary.reset_index(drop=True)


def monthly_table(fact, dim_country):
    df = fact.assign(Year_Month=fact["Date"].dt.strftime("%Y-%m"))
    monthly = df.groupby(["ISO_Code", "Year_Month"]).agg(
        Cases=("Daily_Cases", "sum"),
        Deaths=("Daily_Deaths", "sum"),
        Cumulative_Cases=("Confirmed", "last"),
        Cumulative_Deaths=("Deaths", "last"),
        Days_In_Data=("Date", "count"),
    ).reset_index()
    monthly["Year"] = monthly["Year_Month"].str[:4].astype(int)
    names = dim_country[["ISO_Code", "Country", "Region"]]
    monthly = monthly.merge(names, on="ISO_Code", how="left")
    cols = ["Year_Month", "Year", "ISO_Code", "Country", "Region", "Cases", "Deaths",
            "Cumulative_Cases", "Cumulative_Deaths", "Days_In_Data"]
    return monthly[cols].sort_values(["Year_Month", "Country"]).reset_index(drop=True)


def top_peaks(series, n=3, gap_days=120):
    remaining = series.dropna().copy()
    peaks = []
    while len(peaks) < n and remaining.notna().any():
        day = remaining.idxmax()
        peaks.append((day, float(remaining[day])))
        window = (remaining.index > day - pd.Timedelta(days=gap_days)) & (
            remaining.index < day + pd.Timedelta(days=gap_days)
        )
        remaining[window] = np.nan
    return sorted(peaks)


def compute_findings(fact, dim_country, summary, clean_log):
    last_date = fact["Date"].max()
    latest = fact[fact["Date"] == last_date]
    total_cases = int(latest["Confirmed"].sum())
    total_deaths = int(latest["Deaths"].sum())

    def top(col, n=5, ranked=summary):
        rows = ranked.nlargest(n, col)
        return [
            {"country": r.Country, "value": float(getattr(r, col)),
             "share_of_total": None} for r in rows.itertuples()
        ]

    findings = {
        "first_date": fact["Date"].min().date().isoformat(),
        "last_date": last_date.date().isoformat(),
        "countries": int(fact["ISO_Code"].nunique()),
        "total_cases": total_cases,
        "total_deaths": total_deaths,
        "global_cfr_pct": total_deaths / total_cases * 100,
    }

    for key, col, total in (("top_cases", "Confirmed", total_cases), ("top_deaths", "Deaths", total_deaths)):
        rows = top(col)
        for row in rows:
            row["share_of_total"] = row["value"] / total * 100
        findings[key] = rows

    ranked = summary[summary["Population"].astype("float64") >= MIN_POPULATION_FOR_RANKING]
    findings["ranking_population_floor"] = MIN_POPULATION_FOR_RANKING
    findings["ranking_countries"] = int(len(ranked))
    findings["top_cases_per_100k"] = top("Cases_Per_100K", ranked=ranked)
    findings["top_deaths_per_100k"] = top("Deaths_Per_100K", ranked=ranked)
    findings["population_covered_countries"] = int(summary["Population"].notna().sum())

    iso_names = dim_country.set_index("ISO_Code")["Country"]
    for key, col in (("max_daily_cases", "Daily_Cases"), ("max_daily_deaths", "Daily_Deaths")):
        row = fact.loc[fact[col].idxmax()]
        near = fact[(fact["ISO_Code"] == row["ISO_Code"])
                    & (fact["Date"].sub(row["Date"]).abs().between(pd.Timedelta(days=1), pd.Timedelta(days=3)))]
        findings[key] = {"country": iso_names[row["ISO_Code"]], "date": row["Date"].date().isoformat(),
                         "value": int(row[col]), "neighbour_max": int(near[col].max())}

    daily = fact.groupby("Date")[["Daily_Cases", "Daily_Deaths"]].sum()
    avg = daily.rolling(7).mean()
    findings["global_peaks_cases"] = [
        {"date": d.date().isoformat(), "avg_7d": v} for d, v in top_peaks(avg["Daily_Cases"])
    ]
    findings["global_peaks_deaths"] = [
        {"date": d.date().isoformat(), "avg_7d": v} for d, v in top_peaks(avg["Daily_Deaths"])
    ]

    by_year = fact.assign(Year=fact["Date"].dt.year).groupby("Year")[["Daily_Cases", "Daily_Deaths"]].sum()
    findings["by_year"] = [
        {"year": int(y), "cases": int(r.Daily_Cases), "deaths": int(r.Daily_Deaths),
         "cases_share": r.Daily_Cases / total_cases * 100, "deaths_share": r.Daily_Deaths / total_deaths * 100,
         "days": int((fact.loc[fact["Date"].dt.year == y, "Date"].nunique()))}
        for y, r in by_year.iterrows()
    ]

    rec_day = clean_log["recovered_last_date"]
    rec = fact[fact["Date"] == rec_day]
    findings["recovered"] = {
        "last_date": rec_day.date().isoformat(),
        "total": int(rec["Recovered"].sum()),
        "countries_reporting": int(rec["Recovered"].notna().sum()),
        "countries_with_series": int(fact.loc[fact["Recovered"].notna(), "ISO_Code"].nunique()),
    }

    neg = fact[fact["Daily_Cases"] < 0]
    worst = fact.loc[fact["Daily_Cases"].idxmin()]
    findings["revisions"] = {
        "negative_daily_cases_records": int(len(neg)),
        "negative_daily_cases_countries": int(neg["ISO_Code"].nunique()),
        "negative_daily_deaths_records": int((fact["Daily_Deaths"] < 0).sum()),
        "largest_negative_cases": {"country": iso_names[worst["ISO_Code"]],
                                   "date": worst["Date"].date().isoformat(),
                                   "value": int(worst["Daily_Cases"])},
    }
    return findings
