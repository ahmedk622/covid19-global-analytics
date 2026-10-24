-- Queries for outputs/covid.db (SQLite), built by run_pipeline.py from the Fact_Covid, Dim_Date
-- and Dim_Country tables. Dates are stored as YYYY-MM-DD text.

-- Q1. Country ranking by cumulative reported cases at the latest date, with CFR and rates per 100K
SELECT
    RANK() OVER (ORDER BY f.Confirmed DESC)                       AS rank_cases,
    c.Country,
    c.Region,
    f.Confirmed                                                   AS total_cases,
    f.Deaths                                                      AS total_deaths,
    ROUND(100.0 * f.Deaths / NULLIF(f.Confirmed, 0), 2)           AS cfr_pct,
    ROUND(100000.0 * f.Confirmed / c.Population, 0)               AS cases_per_100k,
    ROUND(100000.0 * f.Deaths / c.Population, 1)                  AS deaths_per_100k
FROM Fact_Covid f
JOIN Dim_Country c ON c.ISO_Code = f.ISO_Code
WHERE f.Date = (SELECT MAX(Date) FROM Fact_Covid)
ORDER BY total_cases DESC
LIMIT 20;

-- Q2. Monthly global cases and deaths with month-over-month change (first and last months are partial)
WITH monthly AS (
    SELECT
        d.Year_Month,
        SUM(f.Daily_Cases)  AS cases,
        SUM(f.Daily_Deaths) AS deaths,
        COUNT(DISTINCT f.Date) AS days_in_data
    FROM Fact_Covid f
    JOIN Dim_Date d ON d.Date = f.Date
    GROUP BY d.Year_Month
)
SELECT
    Year_Month,
    cases,
    deaths,
    days_in_data,
    ROUND(100.0 * (cases - LAG(cases) OVER (ORDER BY Year_Month)) / NULLIF(LAG(cases) OVER (ORDER BY Year_Month), 0), 1)
        AS cases_mom_pct,
    ROUND(100.0 * (deaths - LAG(deaths) OVER (ORDER BY Year_Month)) / NULLIF(LAG(deaths) OVER (ORDER BY Year_Month), 0), 1)
        AS deaths_mom_pct
FROM monthly
ORDER BY Year_Month;

-- Q3. Peak single-day cases per country (top 15). Single days can include batch reporting.
WITH ranked AS (
    SELECT
        ISO_Code,
        Date,
        Daily_Cases,
        ROW_NUMBER() OVER (PARTITION BY ISO_Code ORDER BY Daily_Cases DESC, Date) AS rn
    FROM Fact_Covid
)
SELECT c.Country, r.Date AS peak_date, r.Daily_Cases AS peak_daily_cases
FROM ranked r
JOIN Dim_Country c ON c.ISO_Code = r.ISO_Code
WHERE r.rn = 1
ORDER BY r.Daily_Cases DESC
LIMIT 15;

-- Q4. Countries with the highest case fatality ratio (reported deaths / reported cases),
--     limited to countries with at least 100,000 reported cases
SELECT
    c.Country,
    f.Confirmed AS total_cases,
    f.Deaths    AS total_deaths,
    ROUND(100.0 * f.Deaths / f.Confirmed, 2) AS cfr_pct
FROM Fact_Covid f
JOIN Dim_Country c ON c.ISO_Code = f.ISO_Code
WHERE f.Date = (SELECT MAX(Date) FROM Fact_Covid)
  AND f.Confirmed >= 100000
ORDER BY cfr_pct DESC
LIMIT 15;

-- Q5. Population-normalised comparison by region (countries with a population value only,
--     so numerator and denominator cover the same countries)
SELECT
    c.Region,
    COUNT(*)                                              AS countries,
    SUM(f.Confirmed)                                      AS total_cases,
    SUM(c.Population)                                     AS population,
    ROUND(100000.0 * SUM(f.Confirmed) / SUM(c.Population), 0) AS cases_per_100k,
    ROUND(100000.0 * SUM(f.Deaths) / SUM(c.Population), 1)    AS deaths_per_100k
FROM Fact_Covid f
JOIN Dim_Country c ON c.ISO_Code = f.ISO_Code
WHERE f.Date = (SELECT MAX(Date) FROM Fact_Covid)
  AND c.Population IS NOT NULL
GROUP BY c.Region
ORDER BY cases_per_100k DESC;

-- Q6. 7-day rolling average of daily cases for one country (change the ISO code as needed)
SELECT
    Date,
    Daily_Cases,
    ROUND(AVG(Daily_Cases) OVER (ORDER BY Date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS cases_7d_avg,
    ROW_NUMBER() OVER (ORDER BY Date) AS day_number
FROM Fact_Covid
WHERE ISO_Code = 'IND'
ORDER BY Date;

-- Q7. Reported cases and deaths by region and calendar year, with the share of each region's total
WITH yearly AS (
    SELECT
        c.Region,
        d.Year,
        SUM(f.Daily_Cases)  AS cases,
        SUM(f.Daily_Deaths) AS deaths
    FROM Fact_Covid f
    JOIN Dim_Country c ON c.ISO_Code = f.ISO_Code
    JOIN Dim_Date d ON d.Date = f.Date
    GROUP BY c.Region, d.Year
)
SELECT
    Region,
    Year,
    cases,
    deaths,
    ROUND(100.0 * cases / SUM(cases) OVER (PARTITION BY Region), 1) AS pct_of_region_cases
FROM yearly
ORDER BY Region, Year;

-- Q8. Largest downward revisions of reported cases (negative daily values)
SELECT c.Country, f.Date, f.Daily_Cases AS revision
FROM Fact_Covid f
JOIN Dim_Country c ON c.ISO_Code = f.ISO_Code
WHERE f.Daily_Cases < 0
ORDER BY f.Daily_Cases
LIMIT 10;

-- Q9. Records flagged by the pipeline, by country (top 10 by number of flagged days)
SELECT
    c.Country,
    SUM(f.Revision_Flag)      AS revision_days,
    SUM(f.Inconsistency_Flag) AS inconsistency_days
FROM Fact_Covid f
JOIN Dim_Country c ON c.ISO_Code = f.ISO_Code
GROUP BY c.Country
HAVING SUM(f.Revision_Flag) + SUM(f.Inconsistency_Flag) > 0
ORDER BY revision_days + inconsistency_days DESC
LIMIT 10;
