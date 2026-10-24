import numpy as np
import pandas as pd

from config import (
    NAME_OVERRIDES,
    NON_GEOGRAPHIC,
    RAW_DIR,
    RAW_FILES,
    REGION_EXCEPTIONS,
)

ID_COLS = ["Province/State", "Country/Region", "Lat", "Long"]


def read_wide(key, log):
    df = pd.read_csv(RAW_DIR / RAW_FILES[key], keep_default_na=False, na_values=[""])
    for col in ("Province/State", "Country/Region"):
        stripped = df[col].str.strip()
        log["names_trimmed"] += int((df[col].notna() & (df[col] != stripped)).sum())
        df[col] = stripped
    date_cols = [c for c in df.columns if c not in ID_COLS]
    dates = pd.to_datetime(date_cols, format="%m/%d/%y", errors="coerce")
    log["malformed_date_columns"] += int(dates.isna().sum())

    raw_values = df[date_cols]
    values = raw_values.apply(pd.to_numeric, errors="coerce")
    log["non_numeric_cells"] += int((values.isna() & raw_values.notna()).sum().sum())
    log["null_cells_raw"] += int(raw_values.isna().sum().sum())
    df[date_cols] = values

    log["raw_rows"][key] = len(df)
    log["duplicate_raw_rows"] += int(df.duplicated().sum())
    log["duplicate_raw_keys"] += int(df.duplicated(["Province/State", "Country/Region"]).sum())
    return df, date_cols, dates


def aggregate_to_country(df, date_cols, key, log):
    log["province_rows"][key] = int(df["Province/State"].notna().sum())
    return df.groupby("Country/Region")[date_cols].sum(min_count=1)


def build_country_map(conf_raw, log):
    lookup = pd.read_csv(RAW_DIR / RAW_FILES["lookup"], keep_default_na=False, na_values=[""])
    codes = pd.read_csv(RAW_DIR / RAW_FILES["country_codes"], keep_default_na=False)
    admin0 = lookup[lookup["Admin2"].isna()]

    country_rows = admin0[admin0["Province_State"].isna()].drop_duplicates("Country_Region")
    country_rows = country_rows.set_index("Country_Region")

    # population is summed over the same JHU rows whose cases are summed
    keys = conf_raw[["Province/State", "Country/Region"]].rename(
        columns={"Province/State": "Province_State", "Country/Region": "Country_Region"}
    )
    matched = keys.merge(
        admin0[["Province_State", "Country_Region", "Population"]].drop_duplicates(
            ["Province_State", "Country_Region"]
        ),
        on=["Province_State", "Country_Region"],
        how="left",
    )
    log["rows_without_population"] = matched.loc[
        matched["Population"].isna(), ["Province_State", "Country_Region"]
    ].fillna("").values.tolist()
    population = matched.groupby("Country_Region")["Population"].sum(min_count=1)

    mapping = pd.DataFrame({"JHU_Name": sorted(conf_raw["Country/Region"].unique())})
    mapping = mapping[~mapping["JHU_Name"].isin(NON_GEOGRAPHIC)]
    mapping["ISO_Code"] = mapping["JHU_Name"].map(country_rows["iso3"])
    mapping["ISO2_Code"] = mapping["JHU_Name"].map(country_rows["iso2"])
    mapping["Latitude"] = mapping["JHU_Name"].map(country_rows["Lat"])
    mapping["Longitude"] = mapping["JHU_Name"].map(country_rows["Long_"])
    mapping["Population"] = mapping["JHU_Name"].map(population)

    codes = codes.set_index("ISO3166-1-Alpha-3")
    mapping["Region"] = mapping["ISO_Code"].map(codes["Region Name"])
    mapping["Sub_Region"] = mapping["ISO_Code"].map(codes["Sub-region Name"])

    for jhu_name, (region, sub_region) in REGION_EXCEPTIONS.items():
        row = mapping["JHU_Name"] == jhu_name
        mapping.loc[row, ["Region", "Sub_Region"]] = [region, sub_region]
    mapping["Country"] = mapping["JHU_Name"].map(NAME_OVERRIDES).fillna(mapping["JHU_Name"])
    for col in ("Region", "Sub_Region"):
        mapping[col] = mapping[col].replace("", np.nan)

    log["region_exceptions"] = list(REGION_EXCEPTIONS)
    log["name_overrides"] = list(NAME_OVERRIDES)
    log["names_changed"] = int((mapping["Country"] != mapping["JHU_Name"]).sum())
    return mapping.reset_index(drop=True)


