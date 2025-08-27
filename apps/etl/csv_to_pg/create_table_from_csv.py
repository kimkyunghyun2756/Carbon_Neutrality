# -*- coding: utf-8 -*-
"""
Create a PostgreSQL table from a CSV header (row-1 -> columns).
- Column types:
  - description, name, iso_code, year  -> TEXT   (⚠ year도 TEXT)
  - population, gdp                    -> BIGINT
  - others                             -> NUMERIC
- Identifiers are sanitized to safe snake_case, deduped with _2, _3...
- Supports .env / environment variables.
- Optional: drop & recreate table via --recreate or CSV_RECREATE=1

Requires: SQLAlchemy>=2.0, psycopg[binary]>=3.2, python-dotenv>=1.0 (optional)
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv  # optional
    load_dotenv()
except Exception:
    pass


# ---------- identifier helpers ----------
def sanitize_identifier(name: str, used: set, prefix: str = "c_") -> str:
    """
    Make a safe Postgres identifier:
      - strip, lower
      - whitespace -> _
      - non [a-z0-9_] -> _
      - if starts with digit -> prefix
      - collapse underscores, trim edges
      - trim to 63 chars (PG limit)
      - deduplicate with _2, _3...
    """
    orig = name or ""
    s = orig.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9a-z_]", "_", s)
    if not s:
        s = "column"
    if s[0].isdigit():
        s = prefix + s
    s = re.sub(r"_+", "_", s).strip("_") or "column"
    s = s[:63]

    base = s
    i = 2
    while s in used:
        suffix = f"_{i}"
        s = (base[: (63 - len(suffix))] + suffix) if len(base) + len(suffix) > 63 else base + suffix
        i += 1
    used.add(s)
    return s


def read_header(csv_path: Path, encoding: str = "utf-8") -> List[str]:
    import csv
    with csv_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
    if not header:
        raise RuntimeError("CSV의 1행(헤더)이 비어 있습니다.")
    return header


def infer_table_name(csv_path: Path) -> str:
    used = set()
    return sanitize_identifier(csv_path.stem, used, prefix="t_")


# ---------- type mapping ----------
TYPE_OVERRIDES = {
    "description": "TEXT",
    "name": "TEXT",
    "iso_code": "TEXT",
    "year": "TEXT",        # ← 요청대로 연도는 TEXT로 저장
    "population": "BIGINT",
    "gdp": "BIGINT",
}
DEFAULT_TYPE = "NUMERIC"   # 나머지 컬럼


def choose_type(col: str) -> str:
    return TYPE_OVERRIDES.get(col, DEFAULT_TYPE)


def build_create_table_sql(table: str, raw_cols: List[str], add_id: bool = True) -> Tuple[str, List[str]]:
    used = set()
    cols = [sanitize_identifier(c, used) for c in raw_cols]
    parts = []
    if add_id:
        parts.append('id BIGSERIAL PRIMARY KEY')
    # 각 컬럼에 타입 적용
    parts += [f'"{c}" {choose_type(c)}' for c in cols]
    ddl = f'CREATE TABLE IF NOT EXISTS "{table}" (\n  ' + ",\n  ".join(parts) + "\n);"
    return ddl, cols


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
    p = argparse.ArgumentParser(description="Create a Postgres table from CSV header.")
    # env 기본값 사용 (CSV_PATH/CSV_TABLE/CSV_ENCODING/CSV_NO_ID/CSV_RECREATE)
    p.add_argument("--csv", default=os.getenv("CSV_PATH"), help="CSV file path (or set CSV_PATH)")
    p.add_argument("--table", default=os.getenv("CSV_TABLE"), help="Table name (or set CSV_TABLE; default: from csv filename)")
    p.add_argument("--encoding", default=os.getenv("CSV_ENCODING", "utf-8"), help="CSV encoding (default: utf-8 or CSV_ENCODING)")
    p.add_argument("--no-id", action="store_true", help="Do not create 'id BIGSERIAL' column (or set CSV_NO_ID=true)")
    p.add_argument("--recreate", action="store_true", help="Drop table then create (or set CSV_RECREATE=1)")
    args = p.parse_args()

    if not args.csv:
        p.error("CSV path is required. Use --csv or set CSV_PATH.")
    csv_path = Path(os.path.expandvars(os.path.expanduser(args.csv)))
    if not csv_path.exists():
        print(f"[ERROR] CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(2)

    table = args.table or infer_table_name(csv_path)
    no_id_env = os.getenv("CSV_NO_ID", "").lower() in ("1", "true", "yes")
    add_id = not (args.no_id or no_id_env)

    # recreate flag
    recreate = args.recreate or (os.getenv("CSV_RECREATE", "").lower() in ("1", "true", "yes"))

    header = read_header(csv_path, encoding=args.encoding)
    ddl, cols = build_create_table_sql(table, header, add_id=add_id)

    engine = build_engine()
    with engine.begin() as conn:
        if recreate:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}";'))
        conn.execute(text(ddl))

    print(f"[OK] Created table: {table}")
    print("[INFO] Columns:", ", ".join(cols))


if __name__ == "__main__":
    main()
