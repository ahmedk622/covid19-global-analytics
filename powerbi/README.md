# Power BI build guide

The repository contains everything the report needs except the `.pbix` file itself, which has to be created in Power BI Desktop. This guide lists every step and every visual. Positions are in pixels on a 1280 x 720 canvas.

| File | Purpose |
|---|---|
| `power_query.m` | Power Query code for the four tables |
| `measures.dax` | All measures, ready to paste |
| `theme.json` | Colours and fonts (View > Themes > Browse for themes) |

## 1. Load the data

1. File > Options > Current File > Data Load: untick **Auto date/time**.
2. Home > Transform data > Manage Parameters > New Parameter: name `DataFolder`, type Text, value = full path to `data\processed\` with a trailing backslash.
3. For each of `Fact_Covid`, `Dim_Date`, `Dim_Country`, `DQ_Checks`: New Source > Blank Query > Advanced Editor, paste the matching block from `power_query.m`, rename the query to the table name. Close & Apply.
4. View > Themes > Browse for themes > `theme.json`.
5. Page view: Canvas settings > Type = Custom, 1280 x 720, for every page.

## 2. Model

Model view relationships (both one-to-many, single direction, active):

| From (one) | To (many) |
|---|---|
| `Dim_Date[Date]` | `Fact_Covid[Date]` |
| `Dim_Country[ISO_Code]` | `Fact_Covid[ISO_Code]` |

`DQ_Checks` has no relationships.

Column settings:

| Table | Column | Setting |
|---|---|---|
| Dim_Date | table | Table tools > Mark as date table > `Date` |
| Dim_Date | `Month_Name` | Sort by column `Month_Number` |
| Dim_Date | `Weekday_Name` | Sort by column `Weekday_Number` |
| Dim_Date | all except `Date`, `Year`, `Year_Month` | Hide |
| Dim_Country | `Population` | Format whole number, summarize: Don't summarize |
| Dim_Country | `Latitude`, `Longitude`, `JHU_Name`, `ISO2_Code` | Hide (keep `Latitude`/`Longitude` only if you add a map) |
| Fact_Covid | `Date`, `ISO_Code` | Hide |
| Fact_Covid | all numeric columns | Summarize: Don't summarize (use measures) |

## 3. Measures

Home > Enter data > create an empty table named `_Measures`. Paste each measure from `measures.dax` (New measure). Then set formats:

| Measures | Format |
|---|---|
| Total Cases, Total Deaths, Total Recoveries, Daily Cases, Daily Deaths, Daily Recoveries, Population, Peak Daily Cases, Peak Daily Deaths, Cases Previous Period, Deaths Previous Period, Cases Change vs Previous Period, Revision Days, Inconsistent Records, Countries Covered | Whole number, thousands separator |
| 7-Day Average Cases, 7-Day Average Deaths, Peak 7-Day Average Cases, Peak 7-Day Average Deaths | Whole number, thousands separator |
| Cases Per 100K, Deaths Per 100K | Decimal number, 1 decimal place |
| Case Fatality Ratio, Share of Global Cases, Cases Change vs Previous Period %, Deaths Change vs Previous Period % | Percentage, 2 decimal places (1 for the change measures) |
| Latest Data Date, Selected End Date, Recoveries As-Of Date, all `Peak ... Date` measures | Date, `d mmm yyyy` |

## 4. Pages

Slicer settings used on several pages: Date slicer = `Dim_Date[Date]`, style Between. Region slicer = `Dim_Country[Region]`, style Dropdown. Country slicer = `Dim_Country[Country]`, style Dropdown, multi-select, search on.

After building pages 1 to 3: View > Sync slicers, and tick the Date, Region and Country slicers for pages 1, 2 and 3.

### Page 1: Overview

| Visual | Type | Fields | Position (x, y, w, h) | Notes |
|---|---|---|---|---|
| Title | Card | `[Title Overview]` | 24, 12, 760, 36 | Category label off, 16 pt bold |
| Subtitle | Card | `[Subtitle Overview]` | 24, 46, 1232, 22 | Category label off, 10 pt grey |
| Region | Slicer | `Dim_Country[Region]` | 24, 76, 220, 40 | Dropdown |
| Country | Slicer | `Dim_Country[Country]` | 256, 76, 260, 40 | Dropdown, multi-select |
| Date | Slicer | `Dim_Date[Date]` | 528, 76, 728, 40 | Between |
| KPI: cases | Card | `[Total Cases]` | 24, 128, 232, 84 | Label "Reported cases" |
| KPI: deaths | Card | `[Total Deaths]` | 273, 128, 232, 84 | Label "Reported deaths" |
| KPI: recoveries | Card | `[Total Recoveries]`; add `[Recoveries As-Of Date]` as a reference label | 522, 128, 232, 84 | Label "Reported recoveries (series ends 4 Aug 2021)" |
| KPI: countries | Card | `[Countries Covered]` | 771, 128, 232, 84 | Label "Countries covered" |
| KPI: latest date | Card | `[Latest Data Date]` | 1020, 128, 232, 84 | Label "Latest data date" |
| Cumulative cases | Line chart | X `Dim_Date[Date]`, Y `[Total Cases]` | 24, 228, 404, 240 | Title: "Reported cumulative cases". Line colour 1 (navy) |
| Cumulative deaths | Line chart | X `Dim_Date[Date]`, Y `[Total Deaths]` | 440, 228, 404, 240 | Title: "Reported cumulative deaths". Line colour 2 (red) |
| Daily cases | Line and clustered column chart | X `Dim_Date[Date]`, Column Y `[Daily Cases]`, Line Y `[7-Day Average Cases]` | 856, 228, 400, 240 | Title: "Daily cases and 7-day average". Columns light grey, line navy. Tooltip: report page `Tooltip - Day` |
| Top 10 by cases | Clustered bar chart | Y `Dim_Country[Country]`, X `[Total Cases]` | 24, 484, 610, 212 | Visual filter: Country, Top N = 10 by `[Total Cases]`. Data labels on, sort descending |
| Top 10 per 100K | Clustered bar chart | Y `Dim_Country[Country]`, X `[Cases Per 100K]` | 646, 484, 610, 212 | Visual filters: `Dim_Country[Population]` is greater than or equal to 1000000; Country Top N = 10 by `[Cases Per 100K]`. Title: "Top 10 by cases per 100K (population of 1 million or more)" |

A map is not included. Country names and ISO codes are clean enough to support a filled map on `Dim_Country[Country]`, but the bar charts answer the ranking question more precisely.

### Page 2: Global trends

| Visual | Type | Fields | Position | Notes |
|---|---|---|---|---|
| Title | Card | `[Title Overview]` | 24, 12, 760, 36 | Same as page 1 |
| Date | Slicer | `Dim_Date[Date]` | 24, 76, 728, 40 | Between (synced) |
| Region | Slicer | `Dim_Country[Region]` | 764, 76, 220, 40 | Dropdown (synced) |
| Country | Slicer | `Dim_Country[Country]` | 996, 76, 260, 40 | Dropdown (synced) |
| Peak cases | Card | `[Peak 7-Day Average Cases]` | 24, 128, 300, 64 | Label "Peak 7-day average, cases" |
| Peak cases date | Card | `[Peak 7-Day Average Cases Date]` | 336, 128, 300, 64 | Label "Date of that peak" |
| Peak deaths | Card | `[Peak 7-Day Average Deaths]` | 648, 128, 300, 64 | Label "Peak 7-day average, deaths" |
| Peak deaths date | Card | `[Peak 7-Day Average Deaths Date]` | 960, 128, 296, 64 | Label "Date of that peak" |
| Daily cases | Line and clustered column chart | X `Dim_Date[Date]`, Column `[Daily Cases]`, Line `[7-Day Average Cases]` | 24, 204, 1232, 164 | Title: "Daily reported cases and 7-day average". Tooltip page `Tooltip - Day` |
| Daily deaths | Line and clustered column chart | X `Dim_Date[Date]`, Column `[Daily Deaths]`, Line `[7-Day Average Deaths]` | 24, 380, 1232, 164 | Title: "Daily reported deaths and 7-day average". Line red |
| Cumulative cases | Line chart | X `Dim_Date[Date]`, Y `[Total Cases]` | 24, 556, 610, 148 | Title: "Cumulative reported cases" |
| Cumulative deaths | Line chart | X `Dim_Date[Date]`, Y `[Total Deaths]` | 646, 556, 610, 148 | Title: "Cumulative reported deaths" |

Use the date slicer to isolate a period. The peak cards recalculate for the selected period and countries, which is how peaks are located without typing dates. Single-day spikes in the deaths chart can be batch additions to a country's series; the 7-day line is the better guide to the shape of a wave.

### Page 3: Country comparison

| Visual | Type | Fields | Position | Notes |
|---|---|---|---|---|
| Title | Card | `[Title Overview]` | 24, 12, 760, 36 | |
| Date | Slicer | `Dim_Date[Date]` | 256, 76, 728, 40 | Between (synced) |
| Region | Slicer | `Dim_Country[Region]` | 996, 76, 260, 40 | Dropdown (synced) |
| Country list | Slicer | `Dim_Country[Country]` | 24, 76, 220, 400 | List, multi-select, search on (synced) |
| Context note | Text box | Text below | 24, 488, 220, 216 | 9 pt grey |
| 7-day average by country | Line chart | X `Dim_Date[Date]`, Y `[7-Day Average Cases]`, Legend `Dim_Country[Country]` | 256, 128, 500, 260 | Visual filter: Country, Top N = 10 by `[Total Cases]`. Title: "7-day average of daily cases" |
| Cases per 100K by country | Line chart | X `Dim_Date[Date]`, Y `[Cases Per 100K]`, Legend `Dim_Country[Country]` | 768, 128, 488, 260 | Same Top N filter. Title: "Cumulative cases per 100K" |
| Comparison table | Table | `Dim_Country[Country]`, `[Rank by Cases]`, `[Total Cases]`, `[Total Deaths]`, `[Case Fatality Ratio]`, `[Cases Per 100K]`, `[Deaths Per 100K]`, `[Population]` | 256, 400, 1000, 304 | Sort by `[Total Cases]` descending. Conditional formatting below |

Context note text: "Counts are cases and deaths as reported. Countries differ in testing volume, case definitions, reporting frequency and how deaths are attributed, so differences between countries are not differences in how many people were infected. Per-100K figures use one population value per country. Countries with fewer than a million people give volatile rates."

Table conditional formatting: `[Total Cases]` > Data bars (navy); `[Case Fatality Ratio]` > Background colour > Gradient (min white, max `#E8A09A`); `[Cases Per 100K]` > Data bars (grey-blue `#9DB4D3`).

