#!/usr/bin/env python3
# mod2_execute_sql_file.py
# Execute a .sql file against PostgreSQL using SQLAlchemy.

import os, argparse, sys
from sqlalchemy import create_engine, text

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--dsn", default=os.getenv("PG_DSN", "postgresql+psycopg://app:apppw@localhost:5432/appdb"))
  ap.add_argument("--sql", required=True, help="Path to .sql file")
  args = ap.parse_args()

  if not os.path.exists(args.sql):
    print(f"[ERR] SQL file not found: {args.sql}", file=sys.stderr)
    sys.exit(2)

  engine = create_engine(args.dsn)
  sql_text = open(args.sql, "r", encoding="utf-8").read()
  with engine.begin() as conn:
    conn.execute(text(sql_text))
  print(f"[OK] executed {args.sql}")

if __name__ == "__main__":
  main()
