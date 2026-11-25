"""Build the toxonomy SQLite database from schema/schema.sql and data/*.csv."""
import csv, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = ["reference", "entity", "cv_term", "entity_facet", "taxon", "producer",
          "homology", "immunity", "counter_adaptation", "entity_reference"]


def load_table(conn, name):
    """Insert every row of data/<name>.csv into table <name>."""
    path = ROOT / "data" / f"{name}.csv"
    if not path.exists():
        return 0
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        cols = reader.fieldnames
        sql = "INSERT INTO {} ({}) VALUES ({})".format(
            name, ",".join(cols), ",".join("?" * len(cols)))
        rows = [[(r[c] if r[c] != "" else None) for c in cols] for r in reader]
    conn.executemany(sql, rows)
    return len(rows)


def build(db_path):
    """Create the database from scratch and report per-table row counts."""
    target = Path(db_path)
    if target.exists():
        target.unlink()
    conn = sqlite3.connect(target)
    conn.executescript((ROOT / "schema" / "schema.sql").read_text())
    counts = {name: load_table(conn, name) for name in TABLES}
    conn.commit()
    conn.close()
    return counts


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "toxonomy.db")
    for table, n in build(out).items():
        print(f"{table:20s} {n:5d}")
    print(f"wrote {out}")
