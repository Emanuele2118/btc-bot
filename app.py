import streamlit as st
import json
import os
import pandas as pd

# Configurazione della pagina per adattarla al meglio agli schermi dei telefoni
st.set_page_config(
    page_title="BTC Bot Dashboard",
    page_icon="📈",
    layout="centered"
)

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

# Intestazione della Web App
st.title("🤖 BTC Trading Bot Dashboard")
st.markdown("Monitoraggio in tempo reale del portafoglio di simulazione 24/7.")

# Caricamento dati
portafoglio = carica_portafoglio()
saldo = portafoglio.get("saldo_usd", 10000.0)
lotti = portafoglio.get("lotti", [])
storico = portafoglio.get("storico_operazioni", [])

# Calcoli riassuntivi
capitale_investito_lotti = sum(l.get('spesa', 0) for l in lotti)
profitto_totale = sum(storico)

# --- METRICHE PRINCIPALI (Stile App Finanziaria) ---
col1, col2 = st.columns(2)
with col1:
    st.metric(label="💰 Saldo Disponibile", value=f"${saldo:,.2f}")
with col2:
    st.metric(label="📊 Capitale nei Lotti", value=f"${capitale_investito_lotti:,.2f}")

col3, col4 = st.columns(2)
with col3:
    st.metric(label="📦 Lotti Attivi", value=f"{len(lotti)} / 4")
with col4:
    st.metric(label="🏆 Profitto Chiuso", value=f"${profitto_totale:+,.2f}")

st.divider()

# --- DETTAGLIO LOTTI ATTIVI ---
st.subheader("📌 Posizioni Attive")

if len(lotti) > 0:
    for lotto in lotti:
        st.markdown(f"""
        - **Lotto #{lotto['id']}**
          - Prezzo d'entrata: **${lotto['prezzo_entrata']:,.2f}**
          - Quantità: `{lotto['quantita']:.4f} BTC`
          - Spesa totale: `${lotto['spesa']:,.2f}`
        """)
else:
    st.info("Nessun lotto attivo al momento. Il bot sta monitorando il mercato.")

st.divider()

# --- STORICO RECENTE ---
st.subheader("📜 Storico Operazioni Chiuse")
if len(storico) > 0:
    df_storico = pd.DataFrame(storico, columns=["Profitto ($)"])
    st.dataframe(df_storico.tail(10), use_container_width=True)
else:
    st.write("Nessuna operazione chiusa registrata di recente.")

st.divider()

# Pulsante di aggiornamento manuale
if st.button("🔄 Aggiorna Dati"):
    st.rerun()