### Page 4: Country detail (drill-through)

Page settings: Page information > Drill through > Cross-report off, Keep all filters on, drag `Dim_Country[Country]` into Drill through fields. Select a country on any page, right-click > Drill through > Country detail.

| Visual | Type | Fields | Position | Notes |
|---|---|---|---|---|
| Title | Card | `[Title Country Detail]` | 24, 12, 1000, 36 | Category label off |
| Date | Slicer | `Dim_Date[Date]` | 1036, 12, 220, 40 | Between, synced with other pages |
| KPI: cases | Card | `[Total Cases]` | 24, 76, 195, 84 | |
| KPI: deaths | Card | `[Total Deaths]` | 231, 76, 195, 84 | |
| KPI: recoveries | Card | `[Total Recoveries]` | 438, 76, 195, 84 | Label "Recoveries (to 4 Aug 2021)". Blank for countries that never reported them |
| KPI: CFR | Card | `[Case Fatality Ratio]` | 645, 76, 195, 84 | Label "Reported deaths / reported cases" |
| KPI: cases per 100K | Card | `[Cases Per 100K]` | 852, 76, 195, 84 | |
| KPI: deaths per 100K | Card | `[Deaths Per 100K]` | 1059, 76, 195, 84 | |
| Daily cases | Line and clustered column chart | X `Dim_Date[Date]`, Column `[Daily Cases]`, Line `[7-Day Average Cases]` | 24, 176, 610, 200 | Title: "Daily cases and 7-day average" |
| Daily deaths | Line and clustered column chart | X `Dim_Date[Date]`, Column `[Daily Deaths]`, Line `[7-Day Average Deaths]` | 646, 176, 610, 200 | Title: "Daily deaths and 7-day average" |
| Peaks | Multi-row card | `[Peak Daily Cases]`, `[Peak Daily Cases Date]`, `[Peak 7-Day Average Cases]`, `[Peak 7-Day Average Cases Date]`, `[Peak Daily Deaths]`, `[Peak Daily Deaths Date]` | 24, 388, 610, 150 | Title: "Peaks in the selected period" |
| Period change | Multi-row card | `[Daily Cases]`, `[Cases Previous Period]`, `[Cases Change vs Previous Period %]`, `[Daily Deaths]`, `[Deaths Previous Period]`, `[Deaths Change vs Previous Period %]` | 646, 388, 610, 150 | Font colour of the % fields: fx > Field value > `[Change Color]` (cases only). Title: "Selected period vs the period before" |
| Monthly table | Table | `Dim_Date[Year_Month]`, `[Daily Cases]`, `[Daily Deaths]`, `[Revision Days]` | 24, 550, 1232, 154 | Column headers: "Month", "Cases", "Deaths", "Days with a downward revision". Sort by month ascending |

