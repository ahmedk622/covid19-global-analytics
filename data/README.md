# Data

| Folder / file | Contents | In Git |
|---|---|---|
| `raw/` | Files downloaded by `src/ingest.py` | CSVs ignored; `manifest.json` kept |
| `raw/manifest.json` | URL, access date, size and SHA-256 of each raw file | yes |
| `processed/Fact_Covid.csv` | One row per country and date | yes |
| `processed/Dim_Date.csv` | Continuous calendar | yes |
| `processed/Dim_Country.csv` | Country attributes and population | yes |
| `processed/DQ_Checks.csv` | Pipeline validation results, for the Power BI quality page | yes |

## Source

Johns Hopkins University Center for Systems Science and Engineering (JHU CSSE), COVID-19 Data Repository, global time series (confirmed, deaths, recovered) and UID/ISO lookup table. https://github.com/CSSEGISandData/COVID-19. Values are reported counts. The archive covers 2020-01-22 to 2023-03-09.

Region names come from https://github.com/datasets/country-codes.

Field definitions: `docs/data_dictionary.md`. To rebuild everything from scratch: delete `data/raw/*.csv` and run `python run_pipeline.py`.
