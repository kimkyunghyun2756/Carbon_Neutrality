# -*- coding: utf-8 -*-
"""
- CSV 1행을 컬럼명으로 사용해 TEXT 컬럼들로 테이블을 만듭니다.
- 컬럼명은 snake_case로 정리하고, 중복은 _2, _3... 으로 해소합니다.
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


def sanitize_identifier(name: str, used: set, prefix: str = "c_") -> str:
    """
    Make a safe Postgres identifier:
      - strip, lower
      - non [a-zA-Z0-9_] -> _
      - if starts with digit -> prefix (default c_)
      - collapse consecutive _
      - trim to 63 chars (PG identifier limit)
      - deduplicate with suffixes _2, _3...
    """
    orig = name or ""
    s = orig.strip().lower()
    if not s:
        s = "column"
    s = re.sub(r"[^0-9a-z_]", "_", re.sub(r"\s+", "_", s))
    if re.match(r"^[0-9]", s):
        s = prefix + s
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "column"
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
    # 읽을 때 pandas 없이도 헤더만 뽑아오도록 빠르게 처리
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


def build_create_table_sql(table: str, raw_cols: List[str], add_id: bool = True) -> Tuple[str, List[str]]:
    used = set()
    cols = [sanitize_identifier(c, used) for c in raw_cols]
    parts = []
    if add_id:
        parts.append('id BIGSERIAL PRIMARY KEY')
    parts += [f'"{c}" TEXT' for c in cols]
    ddl = f'CREATE TABLE IF NOT EXISTS "{table}" (\n  ' + ",\n  ".join(parts) + "\n);"
    return ddl, cols


def build_engine() -> Engine:
    # .env 또는 환경변수에서 읽기 (DATABASE_URL이 있으면 그걸 우선)
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
    # ✅ 환경변수 기본값 추가: CSV_PATH / CSV_TABLE / CSV_ENCODING / CSV_NO_ID
    p.add_argument("--csv", default=os.getenv("CSV_PATH"),
                   help="CSV file path (or set CSV_PATH)")
    p.add_argument("--table", default=os.getenv("CSV_TABLE"),
                   help="Table name (or set CSV_TABLE; default: from csv filename)")
    p.add_argument("--encoding", default=os.getenv("CSV_ENCODING", "utf-8"),
                   help="CSV encoding (default: utf-8 or CSV_ENCODING)")
    p.add_argument("--no-id", action="store_true",
                   help="Do not create 'id BIGSERIAL' column (or set CSV_NO_ID=true)")

    args = p.parse_args()

    # ~, $HOME 같은 것 확장
    if not args.csv:
        p.error("CSV path is required. Pass --csv or set CSV_PATH.")
    csv_path = Path(os.path.expandvars(os.path.expanduser(args.csv)))

    # 테이블명이 없으면 파일명에서 유추
    table = args.table or infer_table_name(csv_path)

    # env로 no-id를 켤 수도 있음
    no_id_env = os.getenv("CSV_NO_ID", "").lower() in ("1", "true", "yes")
    add_id = not (args.no_id or no_id_env)

    header = read_header(csv_path, encoding=args.encoding)
    ddl, cols = build_create_table_sql(table, header, add_id=add_id)

    engine = build_engine()
    with engine.begin() as conn:
        conn.execute(text(ddl))

    print("[OK] Created table:", table)
    print("[INFO] Columns:", ", ".join(cols))


if __name__ == "__main__":
    main()
