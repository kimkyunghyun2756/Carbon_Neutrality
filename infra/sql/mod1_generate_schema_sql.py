#!/usr/bin/env python3
# mod1_generate_schema_sql.py
# Create a SQL file that defines the normalized (expanded) schema.

import os, argparse, textwrap, sys

SCHEMA_SQL = r"""
-- schema_normalized.sql (generated)
-- Normalized star schema for carbon emissions
-- Note: '(GCP)' rows are filtered at ETL; here we also keep a CHECK for safety.

DROP TABLE IF EXISTS fact_emission CASCADE;
DROP TABLE IF EXISTS dim_metric CASCADE;
DROP TABLE IF EXISTS dim_unit CASCADE;
DROP TABLE IF EXISTS dim_time CASCADE;
DROP TABLE IF EXISTS dim_entity CASCADE;

CREATE TABLE dim_entity (
  entity_id SERIAL PRIMARY KEY,
  name      TEXT NOT NULL,
  iso_code  CHAR(3),
  kind      TEXT NOT NULL,
  CONSTRAINT chk_entity_no_gcp CHECK (position('(GCP)' in name) = 0)
);
-- Unique on (name, coalesce(iso_code,'---'))
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_dim_entity_name_iso_expr'
  ) THEN
    CREATE UNIQUE INDEX uq_dim_entity_name_iso_expr
      ON dim_entity (name, (COALESCE(iso_code,'---')));
  END IF;
END $$;

CREATE TABLE dim_unit (
  unit_id SERIAL PRIMARY KEY,
  code    TEXT NOT NULL UNIQUE,
  desc    TEXT
);

CREATE TABLE dim_metric (
  metric_id   SERIAL PRIMARY KEY,
  code        TEXT NOT NULL UNIQUE,
  title       TEXT,
  category    TEXT,
  is_derived  BOOLEAN DEFAULT FALSE,
  formula_sql TEXT,
  unit_id     INT REFERENCES dim_unit(unit_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE dim_time (
  year INT PRIMARY KEY
);

CREATE TABLE fact_emission (
  entity_id  INT NOT NULL REFERENCES dim_entity(entity_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  metric_id  INT NOT NULL REFERENCES dim_metric(metric_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  year       INT NOT NULL REFERENCES dim_time(year) ON UPDATE CASCADE ON DELETE RESTRICT,
  value      DOUBLE PRECISION,
  source     TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT fact_emission_pkey PRIMARY KEY (entity_id, metric_id, year)
);

CREATE INDEX IF NOT EXISTS idx_fact_entity_year ON fact_emission(entity_id, year);
CREATE INDEX IF NOT EXISTS idx_fact_metric       ON fact_emission(metric_id);
"""

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--out", default="schema_normalized.sql")
  args = ap.parse_args()
  with open(args.out, "w", encoding="utf-8") as f:
    f.write(SCHEMA_SQL.strip() + "\n")
  print(f"[OK] wrote {args.out}")

if __name__ == "__main__":
  main()
