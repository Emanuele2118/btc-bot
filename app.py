import streamlit as st
import pandas as pd

# Impostazioni pagina
st.set_page_config(page_title="MetaTrader Bot History", page_icon="📈", layout="centered")

# CSS personalizzato per lo stile MetaTrader in modalità chiara (bianca)
st.markdown("""
    <style>
    .main {
        background-color: #ffffff;
        color: #000000;
    }
    .stApp {
        background-color: #ffffff;
    }
    .header-tabs {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #f7f7f7;
        padding: 8px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    .trade-card {
        background-color: #ffffff;
        border-bottom: 1px solid #eeeeee;
        padding: 10px 0;
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
        color: #666666;
    }
    .summary-row span:last-child {
        color: #000000;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

# Tab di navigazione superiore (Positions, Orders, Deals)
tab1, tab2, tab3 = st.tabs(["Positions", "Orders", "Deals"])

with tab1:
    # --- INSERISCI QUI I DATI DEL TUO BOT ---
    # Puoi collegare questo dataframe al tuo foglio Google Sheets o al database del tuo bot
    trades_data = [
        {"symbol": "BTCUSD", "type": "sell", "volume": 0.25, "open": 64250.00, "close": 63100.00, "profit": 287.50, "date": "2026.07.28 11:29:19"},
        {"symbol": "BTCUSD", "type": "sell", "volume": 0.25, "open": 64100.00, "close": 63500.00, "profit": 150.00, "date": "2026.07.28 12:15:40"},
        {"symbol": "BTCUSD", "type": "buy", "volume": 0.50, "open": 62800.00, "close": 63400.00, "profit": 300.00, "date": "2026.07.28 14:02:10"},
    ]

    # Calcoli finanziari dinamici basati sulle operazioni del bot
    deposit = 3000.00
    total_profit = sum(t["profit"] for t in trades_data)
    swap = -4.50
    commission = 0.00
    balance = deposit + total_profit + swap + commission

    # Render delle operazioni stile MetaTrader
    for t in trades_data:
        color_type = "#ff3b30" if t["type"] == "sell" else "#34c759"
        color_profit = "#007aff" if t["profit"] >= 0 else "#ff3b30"
        
        st.markdown(f"""
            <div class="trade-card">
                <div style="display: flex; justify-content: space-between; font-weight: 600; font-size: 14px;">
                    <div>{t['symbol']}, <span style="color: {color_type};">{t['type']}</span> {t['volume']}</div>
                    <div style="color: {color_profit};">{t['profit']:+.2f}</div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; color: #666666; margin-top: 4px;">
                    <div>{t['open']} → {t['close']}</div>
                    <div>{t['date']}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Box Riepilogo Finanziario in basso
    st.markdown(f"""
        <div class="summary-box">
            <div class="summary-row"><span>Deposit</span><span>{deposit:,.2f}</span></div>
            <div class="summary-row"><span>Profit</span><span style="color: #007aff;">{total_profit:,.2f}</span></div>
            <div class="summary-row"><span>Swap</span><span>{swap:,.2f}</span></div>
            <div class="summary-row"><span>Commission</span><span>{commission:,.2f}</span></div>
            <div class="summary-row" style="font-weight: bold; border-top: 1px solid #ddd; margin-top: 6px; padding-top: 6px;">
                <span>Balance</span><span style="color: #007aff; font-size: 16px;">{balance:,.2f}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

with tab2:
    st.info("Nessun ordine pendente al momento.")

with tab3:
    st.info("Storico deal completati sincronizzato con il bot.")

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
