from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
OUTPUTS_DIR = ROOT / "outputs"
EXCEL_DIR = ROOT / "excel"

JHU_BASE = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/"
    "csse_covid_19_data/"
)
SOURCES = {
    "confirmed": JHU_BASE + "csse_covid_19_time_series/time_series_covid19_confirmed_global.csv",
    "deaths": JHU_BASE + "csse_covid_19_time_series/time_series_covid19_deaths_global.csv",
    "recovered": JHU_BASE + "csse_covid_19_time_series/time_series_covid19_recovered_global.csv",
    "lookup": JHU_BASE + "UID_ISO_FIPS_LookUp_Table.csv",
    "country_codes": "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv",
}
RAW_FILES = {
    "confirmed": "time_series_covid19_confirmed_global.csv",
    "deaths": "time_series_covid19_deaths_global.csv",
    "recovered": "time_series_covid19_recovered_global.csv",
    "lookup": "UID_ISO_FIPS_LookUp_Table.csv",
    "country_codes": "country_codes.csv",
}

# Entries in the JHU files that are not countries or territories
NON_GEOGRAPHIC = [
    "Diamond Princess",
    "MS Zaandam",
    "Summer Olympics 2020",
    "Winter Olympics 2022",
]

# JHU names that are replaced with a conventional English short name
NAME_OVERRIDES = {
    "US": "United States",
    "Burma": "Myanmar",
    "Korea, South": "South Korea",
    "Korea, North": "North Korea",
    "Taiwan*": "Taiwan",
    "Congo (Brazzaville)": "Republic of the Congo",
    "Congo (Kinshasa)": "Democratic Republic of the Congo",
    "Holy See": "Vatican City",
    "West Bank and Gaza": "Palestine",
}

# Countries that have no usable row in the ISO country-codes table
REGION_EXCEPTIONS = {
    "Kosovo": ("Europe", "Southern Europe"),
    "Antarctica": ("Antarctica", "Antarctica"),
}
