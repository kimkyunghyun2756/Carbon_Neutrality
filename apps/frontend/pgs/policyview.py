import pandas as pd
import streamlit as st
import altair as alt
from sqlalchemy import text
from db import get_engine
from utils.config import TABLE

CATEGORY_COLUMNS = {
    "인구·경제": ["population", "gdp", "energy_per_gdp_kwh", "co2_per_gdp_kg"],
    "총 배출 추세": ["co2_mt", "co2_including_luc_mt", "cumulative_co2_mt", "total_ghg_100y"],
    "에너지원별 배출": ["coal_co2_mt", "oil_co2_mt", "gas_co2_mt", "cement_co2_mt", "flaring_co2_mt"],
    "온실가스 종류별": ["methane_100y_t", "nitrous_oxide_100y_t", "ghg_per_capita_100y"],
    "토지·흡수원": ["land_use_change_co2_mt", "cumulative_luc_co2_mt"],
    "효율/국민 체감 지표": ["co2_per_capita_t", "co2_per_unit_energy_kw_kwh"]
}

def render():
    st.title("탄소중립 데이터와 정책 연계")

    st.sidebar.header("정책 데이터 필터")
    cat_selected = st.sidebar.selectbox("카테고리 선택", list(CATEGORY_COLUMNS.keys()))

    cols = CATEGORY_COLUMNS[cat_selected]

    # DB에서 대한민국 데이터 전체 가져오기
    sql = text(f'''
        SELECT year::int AS year, {",".join(cols)}
        FROM "{TABLE}"
        WHERE name = 'South Korea' AND year ~ '^\\d{{4}}$'
        ORDER BY year
    ''')
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn)

    st.subheader(f"🇰🇷 대한민국 - {cat_selected}")
    st.write("전체 연도 데이터")
    st.dataframe(df, use_container_width=True)

    # 시각화
    st.markdown("### 시각화")
    for c in cols:
        if c in df.columns:
            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("year:O", title="연도"),
                    y=alt.Y(f"{c}:Q", title=c),
                    tooltip=["year", c]
                )
                .properties(
                    title=f"{c} 추세 (대한민국)",
                    width=600,
                    height=300
                )
            )
            st.altair_chart(chart, use_container_width=True)
