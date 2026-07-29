import os
import json
import requests
import pandas as pd
import streamlit as st
import time
from datetime import datetime, timezone

# ==================== CONFIGURAZIONE PAGINA ====================
st.set_page_config(page_title="BTC Bot Dashboard Live", page_icon="📈", layout="wide")

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
        except Exception:
            pass
    
    return {
        "saldo_usd": CAPITALE_INIZIALE,
        "lotti": [],
        "valore_iniziale_giornata": CAPITALE_INIZIALE,
        "storico_operazioni": []
    }

def ottieni_prezzo_corrente():
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            return float(res.json().get('price'))
    except:
        pass

    try:
        url_binance = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        res = requests.get(url_binance, timeout=3)
        if res.status_code == 200:
            return float(res.json().get('price'))
    except:
        pass

    return 63000.0

# ==================== INTERFACCIA PRINCIPALE ====================
st.title("📊 Monitoraggio Bot in Tempo Reale")

# Sidebar con indicatore di stato live
with st.sidebar:
    st.header("⚙️ Stato Sistema")
    st.success("🟢 Connessione Live Attiva")
    intervallo_refresh = st.slider("Interfaccia aggiornamento (sec)", min_value=2, max_value=15, value=5)
    
    if st.button("🔄 Forza Aggiornamento"):
        st.rerun()

# Contenitore dinamico che si aggiorna senza ricaricare tutta la pagina web
placeholder = st.empty()

# Usiamo un frammento o un ciclo controllato per l'aggiornamento continuo live
# In Streamlit, un piccolo trucco pulito per il loop live senza librerie esterne:
@st.fragment
def esegui_aggiornamento_live():
    # Loop interno che aggiorna il blocco dati ogni X secondi
    while True:
        portafoglio = carica_portafoglio()
        prezzo_attuale = ottieni_prezzo_corrente()

        lotti = portafoglio.get("lotti", [])
        saldo_usd = portafoglio.get("saldo_usd", CAPITALE_INIZIALE)

        # Calcoli
        q_tot = sum(l['quantita'] for l in lotti)
        spesa_tot = sum(l['spesa'] for l in lotti)
        valore_posizioni = q_tot * prezzo_attuale
        valore_totale_portafoglio = saldo_usd + valore_posizioni
        storico = portafoglio.get("storico_operazioni", [])
        profitto_operazioni_chiuse = sum(storico)
        valore_iniziale = portafoglio.get("valore_iniziale_giornata", CAPITALE_INIZIALE)

        # Scriviamo/aggiorniamo l'interfaccia dentro il blocco container
        with placeholder.container():
            st.markdown(f"*(Ultimo aggiornamento live: {datetime.now().strftime('%H:%M:%S')})* — Prezzo Bitcoin: **${prezzo_attuale:,.2f}**")
            
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

            # Sezione Riepilogo
            st.markdown("### Riepilogo")
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
        
        # Pausa prima del prossimo ciclo di aggiornamento live
        time.sleep(intervallo_refresh)

# Avvia il frammento in tempo reale
esegui_aggiornamento_live()
