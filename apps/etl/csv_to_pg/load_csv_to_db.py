# -*- coding: utf-8 -*-
"""
Load CSV data (rows from line 2~) into a PostgreSQL table.
- Column sanitation must match DDL creation.
- Type handling:
  - description, name, iso_code, year -> TEXT  (year도 TEXT)
  - population, gdp                   -> BIGINT (nullable Int64)
  - others                            -> numeric (floats via pandas; PG NUMERIC에 삽입)
- Empty strings -> NULL(pd.NA) when appropriate.

Requires: pandas>=2.2, SQLAlchemy>=2.0, psycopg[binary]>=3.2, python-dotenv(optional)
"""

import argparse
import os
import re
from pathlib import Path
from typing import List, Set

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv  # optional
    load_dotenv()
except Exception:
    pass


# ---------- identifier helpers (must match the one in DDL script) ----------
def sanitize_all(columns: List[str]) -> List[str]:
    used: Set[str] = set()
    out: List[str] = []
    for c in columns:
        s = (c or "").strip().lower()
        s = re.sub(r"\s+", "_", s)
        s = re.sub(r"[^0-9a-z_]", "_", s)
        if not s:
            s = "column"
        if s[0].isdigit():
            s = "c_" + s
        s = re.sub(r"_+", "_", s).strip("_") or "column"
        s = s[:63]

        base = s
        i = 2
        while s in used:
            s = (base[: (63 - len(f"_{i}"))] + f"_{i}") if len(base) + len(f"_{i}") > 63 else f"{base}_{i}"
            i += 1
        used.add(s)
        out.append(s)
    return out


# ---------- engine ----------
def build_engine() -> Engine:
    url = os.getenv("DATABASE_URL")
    if not url:
        host = os.getenv("DB_HOST") or "127.0.0.1"
        port = os.getenv("DB_PORT") or "5432"
        name = os.getenv("DB_NAME") or "appdb"
        user = os.getenv("DB_USER") or "app"
        pw   = os.getenv("DB_PASSWORD") or "apppw"
        url = f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{name}"
    return create_engine(url, future=True)


def main():
    ap = argparse.ArgumentParser(description="Load CSV into Postgres table.")
    ap.add_argument("--csv", default=os.getenv("CSV_PATH"), help="CSV file path (or set CSV_PATH)")
    ap.add_argument("--table", default=os.getenv("CSV_TABLE"), help="Target table name (or set CSV_TABLE; default: from csv filename)")
    ap.add_argument("--encoding", default=os.getenv("CSV_ENCODING", "utf-8"), help="CSV encoding (default: utf-8 or CSV_ENCODING)")
    ap.add_argument("--chunksize", type=int, default=int(os.getenv("CSV_CHUNKSIZE", "1000")), help="Rows per batch")
    ap.add_argument("--sep", default=os.getenv("CSV_SEP", ","), help="CSV separator (default: ',' or CSV_SEP)")
    args = ap.parse_args()

    if not args.csv:
        ap.error("CSV path is required. Use --csv or set CSV_PATH.")
    csv_path = Path(os.path.expandvars(os.path.expanduser(args.csv)))
    if not csv_path.exists():
        raise SystemExit(f"[ERROR] CSV not found: {csv_path}")

    # Load CSV: header=1st row, data from row-2; keep as strings first
    df = pd.read_csv(csv_path, encoding=args.encoding, sep=args.sep, dtype=str, keep_default_na=False)
    # Sanitize columns to match table DDL
    df.columns = sanitize_all(list(df.columns))

    # ---- type groups (sanitized names) ----
    text_cols = {"description", "name", "iso_code", "year"}  # year도 TEXT
    bigint_cols = {"population", "gdp"}
    numeric_cols = [c for c in df.columns if c not in text_cols | bigint_cols]

    # Common trim
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()

    # TEXT: empty -> NULL
    for c in text_cols:
        if c in df.columns:
            df[c] = df[c].replace({"": pd.NA})

    # BIGINT: remove thousands separators, empty->NA, to Int64 (nullable)
    for c in bigint_cols:
        if c in df.columns:
            s = df[c].str.replace(",", "", regex=False).replace({"": pd.NA})
            df[c] = pd.to_numeric(s, errors="coerce").astype("Int64")

    # NUMERIC: remove thousands separators, to float (PG NUMERIC will accept)
    for c in numeric_cols:
        s = df[c].str.replace(",", "", regex=False).replace({"": pd.NA})
        df[c] = pd.to_numeric(s, errors="coerce")

    # Target table name
    table = args.table
    if not table:
        # derive from file name (simple version, same as create_table_from_csv.infer_table_name)
        name = csv_path.stem.lower()
        name = re.sub(r"\s+", "_", name)
        name = re.sub(r"[^0-9a-z_]", "_", name)
        if name and name[0].isdigit():
            name = "t_" + name
        table = name or "data"

    engine = build_engine()
    # Append into existing table
    df.to_sql(
        table,
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=args.chunksize,
    )

    print(f"[OK] Loaded {len(df):,} rows into {table}")


if __name__ == "__main__":
    main()
