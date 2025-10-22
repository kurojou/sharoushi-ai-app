import streamlit as st

# --- ページ設定 ---
st.set_page_config(
    page_title="OOG: 社労士向けAIアシスタント",
    page_icon="📄",
    layout="wide"
)

# --- Streamlit アプリケーションの定義 ---
st.title("OOG: 社労士向けAIアシスタント")
st.caption("On/Off Boarding Genius - 入退社手続きと就業規則改定を、AIで劇的に効率化するツール")

st.info("左のサイドバーから、実行したい機能を選択してください。")

st.subheader("機能一覧")
st.markdown("- [📄 入社・退職手続き](1_入社退職手続き)")
st.markdown("- [📖 就業規則の改正](2_就業規則の改正)")