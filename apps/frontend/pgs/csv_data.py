import streamlit as st
import pandas as pd

def render_csv_page():
    st.title("CSV 데이터 보기")

    # 깃허브 raw CSV URL
    csv_url = "https://raw.githubusercontent.com/kimkyunghyun2756/Carbon_Neutrality/main/data/raw/Data.csv"

    try:
        df = pd.read_csv(csv_url)
        st.write("### 데이터 미리보기")
        st.dataframe(df, use_container_width=True)

        st.write("### 기본 통계")
        st.write(df.describe())

    except Exception as e:
        st.error(f"CSV 파일을 불러오는 중 오류 발생: {e}")
