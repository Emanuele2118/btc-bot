import streamlit as st
import pandas as pd
import requests

# Impostazioni pagina
st.set_page_config(page_title="MetaTrader Bot History", page_icon="📈", layout="centered")

# CSS personalizzato per correggere i colori del testo in modalità chiara (bianca)
st.markdown("""
    <style>
    .main {
        background-color: #ffffff;
        color: #000000;
    }
    .stApp {
        background-color: #ffffff;
    }
    .trade-card {
        background-color: #ffffff;
        border-bottom: 1px solid #eeeeee;
        padding: 12px 0;
    }
    .trade-title {
        font-weight: 600;
        font-size: 14px;
        color: #000000;
    }
    .trade-details {
        font-size: 12px;
        color: #555555;
        margin-top: 4px;
    }
    .summary-box {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-top: 20px;
    }
    .summary-row {
        display: flex;
        justify-content: space-between;
        font-size: 14px;
        padding: 4px 0;
        color: #444444;
    }
    .summary-row span:last-child {
        color: #000000;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

# URL Raw del file portfolio.json su GitHub
GITHUB_JSON_URL = "https://raw.githubusercontent.com/Emanuele2118/btc-bot/main/portfolio.json"

@st.cache_data(ttl=30)
def load_portfolio_data():
    try:
        response = requests.get(GITHUB_JSON_URL)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        pass
    return None

data = load_portfolio_data()

# Tab di navigazione superiore
tab1, tab2, tab3 = st.tabs(["Positions", "Orders", "Deals"])

with tab1:
    if not data:
        st.warning("⚠️ Impossibile connettersi a portfolio.json su GitHub.")
    else:
        saldo_usd = data.get("saldo_usd", 0.0)
        lotti = data.get("Lotti", [])
        
        st.markdown("<h3 style='color: #000000; font-size: 18px;'>Posizioni Attive (Lotti)</h3>", unsafe_allow_html=True)
        
        if not lotti:
            st.info("Nessun lotto attivo al momento.")
        else:
            for l in lotti:
                l_id = l.get("id", "-")
                prezzo = l.get("prezzo_entrata", l.get("prezzo", 0.0))
                quantita = l.get("quantita", 0.0)
                spesa = l.get("spesa", 0.0)
                
                st.markdown(f"""
                    <div class="trade-card">
                        <div style="display: flex; justify-content: space-between;" class="trade-title">
                            <div>BTCUSD, <span style="color: #34c759;">BUY</span> <span style="color: #333333;">{quantita}</span></div>
                            <div style="color: #007aff;">ID: {l_id}</div>
                        </div>
                        <div style="display: flex; justify-content: space-between;" class="trade-details">
                            <div>Prezzo Entrata: <b>{prezzo}</b></div>
                            <div>Spesa: <b>${spesa:,.2f}</b></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        deposit = data.get("valore_iniziale_giornata", 3000.0)
        balance = saldo_usd

        st.markdown(f"""
            <div class="summary-box">
                <div class="summary-row"><span>Valore Iniziale</span><span>{deposit:,.2f}</span></div>
                <div class="summary-row" style="font-weight: bold; border-top: 1px solid #ddd; margin-top: 6px; padding-top: 6px;">
                    <span style="color: #000000;">Saldo USD (Balance)</span><span style="color: #007aff; font-size: 16px;">{balance:,.2f}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

with tab2:
    st.info("Nessun ordine pendente.")

with tab3:
    st.info("Storico operazioni sincronizzato dal bot.")

# Barra di navigazione inferiore stile app mobile
st.markdown("<br><br>", unsafe_allow_html=True)
nav1, nav2, nav3, nav4, nav5 = st.columns(5)
with nav1:
    st.markdown("<div style='text-align: center; color: #666; font-size: 11px;'>📊<br>Quotes</div>", unsafe_allow_html=True)
with nav2:
    st.markdown("<div style='text-align: center; color: #666; font-size: 11px;'>📈<br>Chart</div>", unsafe_allow_html=True)
with nav3:
    st.markdown("<div style='text-align: center; color: #666; font-size: 11px;'>💱<br>Trade</div>", unsafe_allow_html=True)
with nav4:
    st.markdown("<div style='text-align: center; color: #007aff; font-size: 11px;'>🕒<br><b>History</b></div>", unsafe_allow_html=True)
with nav5:
    st.markdown("<div style='text-align: center; color: #666; font-size: 11px;'>⚙️<br>Settings</div>", unsafe_allow_html=True)
