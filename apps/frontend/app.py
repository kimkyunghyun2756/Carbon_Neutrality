import streamlit as st
import pages.dashboard as dashboard
import pages.policyview as policy_view
import pages.manual as manual

st.set_page_config(page_title="Carbon Dashboard", layout="wide")

page = st.sidebar.radio("📑 Pages", [
    "🌍 Dashboard",
    "📊 데이터-정책 연계표",
    "🛠 구축 매뉴얼"
])

if page == "🌍 Dashboard":
    dashboard.render()
elif page == "📊 데이터-정책 연계표":
    policy_view.render()
elif page == "🛠 구축 매뉴얼":
    manual.render()
