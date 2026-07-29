import os
import json
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timezone

# Prova a importare la libreria per l'auto-refresh
try:
    from streamlit_autorefresh import st_autorefresh
    has_autorefresh = True
except ImportError:
    has_autorefresh = False

# ==================== CONFIGURAZIONE PAGINA ====================
st.set_page_config(page_title="BTC Bot Dashboard", page_icon="📈", layout="wide")

PORTFOLIO_FILE = "portfolio.json"
CAPITALE_INIZIALE = 10000.0

# ==================== FUNZIONI DI SUPPORTO ====================
def carica_portafoglio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            st.error(f"Errore nella lettura del file portafoglio: {e}")
    
    # Valori di default se il file non esiste
    return {
        "saldo_usd": CAPITALE_INIZIALE,
        "lotti": [],
        "valore_iniziale_giornata": CAPITALE_INIZIALE,
        "storico_operazioni": []
    }

def ottieni_prezzo_corrente():
    # Prova Coinbase
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return float(res.json().get('price'))
    except:
        pass

    # Fallback su Binance
    try:
        url_binance = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        res = requests.get(url_binance, timeout=5)
        if res.status_code == 200:
            return float(res.json().get('price'))
    except:
        pass

    return 63000.0  # Valore di sicurezza se le API falliscono

# ==================== INTERFACCIA STREAMLIT ====================

# Configura l'aggiornamento automatico ogni 10 secondi (10000 ms) se disponibile
if has_autorefresh:
    st_autorefresh(interval=10000, key="live_update_counter")

st.title("📊 Monitoraggio Bot in Tempo Reale")

# Sidebar per controlli rapidi
with st.sidebar:
    st.header("⚙️ Controlli")
    if st.button("🔄 Aggiorna Ora"):
        st.rerun()
    st.markdown("---")
    if has_autorefresh:
        st.success("🟢 Auto-refresh attivo (ogni 10s)")
    else:
        st.warning("⚠️ Installa `streamlit-autorefresh` per l'aggiornamento automatico live.")

# Caricamento dati aggiornati dal file JSON e prezzo live da API
portafoglio = carica_portafoglio()
prezzo_attuale = ottieni_prezzo_corrente()

lotti = portafoglio.get("lotti", [])
saldo_usd = portafoglio.get("saldo_usd", CAPITALE_INIZIALE)

# Calcoli in tempo reale
q_tot = sum(l['quantita'] for l in lotti)
spesa_tot = sum(l['spesa'] for l in lotti)
prezzo_medio = (spesa_tot / q_tot) if q_tot > 0 else 0.0
valore_posizioni = q_tot * prezzo_attuale
valore_totale_portafoglio = saldo_usd + valore_posizioni

# PnL complessivo delle operazioni chiuse salvate nello storico
storico = portafoglio.get("storico_operazioni", [])
profitto_operazioni_chiuse = sum(storico)

# ==================== SEZIONE POSIZIONI ATTIVE ====================
st.subheader("Posizioni Attive")

if not lotti:
    st.info("Nessun lotto attivo al momento. Il bot è in attesa di segnali d'ingresso.")
else:
    for lotto in lotti:
        p_entrata = lotto['prezzo_entrata']
        q_lotto = lotto['quantita']
        spesa_lotto = lotto['spesa']
        id_lotto = lotto['id']
        
        valore_attuale_lotto = q_lotto * prezzo_attuale
        pnl_lotto = valore_attuale_lotto - spesa_lotto
        pnl_lotto_perc = (pnl_lotto / spesa_lotto) * 100 if spesa_lotto > 0 else 0
        
        col1, col2 = st.columns([3, 1])
        with col1:
            colore_testo = "green" if pnl_lotto >= 0 else "red"
            st.markdown(
                f"**BTCUSD**, BUY `{q_lotto:.4f}`\n\n"
                f"<span style='color:gray; font-size:0.9em;'>Entrata: ${p_entrata:,.2f} | Attuale: ${prezzo_attuale:,.2f}</span>",
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                f"<div style='text-align: right;'>"
                f"<span style='color:{colore_testo}; font-weight: bold; font-size: 1.1em;'>${pnl_lotto:+,.2f}</span><br>"
                f"<span style='color:gray; font-size: 0.8em;'>ID: {id_lotto}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.divider()

# ==================== SEZIONE RIEPILOGO FINANZIARIO ====================
st.markdown("### Riepilogo")

valore_iniziale = portafoglio.get("valore_iniziale_giornata", CAPITALE_INIZIALE)

colore_pnl = "green" if profitto_operazioni_chiuse >= 0 else "red"

st.markdown(
    f"""
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <span style="color: #333; font-weight: 500;">Valore Iniziale Giornata</span>
            <span style="font-weight: 600;">${valore_iniziale:,.2f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <span style="color: #333; font-weight: 500;">Profitto Operazioni Chiuse (P&L)</span>
            <span style="color: {colore_pnl}; font-weight: 600;">${profitto_operazioni_chiuse:+,.2f}</span>
        </div>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 10px 0;">
        <div style="display: flex; justify-content: space-between;">
            <span style="color: #111; font-weight: bold; font-size: 1.1em;">Saldo USD (Balance)</span>
            <span style="color: #0066cc; font-weight: bold; font-size: 1.1em;">${saldo_usd:,.2f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 8px;">
            <span style="color: #111; font-weight: bold; font-size: 1.1em;">Valore Totale Portafoglio</span>
            <span style="color: #222; font-weight: bold; font-size: 1.1em;">${valore_totale_portafoglio:,.2f}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
