import streamlit as st
import pandas as pd

# Impostazioni pagina
st.set_page_config(page_title="MetaTrader Light", page_icon="📈", layout="centered")

# CSS personalizzato per ricreare lo stile MetaTrader in modalità chiara (bianca)
st.markdown("""
    <style>
    .main {
        background-color: #ffffff;
        color: #000000;
    }
    .stApp {
        background-color: #ffffff;
    }
    h1, h2, h3 {
        color: #000000;
    }
    .market-card {
        border-bottom: 1px solid #e0e0e0;
        padding: 10px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .symbol {
        font-weight: bold;
        font-size: 16px;
        color: #000000;
    }
    .spread {
        font-size: 12px;
        color: #666666;
    }
    .price-bid {
        color: #0055ff;
        font-weight: bold;
        font-size: 16px;
        text-align: right;
    }
    .price-ask {
        color: #ff0000;
        font-weight: bold;
        font-size: 16px;
        text-align: right;
    }
    </style>
""", unsafe_allow_html=True)

# Intestazione con Tab Simple / Advanced
col1, col2 = st.columns([3, 1])
with col1:
    tab_mode = st.radio("Modalità", ["Simple", "Advanced"], horizontal=True, label_visibility="collapsed")
with col2:
    if st.button("➕", use_container_width=True):
        st.toast("Aggiungi simbolo cliccato")

st.divider()

# Dati di mercato simulati (ispirati allo screenshot di destra)
data = [
    {"time": "12:11:45", "symbol": "EURUSD", "spread": 21, "bid": "1.1554⁶", "ask": "1.1556⁷", "low": "1.15483", "high": "1.15750"},
    {"time": "12:11:45", "symbol": "GBPUSD", "spread": 19, "bid": "1.3476⁰", "ask": "1.3477⁹", "low": "1.34493", "high": "1.34998"},
    {"time": "12:11:45", "symbol": "USDJPY", "spread": 24, "bid": "113.44⁰", "ask": "113.46⁴", "low": "113.341", "high": "113.656"},
    {"time": "12:11:43", "symbol": "USDCAD", "spread": 25, "bid": "1.2456⁶", "ask": "1.2459¹", "low": "1.24382", "high": "1.24643"},
    {"time": "12:11:44", "symbol": "USDCHF", "spread": 21, "bid": "0.9149⁷", "ask": "0.9151⁸", "low": "0.91162", "high": "0.91498"},
    {"time": "12:11:44", "symbol": "NZDUSD", "spread": 35, "bid": "0.7135³", "ask": "0.7138⁸", "low": "0.71022", "high": "0.71523"},
    {"time": "12:11:42", "symbol": "AUDUSD", "spread": 20, "bid": "0.7394⁸", "ask": "0.7396⁸", "low": "0.73832", "high": "0.74119"},
    {"time": "12:11:44", "symbol": "AUDNZD", "spread": 75, "bid": "1.0358⁸", "ask": "1.0366³", "low": "1.03555", "high": "1.04009"},
    {"time": "12:11:35", "symbol": "AUDCAD", "spread": 60, "bid": "0.9210⁰", "ask": "0.9216⁰", "low": "0.92000", "high": "0.92225"},
]

# Rendering della lista in stile MetaTrader Light
for row in data:
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        st.markdown(f"<span style='font-size: 11px; color: #888;'>{row['time']}</span><br><b style='font-size: 15px; color: #000;'>{row['symbol']}</b><br><span style='font-size: 12px; color: #666;'>Spread: {row['spread']}</span>", unsafe_allow_html=True)
    with c2:
        if tab_mode == "Advanced":
            st.markdown(f"<div style='text-align: right;'><span style='color: #0055ff; font-weight: bold; font-size: 16px;'>{row['bid']}</span><br><span style='font-size: 11px; color: #666;'>Low: {row['low']}</span></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align: right;'><span style='color: #0055ff; font-weight: bold; font-size: 16px;'>{row['bid']}</span></div>", unsafe_allow_html=True)
    with c3:
        if tab_mode == "Advanced":
            st.markdown(f"<div style='text-align: right;'><span style='color: #ff0000; font-weight: bold; font-size: 16px;'>{row['ask']}</span><br><span style='font-size: 11px; color: #666;'>High: {row['high']}</span></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align: right;'><span style='color: #ff0000; font-weight: bold; font-size: 16px;'>{row['ask']}</span></div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

# Barra di navigazione inferiore simulata
st.markdown("<br><br>", unsafe_allow_html=True)
nav1, nav2, nav3, nav4, nav5 = st.columns(5)
with nav1:
    st.markdown("<div style='text-align: center; color: #0055ff; font-size: 11px;'>📊<br><b>Quotes</b></div>", unsafe_allow_html=True)
with nav2:
    st.markdown("<div style='text-align: center; color: #888; font-size: 11px;'>📈<br>Chart</div>", unsafe_allow_html=True)
with nav3:
    st.markdown("<div style='text-align: center; color: #888; font-size: 11px;'>💱<br>Trade</div>", unsafe_allow_html=True)
with nav4:
    st.markdown("<div style='text-align: center; color: #888; font-size: 11px;'>🕒<br>History</div>", unsafe_allow_html=True)
with nav5:
    st.markdown("<div style='text-align: center; color: #888; font-size: 11px;'>⚙️<br>Settings</div>", unsafe_allow_html=True)
