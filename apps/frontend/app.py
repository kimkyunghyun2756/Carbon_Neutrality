import os
import re
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from functools import lru_cache

# --- env (K8s에서는 envFrom, 로컬은 .env 로드)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "apppw")
TABLE = os.getenv("CSV_TABLE", "data")

@lru_cache(maxsize=1)
def _engine():
    url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, pool_pre_ping=True, future=True)

st.set_page_config(page_title="Carbon Dashboard", layout="wide")
st.title("🌍 Carbon Dashboard")

# --- basic stats
with _engine().connect() as conn:
    q_stats = text(f'''
        SELECT COUNT(*) AS rows,
               MIN(year) AS min_year,
               MAX(year) AS max_year,
               COUNT(DISTINCT iso_code) AS iso_codes
        FROM "{TABLE}";
    ''')
    stats = pd.read_sql(q_stats, conn)

st.sidebar.header("Filters")
with _engine().connect() as conn:
    countries = pd.read_sql(text(f'SELECT DISTINCT iso_code FROM "{TABLE}" WHERE iso_code IS NOT NULL ORDER BY iso_code'), conn)["iso_code"].tolist()
    years_txt = pd.read_sql(text(f'SELECT DISTINCT year FROM "{TABLE}" WHERE year IS NOT NULL'), conn)["year"].tolist()

# 연도 텍스트 중 숫자 4자리만 골라 정렬
year_numbers = sorted({int(y) for y in years_txt if re.fullmatch(r"\d{4}", str(y))})

iso = st.sidebar.selectbox("ISO Code", ["(All)"] + countries, index=0)
year_from, year_to = (min(year_numbers), max(year_numbers)) if year_numbers else (None, None)
yr = st.sidebar.slider("Year (numeric only)", min_value=year_from or 1900, max_value=year_to or 2100,
                       value=(year_from or 1900, year_to or 2100))

st.subheader("Overview")
st.write(stats)

# --- time series (co2_mt)
filters = []
params = {}
if iso != "(All)":
    filters.append('iso_code = :iso')
    params["iso"] = iso
filters.append("year ~ '^\\d{4}$'")
filters.append("year::int BETWEEN :y1 AND :y2")
params["y1"], params["y2"] = yr

where = "WHERE " + " AND ".join(filters)
sql_ts = text(f'''
    SELECT iso_code, year::int AS year, co2_mt, total_ghg_100y, population, gdp
    FROM "{TABLE}"
    {where}
    ORDER BY year
''')

with _engine().connect() as conn:
    ts = pd.read_sql(sql_ts, conn, params=params)

col1, col2 = st.columns(2)
with col1:
    st.subheader("CO₂ (Mt) over time")
    st.line_chart(ts.set_index("year")["co2_mt"])

with col2:
    st.subheader("Total GHG (100y) over time")
    st.line_chart(ts.set_index("year")["total_ghg_100y"])

st.subheader("Top emitters (latest year)")
if not ts.empty:
    latest_year = ts["year"].max()
    with _engine().connect() as conn:
        top = pd.read_sql(text(f'''
            SELECT iso_code, year::int AS year, co2_mt
            FROM "{TABLE}"
            WHERE year ~ '^\\d{{4}}$' AND year::int = :ly
            ORDER BY co2_mt DESC NULLS LAST
            LIMIT 20
        '''), conn, params={"ly": int(latest_year)})
    st.dataframe(top, use_container_width=True)

st.caption("DB: "
           f"{DB_HOST}:{DB_PORT}/{DB_NAME}, table: {TABLE}")
