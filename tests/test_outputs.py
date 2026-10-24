"""Checks on the pipeline outputs. Run the pipeline first: python run_pipeline.py"""
import json
import re
import sys
import unittest
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PROCESSED = ROOT / "data" / "processed"
CUTOFF = pd.Timestamp("2021-08-04")


def read(name):
    return pd.read_csv(PROCESSED / f"{name}.csv", keep_default_na=False, na_values=[""])


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PROCESSED / "Fact_Covid.csv").exists():
            raise unittest.SkipTest("run python run_pipeline.py first")
        cls.fact = read("Fact_Covid")
        cls.fact["Date"] = pd.to_datetime(cls.fact["Date"])
        cls.dim_date = read("Dim_Date")
        cls.dim_date["Date"] = pd.to_datetime(cls.dim_date["Date"])
        cls.dim_country = read("Dim_Country")

    def test_grain_and_keys(self):
        f = self.fact
        self.assertEqual(f.duplicated(["ISO_Code", "Date"]).sum(), 0)
        self.assertEqual(len(f), f["ISO_Code"].nunique() * f["Date"].nunique())
        self.assertTrue(f["ISO_Code"].isin(self.dim_country["ISO_Code"]).all())
        self.assertTrue(f["Date"].isin(self.dim_date["Date"]).all())
        self.assertTrue(self.dim_country["ISO_Code"].is_unique)
        self.assertTrue(self.dim_date["Date"].is_unique)

    def test_date_table_is_continuous(self):
        gaps = self.dim_date["Date"].sort_values().diff().dropna()
        self.assertTrue((gaps == pd.Timedelta(days=1)).all())
        self.assertEqual(self.dim_date["Date"].min(), self.fact["Date"].min())
        self.assertEqual(self.dim_date["Date"].max(), self.fact["Date"].max())

    def test_daily_values_add_up_to_cumulative(self):
        by_country = self.fact.sort_values("Date").groupby("ISO_Code")
        for daily, total in (("Daily_Cases", "Confirmed"), ("Daily_Deaths", "Deaths")):
            self.assertTrue((by_country[daily].sum() == by_country[total].last()).all())

    def test_cumulative_values_are_not_negative(self):
        self.assertTrue((self.fact[["Confirmed", "Deaths"]] >= 0).all().all())

    def test_recoveries_are_blank_not_zero_when_unavailable(self):
        f = self.fact
        self.assertTrue(f.loc[f["Date"] > CUTOFF, "Recovered"].isna().all())
        missing = f["Recovered"].isna()
        self.assertTrue(f.loc[missing, "Active"].isna().all())
        self.assertTrue(f.loc[missing, "Daily_Recoveries"].isna().all())
        self.assertTrue((f["Active"].dropna() >= 0).all())
        for iso in ("GBR", "USA", "BEL", "SRB"):
            rows = f[(f["ISO_Code"] == iso) & (f["Date"] == CUTOFF)]
            self.assertTrue(rows["Recovered"].isna().all(), iso)

    def test_flags_match_their_definitions(self):
        f = self.fact
        revision = (f["Daily_Cases"] < 0) | (f["Daily_Deaths"] < 0) | (f["Daily_Recoveries"] < 0)
        self.assertTrue((f["Revision_Flag"] == revision.astype(int)).all())
        inconsistent = f["Deaths"] + f["Recovered"].fillna(0) > f["Confirmed"]
        self.assertTrue((f["Inconsistency_Flag"] == inconsistent.astype(int)).all())

    def test_negative_daily_values_are_kept(self):
        self.assertGreater((self.fact["Daily_Cases"] < 0).sum(), 0)

    def test_population_coverage(self):
        self.assertGreaterEqual(self.dim_country["Population"].notna().mean(), 0.95)

    def test_validation_has_no_failures(self):
        dq = read("DQ_Checks")
        self.assertNotIn("FAIL", set(dq["Status"]))


class PowerBiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dax = (ROOT / "powerbi" / "measures.dax").read_text(encoding="utf-8")
        cls.docs = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "powerbi").glob("*.md")}
        cls.tables = {n: pd.read_csv(PROCESSED / f"{n}.csv", nrows=0).columns for n in
                      ("Fact_Covid", "Dim_Date", "Dim_Country", "DQ_Checks") if (PROCESSED / f"{n}.csv").exists()}
        cls.measures = {n for n in re.findall(r"^([A-Za-z0-9][A-Za-z0-9 %\-]*?) =\s*$", cls.dax, flags=re.M)
                        if not n.startswith("VAR ")}

    def test_power_query_columns_match_csv(self):
        code = (ROOT / "powerbi" / "power_query.m").read_text(encoding="utf-8")
        blocks = re.split(r"// ===== (\w+) =====", code)[1:]
        for name, body in zip(blocks[::2], blocks[1::2]):
            declared = re.findall(r'\{"(\w+)", ', body)
            self.assertEqual(set(declared), set(self.tables[name]), name)

    def test_guides_only_use_existing_measures_and_columns(self):
        text = "\n".join(self.docs.values())
        for name in set(re.findall(r"`\[([^\]]+)\]`", text)) - {"Measure"}:
            self.assertIn(name, self.measures, name)
        for table, column in set(re.findall(r"`?(Dim_Date|Dim_Country|Fact_Covid|DQ_Checks)\[(\w+)\]`?", text + self.dax)):
            self.assertIn(column, self.tables[table], f"{table}[{column}]")

    def test_dax_parentheses_are_balanced(self):
        for block in re.split(r"\n\n(?=[A-Za-z0-9/])", self.dax):
            self.assertEqual(block.count("("), block.count(")"), block.splitlines()[0])

    def test_rank_measures_remove_region_and_country_filters(self):
        self.assertNotIn("ALL ( Dim_Country[Country] )", self.dax)
        self.assertIn("RANKX ( ALL ( Dim_Country )", self.dax)

    def test_visual_positions_fit_the_canvas(self):
        for name in ("README.md", "overview_page.md"):
            for line in self.docs[name].splitlines():
                if not line.startswith("|"):
                    continue
                for x, y, w, h in re.findall(r"(\d+), (\d+), (\d+), (\d+)", line):
                    x, y, w, h = map(int, (x, y, w, h))
                    self.assertLessEqual(x + w, 1280, line[:80])
                    self.assertLessEqual(y + h, 720, line[:80])

    def test_theme_is_valid_json(self):
        theme = json.loads((ROOT / "powerbi" / "theme.json").read_text(encoding="utf-8"))
        self.assertIn("dataColors", theme)


class OutputTests(unittest.TestCase):
    def test_preview_shows_values_from_the_data(self):
        html_path = ROOT / "preview" / "overview.html"
        if not html_path.exists():
            self.skipTest("run python run_pipeline.py first")
        html = html_path.read_text(encoding="utf-8")
        fact = read("Fact_Covid")
        last = fact["Date"].max()
        cases = int(fact.loc[fact["Date"] == last, "Confirmed"].sum())
        self.assertIn(f"{cases:,}", html)

    def test_excel_workbook_structure(self):
        path = ROOT / "excel" / "covid_analysis.xlsx"
        if not path.exists():
            self.skipTest("run python run_pipeline.py first")
        with zipfile.ZipFile(path) as z:
            workbook = z.read("xl/workbook.xml").decode()
            sheets = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
        for name in ("Overview", "Data_Dictionary", "Data_Quality", "Country_Summary",
                     "Monthly_Global", "Pivot_Analysis", "Analytical_Data"):
            self.assertIn(f'name="{name}"', workbook)
        self.assertGreater(sheets.count("<f>"), 1000)
        self.assertNotRegex(sheets, r"<f>[^<]*(?<![_.\w])MAXIFS\(")

    def test_sql_queries_run(self):
        if not (ROOT / "outputs" / "covid.db").exists():
            self.skipTest("run python run_pipeline.py first")
        from run_sql import run
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            results = run()
        self.assertEqual(len(results), 9)
        self.assertTrue(all(rows for _, _, rows in results))


if __name__ == "__main__":
    unittest.main()
