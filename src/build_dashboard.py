import json

import numpy as np
import pandas as pd

from config import RAW_DIR, ROOT
from validate import DATASET_NAME, SOURCE_URL

DASHBOARD_DIR = ROOT / "dashboard"
RANKING_POPULATION_FLOOR = 1_000_000


def clean_numbers(values):
    return [None if pd.isna(v) else int(v) for v in values]


def build_payload(fact, dim_country, dq_table):
    fact = fact.sort_values(["ISO_Code", "Date"])
    dates = pd.date_range(fact["Date"].min(), fact["Date"].max(), freq="D")
    per_country = fact.groupby("ISO_Code")
    if not (per_country.size() == len(dates)).all():
        raise ValueError("every country must have one row for every date")

    series = {}
    for iso, rows in per_country:
        series[iso] = {
            "c": rows["Daily_Cases"].astype(int).tolist(),
            "d": rows["Daily_Deaths"].astype(int).tolist(),
            "r": clean_numbers(rows["Recovered"]),
            "rev": np.flatnonzero(rows["Revision_Flag"].to_numpy()).tolist(),
            "inc": np.flatnonzero(rows["Inconsistency_Flag"].to_numpy()).tolist(),
        }

    countries = [
        {
            "iso": r.ISO_Code, "name": r.Country, "jhu": r.JHU_Name, "iso2": r.ISO2_Code,
            "region": r.Region, "sub": r.Sub_Region,
            "pop": None if pd.isna(r.Population) else int(r.Population),
        }
        for r in dim_country.sort_values("Country").itertuples()
    ]
    manifest = json.loads((RAW_DIR / "manifest.json").read_text())
    confirmed = manifest["time_series_covid19_confirmed_global.csv"]
    run_date = dq_table.loc[dq_table["Item"] == "Pipeline run date", "Value"].iloc[0]
    last_recovered = fact.loc[fact["Recovered"].notna(), "Date"].max()

    return {
        "meta": {
            "first": dates[0].strftime("%Y-%m-%d"),
            "last": dates[-1].strftime("%Y-%m-%d"),
            "days": len(dates),
            "dataset": DATASET_NAME,
            "sourceUrl": SOURCE_URL,
            "sourceCommit": confirmed["commit"],
            "sourceAccessed": confirmed["accessed"],
            "pipelineRun": run_date,
            "recoveryLastDate": last_recovered.strftime("%Y-%m-%d"),
            "rankingPopulationFloor": RANKING_POPULATION_FLOOR,
            "factRows": int(len(fact)),
        },
        "regions": sorted(dim_country["Region"].dropna().unique().tolist()),
        "countries": countries,
        "series": series,
        "dq": dq_table[["Section", "Item", "Value", "Status", "Note"]].fillna("").to_dict("records"),
    }


def write_dashboard_data(fact, dim_country, dq_table):
    DASHBOARD_DIR.mkdir(exist_ok=True)
    payload = build_payload(fact, dim_country, dq_table)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    (DASHBOARD_DIR / "data.js").write_text(f"window.COVID_DATA={text};\n", encoding="utf-8")
