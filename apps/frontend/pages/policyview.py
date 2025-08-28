import pandas as pd
import streamlit as st
from sqlalchemy import text
from db import get_engine
from utils.config import TABLE

CATEGORY_COLUMNS = {
    "인구·경제": ["population", "gdp", "energy_per_gdp", "co2_per_gdp"],
    "총 배출 추세": ["co2_mt", "co2_including_luc", "cumulative_co2", "total_ghg_100y"],
    "에너지원별 배출": ["coal_co2", "oil_co2", "gas_co2", "cement_co2", "flaring_co2"],
    "온실가스 종류별": ["methane", "nitrous_oxide", "ghg_per_capita"],
    "토지·흡수원": ["land_use_change_co2", "cumulative_luc_co2"],
    "효율/국민 체감 지표": ["co2_per_capita", "co2_per_unit_energy"]
}

def render():
    st.title("📊 탄소중립 데이터와 정책 연계")

    st.sidebar.header("정책 데이터 필터")
    cat_selected = st.sidebar.selectbox("카테고리 선택", list(CATEGORY_COLUMNS.keys()))

    # DB에서 대한민국 데이터 가져오기
    cols = CATEGORY_COLUMNS[cat_selected]
    sql = text(f'''
        SELECT year::int AS year, {",".join(cols)}
        FROM "{TABLE}"
        WHERE name = 'South Korea' AND year ~ '^\\d{{4}}$'
        ORDER BY year
    ''')
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn)

    st.subheader(f"🇰🇷 대한민국 - {cat_selected}")
    st.dataframe(df.tail(10), use_container_width=True)

    # 시각화
    for c in cols:
        if c in df.columns:
            st.line_chart(df.set_index("year")[c], height=250)
