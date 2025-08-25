# mod3_db.py
# Reusable DB connection helpers (SQLAlchemy).
import os
from sqlalchemy import create_engine, text

def get_engine(dsn: str | None = None):
  dsn = dsn or os.getenv("PG_DSN", "postgresql+psycopg://app:apppw@localhost:5432/appdb")
  return create_engine(dsn)

def ping(engine) -> bool:
  try:
    with engine.connect() as conn:
      conn.execute(text("SELECT 1"))
    return True
  except Exception:
    return False
