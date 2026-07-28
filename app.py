import streamlit as st
import pandas as pd
import requests

# Impostazioni pagina
st.set_page_config(page_title="MetaTrader Bot - Posizioni", page_icon="📈", layout="centered")

# CSS personalizzato per lo stile pulito e chiaro
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

GITHUB_JSON_URL = "https://raw.githubusercontent.com/Emanuele2118/btc-bot/main/portfolio.json"

@st.cache_data(ttl=10)
def load_data():
    try:
        res = requests.get(GITHUB_JSON_URL)
        portfolio = res.json() if res.status_code == 200 else None
    except:
        portfolio = None
        
    # Prendi il prezzo attuale di BTC in tempo reale
    btc_current_price = 63000.0
    try:
        price_res = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=3)
        if price_res.status_code == 200:
            data_price = price_res.json()
            btc_current_price = float(data_price.get("price", 63000.0))
    except:
        pass
        
    return portfolio, btc_current_price

data, current_btc_price = load_data()

# Titolo principale e schermata unica
st.markdown("<h3 style='color: #000000; font-size: 20px; margin-bottom: 20px;'>Posizioni Attive</h3>", unsafe_allow_html=True)

if not data:
    st.warning("⚠️ Impossibile connettersi a portfolio.json su GitHub.")
else:
    lotti = data.get("lotti", [])
    saldo_usd = data.get("saldo_usd", 0.0)
    
    if not lotti:
        st.info("Nessun lotto attivo al momento.")
    else:
        total_profit = 0.0
        
        for l in lotti:
            l_id = l.get("id", "-")
            prezzo_entrata = l.get("prezzo_entrata", 0.0)
            quantita = l.get("quantita", 0.0)
            spesa = l.get("spesa", 0.0)
            
            # Calcolo profitto/perdita stimato per singolo lotto (long/buy)
            profit_lotto = (current_btc_price - prezzo_entrata) * quantita
            total_profit += profit_lotto
            
            color_profit = "#34c759" if profit_lotto >= 0 else "#ff3b30"
            sign = "+" if profit_lotto >= 0 else ""
            
            st.markdown(f"""
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between;" class="trade-title">
                        <div>BTCUSD, <span style="color: #34c759;">BUY</span> <span style="color: #333333;">{quantita:.4f}</span></div>
                        <div style="color: {color_profit}; font-weight: bold;">{sign}${profit_lotto:,.2f}</div>
                    </div>
                    <div style="display: flex; justify-content: space-between;" class="trade-details">
                        <div>Entrata: <b>{prezzo_entrata:,.2f}</b> | Attuale: <b>{current_btc_price:,.2f}</b></div>
                        <div>ID: {l_id}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        deposit = data.get("valore_iniziale_giornata", 3000.0)
        total_color = "#34c759" if total_profit >= 0 else "#ff3b30"
        total_sign = "+" if total_profit >= 0 else ""

        st.markdown(f"""
            <div class="summary-box">
                <div class="summary-row"><span>Valore Iniziale</span><span>{deposit:,.2f}</span></div>
                <div class="summary-row"><span>Profitto Operazioni (P&L)</span><span style="color: {total_color}; font-weight: bold;">{total_sign}${total_profit:,.2f}</span></div>
                <div class="summary-row" style="font-weight: bold; border-top: 1px solid #ddd; margin-top: 6px; padding-top: 6px;">
                    <span style="color: #000000;">Saldo USD (Balance)</span><span style="color: #007aff; font-size: 16px;">{saldo_usd:,.2f}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