def to_long(wide, dates, value_name):
    wide = wide.copy()
    wide.columns = dates
    long = wide.rename_axis(columns="Date").reset_index().melt(
        id_vars="Country/Region", var_name="Date", value_name=value_name
    )
    long["Date"] = pd.to_datetime(long["Date"])
    return long.rename(columns={"Country/Region": "JHU_Name"})


def clean():
    log = {
        "raw_rows": {},
        "province_rows": {},
        "names_trimmed": 0,
        "malformed_date_columns": 0,
        "non_numeric_cells": 0,
        "null_cells_raw": 0,
        "duplicate_raw_rows": 0,
        "duplicate_raw_keys": 0,
    }
    frames, dates_by_file, wide_by_key = {}, {}, {}
    for key in ("confirmed", "deaths", "recovered"):
        raw, date_cols, dates = read_wide(key, log)
        frames[key] = raw
        dates_by_file[key] = list(date_cols)
        wide_by_key[key] = (aggregate_to_country(raw, date_cols, key, log), dates)

    log["date_columns_match"] = (
        dates_by_file["confirmed"] == dates_by_file["deaths"] == dates_by_file["recovered"]
    )
    log["raw_date_columns"] = len(dates_by_file["confirmed"])

    conf_wide = wide_by_key["confirmed"][0]
    log["excluded_entities"] = [
        {
            "name": name,
            "max_confirmed": int(conf_wide.loc[name].max()),
            "max_deaths": int(wide_by_key["deaths"][0].loc[name].max()),
        }
        for name in NON_GEOGRAPHIC
        if name in conf_wide.index
    ]
    log["countries_in_raw"] = int(conf_wide.shape[0])
    log["countries_with_provinces"] = int(frames["confirmed"].loc[
        frames["confirmed"]["Province/State"].notna(), "Country/Region"].nunique())

    # raw country totals per date (before excluding non-geographic entries)
    keep = [n for n in conf_wide.index if n not in NON_GEOGRAPHIC]
    log["control_raw"] = {
        key: wide_by_key[key][0].loc[[n for n in wide_by_key[key][0].index if n in keep]].sum().values
        for key in ("confirmed", "deaths")
    }

    country_map = build_country_map(frames["confirmed"], log)

    long = {}
    for key, col in (("confirmed", "Confirmed"), ("deaths", "Deaths"), ("recovered", "Recovered")):
        wide, dates = wide_by_key[key]
        wide = wide.loc[[n for n in wide.index if n not in NON_GEOGRAPHIC]]
        long[key] = to_long(wide, dates, col)

    data = long["confirmed"].merge(long["deaths"], on=["JHU_Name", "Date"], how="outer")
    data = data.merge(long["recovered"], on=["JHU_Name", "Date"], how="outer")
    data = data.merge(country_map[["JHU_Name", "ISO_Code"]], on="JHU_Name", how="left")

    # recoveries: the source stopped updating the series; treat later values as not available
    recovered_total = data.groupby("Date")["Recovered"].sum()
    last_reported = recovered_total[recovered_total > 0].index.max()
    never_reported = data.groupby("JHU_Name")["Recovered"].max()
    never_reported = never_reported[never_reported == 0].index.tolist()
    data.loc[data["Date"] > last_reported, "Recovered"] = np.nan
    data.loc[data["JHU_Name"].isin(never_reported), "Recovered"] = np.nan
    log["recovered_last_date"] = last_reported
    log["recovered_never_reported"] = sorted(never_reported)

    for col in ("Confirmed", "Deaths"):
        data[col] = data[col].astype("int64")
    data["Recovered"] = data["Recovered"].astype("Int64")

    cols = ["Date", "ISO_Code", "JHU_Name", "Confirmed", "Deaths", "Recovered"]
    data = data[cols].sort_values(["ISO_Code", "Date"]).reset_index(drop=True)
    return data, country_map, log
