import re
import pandas as pd
import streamlit as st
from sqlalchemy import text
from db import get_engine
from utils.config import TABLE, DB_HOST, DB_PORT, DB_NAME

def render():
    st.title("🌍 Carbon Dashboard")

    # 기본 통계
    with get_engine().connect() as conn:
        q_stats = text(f'''
            SELECT COUNT(*) AS rows,
                   MIN(year) AS min_year,
                   MAX(year) AS max_year,
                   COUNT(DISTINCT name) AS countries
            FROM "{TABLE}";
        ''')
        stats = pd.read_sql(q_stats, conn)

    st.sidebar.header("Filters")
    with get_engine().connect() as conn:
        countries = pd.read_sql(
            text(f'SELECT DISTINCT name FROM "{TABLE}" WHERE name IS NOT NULL ORDER BY name'),
            conn
        )["name"].tolist()
        years_txt = pd.read_sql(
            text(f'SELECT DISTINCT year FROM "{TABLE}" WHERE year IS NOT NULL'),
            conn
        )["year"].tolist()

    year_numbers = sorted({int(y) for y in years_txt if re.fullmatch(r"\d{4}", str(y))})
    iso = st.sidebar.selectbox("Country (Name)", ["(All)"] + countries, index=0)
    year_from, year_to = (min(year_numbers), max(year_numbers)) if year_numbers else (None, None)
    yr = st.sidebar.slider("Year (numeric only)", min_value=year_from or 1900, max_value=year_to or 2100,
                        value=(year_from or 1900, year_to or 2100))

    st.subheader("Overview")
    st.write(stats)

    # 시계열
    filters, params = [], {}
    if iso != "(All)":
        filters.append('name = :nm')
        params["nm"] = iso
    filters.append("year ~ '^\\d{4}$'")
    filters.append("year::int BETWEEN :y1 AND :y2")
    params["y1"], params["y2"] = yr

    where = "WHERE " + " AND ".join(filters)
    sql_ts = text(f'''
        SELECT name, year::int AS year, co2_mt, total_ghg_100y, population, gdp
        FROM "{TABLE}"
        {where}
        ORDER BY year
    ''')

    with get_engine().connect() as conn:
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
        with get_engine().connect() as conn:
            top = pd.read_sql(text(f'''
                SELECT name, year::int AS year, co2_mt
                FROM "{TABLE}"
                WHERE year ~ '^\\d{{4}}$' AND year::int = :ly
                ORDER BY co2_mt DESC NULLS LAST
                LIMIT 20
            '''), conn, params={"ly": int(latest_year)})
        st.dataframe(top, use_container_width=True)

    st.caption(f"DB: {DB_HOST}:{DB_PORT}/{DB_NAME}, table: {TABLE}")
