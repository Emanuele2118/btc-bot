import streamlit as st
import json
import os
import pandas as pd
import requests

# Configurazione della pagina (stile terminale finanziario)
st.set_page_config(
    page_title="Trading - BTC/USD",
    page_icon="📈",
    layout="centered"
)

# --- STILE CSS PERSONALIZZATO (TEMA METATRADER DARK) ---
st.markdown("""
<style>
    /* Sfondo generale scuro stile MetaTrader */
    .stApp {
        background-color: #121212;
        color: #e0e0e0;
    }
    
    /* Box delle metriche */
    div[data-testid="stMetric"] {
        background-color: #1e1e1e;
        border: 1px solid #2d2d2d;
        padding: 12px;
        border-radius: 6px;
    }
    div[data-testid="stMetric"] label {
        color: #9e9e9e !important;
        font-size: 13px !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 20px !important;
        font-weight: 600;
    }

    /* Tab personalizzate */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #121212;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1e1e1e;
        border-radius: 4px;
        color: #b0b0b0;
        padding: 8px 16px;
        border: 1px solid #2d2d2d;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2a2a2a !important;
        color: #ffffff !important;
        border-color: #00acc1 !important;
    }

    /* Titoli e separatori */
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    hr {
        border-color: #2d2d2d;
    }
    
    /* Pulsanti */
    .stButton button {
        background-color: #2196f3;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: 600;
        width: 100%;
    }
    .stButton button:hover {
        background-color: #1976d2;
    }
</style>
""", unsafe_allow_html=True)

PORTFOLIO_FILE = "portfolio.json"

def carica_portafoglio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "saldo_usd": 10000.0,
        "lotti": [],
        "storico_operazioni": []
    }

# Funzione per recuperare il prezzo live di BTC al momento dell'apertura dell'app
@st.cache_data(ttl=15)
def ottieni_prezzo_live():
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return float(res.json().get('price', 0))
    except:
        pass
    return 0.0

# --- INTESTAZIONE STILE PIATTAFORMA ---
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown("### 📊 BTC/USD (Simulatore)")
with col_head2:
    prezzo_live = ottieni_prezzo_live()
    if prezzo_live > 0:
        st.markdown(f"<h3 style='text-align: right; color: #26a69a !important;'>${prezzo_live:,.2f}</h3>", unsafe_allow_html=True)

portafoglio = carica_portafoglio()
saldo = portafoglio.get("saldo_usd", 10000.0)
lotti = portafoglio.get("lotti", [])
storico = portafoglio.get("storico_operazioni", [])

# Calcoli finanziari
capitale_lotti = sum(l.get('spesa', 0) for l in lotti)
valore_attuale_posizioni = sum(l['quantita'] * prezzo_live for l in lotti) if prezzo_live > 0 else capitale_lotti
profitto_aperte = valore_attuale_posizioni - capitale_lotti if prezzo_live > 0 else 0.0
equity_totale = saldo + valore_attuale_posizioni
profitto_chiuso = sum(storico)

# --- BILANCIO / CONTO (Stile Header Account MT) ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Saldo", value=f"${saldo:,.2f}")
with col2:
    st.metric(label="Equity", value=f"${equity_totale:,.2f}")
with col3:
    col_pnl_color = "#26a69a" if profitto_aperte >= 0 else "#ef5350"
    st.metric(label="Profitto Aperto", value=f"${profitto_aperte:+,.2f}")

st.divider()

# --- SEZIONI A SCHEDE (Tab stile MetaTrader: Posizioni / Storico) ---
tab_posizioni, tab_storico, tab_info = st.tabs(["📌 Posizioni Attive", "📜 Storico", "⚙️ Account"])

with tab_posizioni:
    st.markdown(f"**Lotti attivi:** {len(lotti)} / 4")
    
    if len(lotti) > 0:
        for lotto in lotti:
            p_entrata = lotto['prezzo_entrata']
            qta = lotto['quantita']
            valore_attuale_lotto = qta * prezzo_live if prezzo_live > 0 else lotto['spesa']
            pnl_lotto = valore_attuale_lotto - lotto['spesa']
            pnl_perc = (pnl_lotto / lotto['spesa']) * 100 if lotto['spesa'] > 0 else 0
            
            colore_pnl = "#26a69a" if pnl_lotto >= 0 else "#ef5350"
            
            st.markdown(f"""
            <div style="background-color: #1e1e1e; padding: 12px; border-radius: 6px; border-left: 4px solid {colore_pnl}; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; font-weight: bold;">
                    <span>Lotto #{lotto['id']} (BTC)</span>
                    <span style="color: {colore_pnl};">${pnl_lotto:+,.2f} ({pnl_perc:+.2f}%)</span>
                </div>
                <div style="font-size: 13px; color: #b0b0b0; margin-top: 6px;">
                    <div>Quantità: <b>{qta:.4f} BTC</b></div>
                    <div>Prezzo Apertura: <b>${p_entrata:,.2f}</b></div>
                    <div>Valore Attuale: <b>${valore_attuale_lotto:,.2f}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nessuna posizione aperta al momento.")

with tab_storico:
    st.markdown(f"**Profitto Chiuso Totale:** <span style='color: {'#26a69a' if profitto_chiuso >= 0 else '#ef5350'};'>${profitto_chiuso:+,.2f}</span>", unsafe_allow_html=True)
    st.markdown("---")
    
    if len(storico) > 0:
        for idx, op in enumerate(reversed(storico[-15:])):
            colore_op = "#26a69a" if op >= 0 else "#ef5350"
            st.markdown(f"""
            <div style="background-color: #1e1e1e; padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #b0b0b0; font-size: 13px;">Operazione #{len(storico) - idx}</span>
                <span style="color: {colore_op}; font-weight: bold; font-size: 14px;">${op:+,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("Nessuna operazione chiusa registrata.")

with tab_info:
    st.markdown("### Dettagli Simulator")
    st.markdown(f"• **Capitale Iniziale:** $10,000.00")
    st.markdown(f"• **Capitale per Lotto:** $2,500.00")
    st.markdown(f"• **Lotti Massimi:** 4")
    
    if st.button("🔄 Aggiorna Dati"):
        st.rerun()
