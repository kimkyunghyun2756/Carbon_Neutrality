#!/usr/bin/env python3
# mod4_generate_load_sql.py
# Create a single SQL file that:
#  - creates a staging table matching CSV columns
#  - inserts all CSV rows (excluding Name like '%(GCP)%')
#  - populates dim_entity, dim_time, dim_unit, dim_metric
#  - loads fact_emission by unpivoting staging values

import os, argparse, sys, pandas as pd, math, re, textwrap

def unit_for_metric(code: str) -> str:
  if code in {"population"}: return "people"
  if code in {"gdp"}: return "USD"
  if code.startswith("share_global_") or code.endswith("_growth_prct") or code == "trade_co2_share": return "%"
  if code.startswith("temperature_change_") or code == "share_of_temperature_change_from_ghg": return "degC"
  if code.endswith("_per_capita"): return "per_capita"
  if code.endswith("_per_gdp"): return "per_USD"
  if code.endswith("_per_unit_energy"): return "per_energy"
  if code in {"total_ghg","total_ghg_excluding_lucf","methane","nitrous_oxide","ghg_per_capita","ghg_excluding_lucf_per_capita"}: return "MtCO2e"
  if code in {"primary_energy_consumption","energy_per_capita","energy_per_gdp"}: return "energy"
  return "MtCO2"

def category_for_metric(code: str) -> str:
  if code in {"co2","co2_including_luc"}: return "totals"
  if code in {"coal_co2","oil_co2","gas_co2","cement_co2","flaring_co2","land_use_change_co2","other_industry_co2"}: return "fuel"
  if code.startswith("cumulative_"): return "cumulative"
  if code.endswith("_per_capita"): return "per_capita"
  if code.endswith("_per_gdp"): return "per_gdp"
  if code.endswith("_per_unit_energy"): return "per_unit_energy"
  if code.startswith("share_global_"): return "share"
  if code.endswith("_growth_abs") or code.endswith("_growth_prct"): return "growth"
  if code in {"primary_energy_consumption","energy_per_capita","energy_per_gdp"}: return "energy"
  if code in {"total_ghg","total_ghg_excluding_lucf","methane","nitrous_oxide","ghg_per_capita","ghg_excluding_lucf_per_capita"}: return "ghg"
  if code.startswith("temperature_change_") or code == "share_of_temperature_change_from_ghg": return "temp"
  if code in {"consumption_co2","trade_co2","trade_co2_share"}: return "trade"
  return "other"

def sql_literal(v):
  import math
  if v is None: return "NULL"
  try:
    if isinstance(v, float) and math.isnan(v): return "NULL"
  except Exception:
    pass
  if isinstance(v, (int, float)):
    return str(v)
  s = str(v).replace("'", "''")
  return f"'{s}'"

def infer_sql_type(name, series):
  if name == "year": return "integer"
  if name == "iso_code": return "char(3)"
  if name in ("Name","Description"): return "text"
  if pd.api.types.is_integer_dtype(series): return "bigint"
  if pd.api.types.is_float_dtype(series): return "double precision"
  try:
    pd.to_numeric(series.dropna().head(100))
    return "double precision"
  except Exception:
    return "text"