For printing or PDF: File > Export > Export to PDF exports this page as laid out. Everything needed is visible without scrolling.

### Tooltip page: `Tooltip - Day`

1. Add a page named `Tooltip - Day`. Canvas settings > Type = Tooltip. Page information > Allow use as tooltip = On. Right-click the tab > Hide page.
2. Add Tooltip fields: `Dim_Date[Date]`, `Dim_Country[Country]`.
3. Visuals: a Card with `[Tooltip Title]` at the top (category label off, 11 pt bold), then a Multi-row card with `[Daily Cases]`, `[7-Day Average Cases]`, `[Daily Deaths]`, `[Total Cases]`, `[Total Deaths]`.
4. On the daily case and death charts (pages 1, 2, 4): Format > General > Tooltips > On, Type = Report page, Page = `Tooltip - Day`.

### Page 5: Data quality and methodology

| Visual | Type | Fields | Position | Notes |
|---|---|---|---|---|
| Title | Text box | "Data quality and methodology" | 24, 12, 760, 36 | 16 pt bold |
| Summary | Table | `DQ_Checks[Item]`, `DQ_Checks[Value]` | 24, 64, 820, 200 | Visual filter: `DQ_Checks[Section]` is `Summary`. Column headers off, no grid |
| Checks | Table | `DQ_Checks[Section]`, `DQ_Checks[Item]`, `DQ_Checks[Value]`, `DQ_Checks[Status]`, `DQ_Checks[Note]` | 24, 276, 820, 428 | Visual filter: `DQ_Checks[Section]` is not `Summary`. Conditional formatting on `Status`: Format style = Rules, background: text is `PASS` `#D9EAD3`; `WARNING` `#FCE8B2`; `FAIL` `#F4C7C3` |
| Methodology | Text box | Text below | 860, 64, 396, 640 | 10 pt |

