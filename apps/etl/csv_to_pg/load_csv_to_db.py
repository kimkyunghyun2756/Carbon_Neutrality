# -*- coding: utf-8 -*-
"""
Load CSV data (rows from line 2~) into a PostgreSQL table.
- Uses pandas.DataFrame.to_sql() with method="multi".
- Column names are sanitized same as in DDL creation.
한국어 요약:
- CSV 2행부터 모든 데이터를 그대로 적재합니다. (헤더는 컬럼명)
- 컬럼명 치환 로직은 테이블 생성과 동일하게 적용합니다.
"""

import argparse
import os
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv  # optional
    load_dotenv()
except Exception:
    pass


def sanitize_all(columns: List[str]) -> List[str]:
    used = set()
    out = []
    for c in columns:
        s = c.strip().lower()
        s = re.sub(r"[^0-9a-z_]", "_", re.sub(r"\s+", "_", s))
        if not s:
            s = "column"
        if s[0].isdigit():
            s = "c_" + s
        s = re.sub(r"_+", "_", s).strip("_")
        s = s[:63] or "column"
        base = s
        i = 2
        while s in used:
            s = (base[: (63 - len(f"_{i}"))] + f"_{i}") if len(base) + len(f"_{i}") > 63 else f"{base}_{i}"
            i += 1
        used.add(s)
        out.append(s)
    return out


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
    # ✅ 환경변수 기본값 추가: CSV_PATH / CSV_TABLE / CSV_ENCODING / CSV_SEP / CSV_CHUNKSIZE
    ap.add_argument("--csv", default=os.getenv("CSV_PATH"),
                    help="CSV file path (or set CSV_PATH)")
    ap.add_argument("--table", default=os.getenv("CSV_TABLE"),
                    help="Target table name (or set CSV_TABLE; default: from csv filename)")
    ap.add_argument("--encoding", default=os.getenv("CSV_ENCODING", "utf-8"),
                    help="CSV encoding (default: utf-8 or CSV_ENCODING)")
    ap.add_argument("--chunksize", type=int,
                    default=int(os.getenv("CSV_CHUNKSIZE", "1000")),
                    help="Rows per batch (default: 1000 or CSV_CHUNKSIZE)")
    ap.add_argument("--sep", default=os.getenv("CSV_SEP", ","),
                    help="CSV separator (default: ',' or CSV_SEP)")
    args = ap.parse_args()

    if not args.csv:
        ap.error("CSV path is required. Pass --csv or set CSV_PATH.")
    csv_path = Path(os.path.expandvars(os.path.expanduser(args.csv)))
    if not csv_path.exists():
        raise SystemExit(f"[ERROR] CSV not found: {csv_path}")

    # 테이블명이 비어 있으면 파일명으로 유추 (생성 스크립트와 동일 규칙)
    table = args.table
    if not table:
        from pathlib import Path as _P
        from re import sub as _sub
        used = set()
        # infer_table_name과 동일 로직을 써도 되고, 간단히 파일명 기반으로:
        table = csv_path.stem.lower()
        table = _sub(r"\s+", "_", table)
        table = _sub(r"[^0-9a-z_]", "_", table)
        if table[0].isdigit():
            table = "t_" + table

    df = pd.read_csv(csv_path, encoding=args.encoding, sep=args.sep,
                     dtype=str, keep_default_na=False)
    df.columns = sanitize_all(list(df.columns))

    engine = build_engine()
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
