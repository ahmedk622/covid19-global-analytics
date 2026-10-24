# Methodology

## Source selection

The JHU CSSE COVID-19 repository was kept as the single source of case, death and recovery figures. It was chosen over live APIs because JHU stopped collecting global data on 2023-03-10 (stated in the repository README), so the time series ends on 2023-03-09 and no longer changes, and the pipeline gives the same result every time it runs. It has one row per country or province and one column per day, with a stable layout, and it comes with a lookup table (ISO codes, population) published alongside the data. Values are **reported** counts, not estimates.

Reference tables:

| Table | Used for | Location |
|---|---|---|
| JHU `UID_ISO_FIPS_LookUp_Table.csv` | ISO codes, population, latitude/longitude | same JHU repository |
| `datasets/country-codes` | UN region and sub-region by ISO code | https://github.com/datasets/country-codes |

Download dates, URLs, sizes and SHA-256 hashes are recorded in `data/raw/manifest.json`.

No second COVID source was added. A second source would have different country coverage, definitions and revision histories, and since this archive is frozen it would not have corrected anything. The pipeline instead compares totals before and after processing (below). The statement used in the reports: *Single-source validation was used because the selected dataset provided the required historical coverage and multi-source reconciliation was not necessary for this implementation.*

## Pipeline

```
ingest -> clean -> transform -> validate -> export
```

`python run_pipeline.py` runs all stages in order. There is no separate reconcile stage for the reason above.

1. **Ingest** (`src/ingest.py`): downloads the five raw files into `data/raw/` and writes the manifest. Existing files are not downloaded again unless `--refresh` is passed.
2. **Clean** (`src/clean.py`):
   - trims names, parses the `m/d/yy` column headers, forces numeric values and counts anything that fails;
   - sums province-level rows into countries (91 rows for 8 countries);
   - excludes four entries that are not countries (Diamond Princess, MS Zaandam, Summer Olympics 2020, Winter Olympics 2022) and records their totals in the data quality report;
   - maps each JHU country name to an ISO alpha-3 code using the JHU lookup table, and to a region using the country-codes table;
   - blanks recovery values that the source no longer maintains (see Recoveries).
3. **Transform** (`src/transform.py`): builds `Fact_Covid`, `Dim_Date`, `Dim_Country`, the country summary and monthly tables, and the key findings.
4. **Validate** (`src/validate.py`): runs the checks and writes `reports/data_quality_report.md` and `data/processed/DQ_Checks.csv`. A FAIL stops the pipeline before export.
5. **Export** (`src/export.py`): writes CSVs, the SQLite database, the Excel workbook, charts, `docs/data_dictionary.md` and `reports/key_findings.md`.

## Country standardisation

The JHU name is the starting point because it matches the case files exactly. ISO alpha-3 codes come from the JHU lookup table and are the join key everywhere. Nine display names are replaced with conventional English names (for example `US` becomes United States, `Burma` becomes Myanmar, `Taiwan*` becomes Taiwan); the original name stays in `Dim_Country[JHU_Name]`. Kosovo uses JHU's code `XKS`, which is not an official ISO code. Kosovo and Antarctica are not in the country-codes region fields, so their region is set explicitly.

## Cleaning decisions

- **Nothing is deleted or edited to make numbers look better.** Problems are counted and flagged.
- **Downward revisions.** If a country's cumulative total falls, the daily value is negative. These are kept so that daily values add up to the cumulative total, and `Revision_Flag = 1` marks the day. The source does not say which earlier days a correction belongs to, so redistributing it would be a guess.
- **Impossible combinations.** Deaths above confirmed cases, or deaths plus recoveries above confirmed cases, set `Inconsistency_Flag = 1`. Values stay as reported. Of 302 records with deaths above confirmed cases, 300 are North Korea (6 reported deaths against at most 1 confirmed case).
- **Active cases** are only calculated where recoveries exist and the result is not negative; otherwise they are blank.

## Recoveries

The recovery series stops being maintained on 2021-08-04: the global total falls to zero on the next date. Values after that date are therefore treated as not available (blank), not as zero. Eight countries never reported recoveries and are blank for the whole period. Because recoveries are incomplete, `Active` and `Daily_Recoveries` are blank in the same places. The dashboard shows recoveries as of the last date that has data.

## Derived metrics

| Metric | Definition | Where |
|---|---|---|
| Daily cases / deaths | Cumulative on the date minus cumulative on the previous date; on the first date, the cumulative value itself | Fact table |
| 7-day average | Mean of the daily value over the last 7 days, shown only once 7 days exist | DAX; Python for peaks |
| Case fatality ratio | Reported deaths / reported cases on the same date | DAX, SQL, Excel |
| Cases (deaths) per 100K | Reported cases (deaths) / population x 100,000 | DAX, SQL, Excel |
| Peaks | Maximum daily value, and maximum of the 7-day average, found by calculation | DAX, Python |
| Period-over-period change | Selected period vs the same number of days immediately before it | DAX |

Rates and rolling averages are not stored in the fact table because they depend on the slicer selection and are not additive.

## Population normalisation

Population comes from the JHU lookup table: one value per country, with no reference year stated in the file. For countries made of several JHU rows (France, United Kingdom, Netherlands, Denmark, China, Australia, Canada, New Zealand), the populations of the rows whose cases are summed are added together, so overseas territories counted in the cases are also counted in the population. Province rows with no population value (the Canadian cruise-ship and repatriated-traveller rows, China's "Unknown" row) are counted in cases only; their case counts are small. Antarctica has no population and is left out of all rates. In ranking findings, only countries with at least 1,000,000 people are ranked, since very small populations produce unstable rates.

## Power BI model

Star schema: `Dim_Date` and `Dim_Country` each have a one-to-many, single-direction relationship to `Fact_Covid`. The date table is continuous (1,143 days) and is marked as the date table. Cumulative measures take the value on the last date in the filter; daily measures add up. Details are in `powerbi/README.md`.

## Limitations

- Counts are what countries reported. Testing volume, case definitions and how deaths are attributed differ between countries and changed over time.
- Many countries moved to weekly or irregular reporting in 2022 to 2023, so daily values are lumpy and single days can contain backlog (for example, China's reported deaths on 2023-01-15).
- Countries revised their series retrospectively; the archive keeps the final cumulative figures, not what was known on each day.
- Reporting delays mean a day's value is not necessarily the day's events.
- Under-reporting is likely in many places and cannot be measured from this data.
- Population is a single figure, not a yearly series.
- The last month in the data (March 2023) has 9 days, and the first (January 2020) starts on the 22nd.
- Recoveries are unusable after 2021-08-04.

## Reproducibility

```
python -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_pipeline.py
```

All paths are relative to the repository root. For the archived data, the numbers are the same on every run; only the run date in the data quality report and the access dates in the manifest change.