`DQ_Checks` is a snapshot from the last pipeline run: rerun `python run_pipeline.py` and Refresh to update it.

Methodology text box content:

- Reported cases: cumulative confirmed cases as published by national authorities and collected by JHU CSSE. Not estimates of true infections.
- Daily values: the change in the cumulative figure from the previous day. When a country lowers its cumulative total the daily value is negative; these values are kept and flagged, not removed.
- Case fatality ratio: reported deaths divided by reported cases on the same date. It is not the probability of dying for an infected person or for the population.
- Per 100K: reported cases (or deaths) divided by population, times 100,000, using only countries that have a population value.
- Suspicious records: duplicates, impossible values and downward revisions are counted, flagged and reported on this page. No value in the source was changed.
- Recoveries: the source series ends on 4 Aug 2021, so recovery and active-case figures are not available afterwards.
- Comparing countries: testing, case definitions, reporting frequency and death attribution differ between countries and over time.

## 5. Interactions and formatting checklist

- Edit interactions (Format > Edit interactions): on pages 1 and 2, set the Top 10 bar charts to not filter the KPI cards.
- Conditional formatting: comparison table (page 3) and period-change card (page 4) as described above.
- Axis: line charts use the continuous date axis; set X-axis type = Continuous and hide the axis title.
- Number display units: leave the axis display units on Auto; set card values to None so exact totals show.
- Alt text on every visual (Format > General > Alt text).

## 6. What has and has not been verified

Verified in the build environment: every CSV loads with the column types in `power_query.m`; keys are unique in the dimensions and complete in the fact table; the date table is continuous; the SQL and Excel calculations that mirror these measures (totals, CFR, per-100K, rankings) were run and checked against pandas.

Not verified: the `.pbix` was not built, and the DAX and `theme.json` were not run in Power BI Desktop because it is not available in the build environment. If Power BI rejects a measure or the theme, the corresponding SQL query in `sql/analysis.sql` shows the intended logic.
