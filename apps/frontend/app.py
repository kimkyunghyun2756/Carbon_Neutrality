import streamlit as st
import pgs.dashboard as dashboard
import pgs.policyview as policy_view
import pgs.manual as manual
import pgs.csv_data as cd

st.set_page_config(page_title="Carbon Dashboard", layout="wide")

page = st.sidebar.radio("Pages", [
    "구축 매뉴얼",
    "데이터-정책 연계표",
    "CSV 전체 데이터",
    "Dashboard"
])

if page == "Dashboard":
    dashboard.render()
elif page == "데이터-정책 연계표":
    policy_view.render()
elif page == "구축 매뉴얼":
    manual.render()
elif page == "CSV 전체 데이터":
    cd.render_csv_page()
