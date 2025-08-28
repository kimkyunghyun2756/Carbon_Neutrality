import os
import re
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from functools import lru_cache
from dotenv import load_dotenv

# --- env load
try:
    load_dotenv()
except Exception:
    pass

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
TABLE = os.getenv("CSV_TABLE")

@lru_cache(maxsize=1)
def _engine():
    url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, pool_pre_ping=True, future=True)

st.set_page_config(page_title="Carbon Dashboard", layout="wide")

# --- 페이지 선택
page = st.sidebar.radio("📑 Pages", [
    "🌍 Dashboard",
    "📊 데이터-정책 연계표"
])

# --- 기존 대시보드 페이지
if page == "🌍 Dashboard":
    st.title("🌍 Carbon Dashboard")

    # 기본 통계
    with _engine().connect() as conn:
        q_stats = text(f'''
            SELECT COUNT(*) AS rows,
                   MIN(year) AS min_year,
                   MAX(year) AS max_year,
                   COUNT(DISTINCT name) AS countries
            FROM "{TABLE}";
        ''')
        stats = pd.read_sql(q_stats, conn)

    st.sidebar.header("Filters")
    with _engine().connect() as conn:
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
    filters = []
    params = {}
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
                SELECT name, year::int AS year, co2_mt
                FROM "{TABLE}"
                WHERE year ~ '^\\d{{4}}$' AND year::int = :ly
                ORDER BY co2_mt DESC NULLS LAST
                LIMIT 20
            '''), conn, params={"ly": int(latest_year)})
        st.dataframe(top, use_container_width=True)

    st.caption("DB: "
            f"{DB_HOST}:{DB_PORT}/{DB_NAME}, table: {TABLE}")

# --- 새 정책 연계표 페이지
elif page == "📊 데이터-정책 연계표":
    st.title("📊 탄소중립 데이터와 정책 연계")

    # 데이터 정의
    data = {
        "카테고리": [
            "인구·경제", "총 배출 추세", "에너지원별 배출",
            "온실가스 종류별", "토지·흡수원", "효율/국민 체감 지표"
        ],
        "주요 컬럼": [
            "population, gdp, energy_per_gdp, co2_per_gdp",
            "co2, co2_growth_abs, co2_growth_prct, co2_including_luc, cumulative_co2, total_ghg_100y",
            "coal_co2, oil_co2, gas_co2, cement_co2, flaring_co2",
            "methane, nitrous_oxide, ghg_per_capita",
            "land_use_change_co2, cumulative_luc_co2",
            "co2_per_capita, *_per_capita 계열, co2_per_unit_energy"
        ],
        "정책 활용 목적": [
            "1인당 배출량, 경제성장 대비 탄소 효율, 저탄소 성장 정책 평가",
            "국가 온실가스 총량 및 증가율 모니터링, 감축로드맵 달성 여부 확인",
            "탈석탄 정책, 수송부문 전환(석유), 가스 전환, 산업부문 감축",
            "농업·폐기물 부문 정책(메탄, N₂O), 국제 비교(1인당 GHG)",
            "산림·토지 정책, 흡수원 확보 정책 성과",
            "국민 체감도, 국제 비교, 에너지 믹스 탈탄소화 평가"
        ]
    }

    df_policy = pd.DataFrame(data)

    # --- 동적 필터
    st.sidebar.header("정책 데이터 필터")
    cat_selected = st.sidebar.selectbox("카테고리 선택", ["(전체)"] + df_policy["카테고리"].tolist())

    if cat_selected == "(전체)":
        st.dataframe(df_policy, use_container_width=True)
    else:
        st.subheader(f"🔎 {cat_selected}")
        row = df_policy[df_policy["카테고리"] == cat_selected].iloc[0]
        st.markdown(f"**주요 컬럼:** `{row['주요 컬럼']}`")
        st.markdown(f"**정책 활용 목적:** {row['정책 활용 목적']}")