def q_ident(col):
  return f'"{col}"' if (not col.isidentifier() or col[0].isdigit() or col.lower() != col) else col

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--csv", default="Data.csv")
  ap.add_argument("--out", default="load_from_csv.sql")
  ap.add_argument("--insert-batch", type=int, default=500, help="rows per INSERT VALUES batch")
  args = ap.parse_args()

  if not os.path.exists(args.csv):
    print(f"[ERR] CSV not found: {args.csv}", file=sys.stderr); sys.exit(2)

  df = pd.read_csv(args.csv, low_memory=False)
  # filter out (GCP)
  mask_gcp = df["Name"].astype(str).str.contains(r"\(GCP\)", na=False)
  df = df.loc[~mask_gcp].copy()

  id_vars = ["Name","iso_code","Description","year"]
  cols = list(df.columns)

  # 1) staging DDL
  col_defs = []
  for c in cols:
    sqlt = infer_sql_type(c, df[c])
    col_defs.append(f"  {q_ident(c)} {sqlt}")
  staging_ddl = "CREATE TABLE IF NOT EXISTS staging_emissions_wide (\n" + ",\n".join(col_defs) + "\n);\n"

  # 2) INSERT batches into staging
  batches = []
  batch_size = args.insert_batch
  for start in range(0, len(df), batch_size):
    chunk = df.iloc[start:start+batch_size]
    values_rows = []
    for _, row in chunk.iterrows():
      vals = [sql_literal(None if (pd.isna(v)) else v) for v in [row[c] for c in cols]]
      values_rows.append("(" + ", ".join(vals) + ")")
    insert_sql = f"INSERT INTO staging_emissions_wide ({', '.join(q_ident(c) for c in cols)})\nVALUES\n  " + ",\n  ".join(values_rows) + ";\n"
    batches.append(insert_sql)

  # 3) Units & Metrics VALUE tuples
  metric_cols = [c for c in cols if c not in id_vars]
  unit_codes = sorted({unit_for_metric(c) for c in metric_cols})
  units_insert = "INSERT INTO dim_unit(code, desc)\nVALUES\n  " + ",\n  ".join(f"('{u}', NULL)" for u in unit_codes) + "\nON CONFLICT (code) DO NOTHING;\n"

  values_lines = []
  for c in metric_cols:
    title = c.replace("_"," ").title()
    cat = category_for_metric(c)
    der = "true" if ("_per_" in c or c.startswith("cumulative_") or c.startswith("share_global_") or c.endswith("_growth_abs") or c.endswith("_growth_prct") or c in ("consumption_co2","trade_co2","trade_co2_share")) else "false"
    unit = unit_for_metric(c)
    values_lines.append(f"('{c}','{title}','{cat}',{der},'{unit}')")
  metrics_values = ",\n  ".join(values_lines)
  metrics_insert = f"""
WITH m(code,title,category,is_derived,unit_code) AS (
  VALUES
  {metrics_values}
)
INSERT INTO dim_metric(code,title,category,is_derived,unit_id)
SELECT m.code, m.title, m.category, m.is_derived, u.unit_id
FROM m
JOIN dim_unit u ON u.code = m.unit_code
ON CONFLICT (code) DO UPDATE
  SET title = EXCLUDED.title,
      category = EXCLUDED.category,
      is_derived = EXCLUDED.is_derived,
      unit_id = EXCLUDED.unit_id;
"""

  # 4) Entities & Time inserts
  entities_insert = """
INSERT INTO dim_entity(name, iso_code, kind)
SELECT DISTINCT "Name", iso_code, "Description"
FROM staging_emissions_wide
WHERE position('(GCP)' in "Name") = 0
ON CONFLICT (name, COALESCE(iso_code,'---')) DO NOTHING;
"""
  years_insert = """
INSERT INTO dim_time(year)
SELECT DISTINCT year FROM staging_emissions_wide
WHERE year IS NOT NULL
ON CONFLICT (year) DO NOTHING;
"""

  # 5) Facts
  v_pairs = ",\n      ".join([f"('{c}', s.{q_ident(c)})" for c in metric_cols])
  facts_insert = f"""
INSERT INTO fact_emission(entity_id, metric_id, year, value, source, updated_at)
SELECT
  e.entity_id,
  m.metric_id,
  s.year,
  v.val::double precision AS value,
  'csv' AS source,
  NOW() AS updated_at
FROM staging_emissions_wide s
JOIN dim_entity e
  ON e.name = s."Name" AND COALESCE(e.iso_code,'---') = COALESCE(s.iso_code,'---')
JOIN dim_time t ON t.year = s.year
JOIN (
      VALUES
      {v_pairs}
) AS v(code, val) ON TRUE
JOIN dim_metric m ON m.code = v.code
WHERE v.val IS NOT NULL;
"""

  parts = []
  parts.append("-- load_from_csv.sql (generated)\nBEGIN;")
  parts.append("-- 1) staging")
  parts.append("DROP TABLE IF EXISTS staging_emissions_wide;")
  parts.append(staging_ddl)
  parts.extend(batches)
  parts.append("-- 2) dim_unit / dim_metric")
  parts.append(units_insert)
  parts.append(metrics_insert)
  parts.append("-- 3) dim_entity / dim_time")
  parts.append(entities_insert)
  parts.append(years_insert)
  parts.append("-- 4) facts")
  parts.append(facts_insert)
  parts.append("COMMIT;")

  with open(args.out, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))

  print(f"[OK] wrote {args.out} (rows={len(df)}, metrics={len(metric_cols)})")

if __name__ == "__main__":
  main()
