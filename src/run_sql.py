import re
import sqlite3
import sys

from config import OUTPUTS_DIR, ROOT


def load_queries():
    text = (ROOT / "sql" / "analysis.sql").read_text(encoding="utf-8")
    queries = []
    for block in text.split(";"):
        if "SELECT" not in block:
            continue
        title = re.search(r"^-- (Q\d+\..*)$", block, flags=re.M)
        queries.append((title.group(1) if title else "query", block.strip()))
    return queries


def run(rows_to_show=5):
    db = OUTPUTS_DIR / "covid.db"
    if not db.exists():
        sys.exit("outputs/covid.db not found. Run python run_pipeline.py first.")
    results = []
    with sqlite3.connect(db) as conn:
        for title, query in load_queries():
            cursor = conn.execute(query)
            columns = [c[0] for c in cursor.description]
            rows = cursor.fetchall()
            results.append((title, columns, rows))
            print(f"\n{title}\n  {len(rows)} rows; columns: {', '.join(columns)}")
            for row in rows[:rows_to_show]:
                print("  ", row)
    return results


if __name__ == "__main__":
    run()
