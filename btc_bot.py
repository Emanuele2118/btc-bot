import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ==================== CONFIGURAZIONE ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL") # Opzionale per log esterni

PORTFOLIO_FILE = "portfolio.json"

# Configurazione Capitale e Strategia
CAPITALE_INIZIALE = 10000.0  # USD totali allocati per il paper trading
CAPITALE_PER_LOTTO = 5000.0   # USD per ogni lotto (max 2 lotti)

# ==================== GESTIONE PORTAFOGLIO ====================
def carica_portafoglio():
    """Carica lo stato dei lotti dal file JSON persistente o inizializza lo stato predefinito."""
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Errore nella lettura del portafoglio: {e}")
    
    # Stato iniziale di default (Portafoglio vuoto)
    return {
        "saldo_usd": CAPITALE_INIZIALE,
        "lotti": []  # Lista dei lotti attivi
    }

def salva_portafoglio(portafoglio):
    """Salva lo stato corrente dei lotti nel file JSON."""
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portafoglio, f, indent=4)
    except Exception as e:
        print(f"Errore nel salvataggio del portafoglio: {e}")

# ==================== RECUPERO DATI DI MERCATO CON FALLBACK ====================
def ottieni_dati_binance():
    """Scarica i dati storici da Binance, con fallback su CoinGecko se Binance fallisce."""
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=150"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if len(data) >= 50:
                df = pd.DataFrame(data, columns=[
                    'Time', 'Open', 'High', 'Low', 'Close', 'Volume',
                    'CloseTime', 'QuoteAssetVolume', 'NumberOfTrades',
                    'TakerBuyBaseAssetVolume', 'TakerBuyQuoteAssetVolume', 'Ignore'
                ])
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = df[col].astype(float)
                df['Time'] = df['Time'] / 1000.0
                return df
    except Exception as e:
        print(f"Errore connessione Binance: {e}")

    print("Tentativo fallback su CoinGecko...")
    try:
        url_cg = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc?vs_currency=usd&days=7"
        resp = requests.get(url_cg, timeout=10)
        if resp.status_code == 200:
            cg_data = resp.json()
            df = pd.DataFrame(cg_data, columns=['Time', 'Open', 'High', 'Low', 'Close'])
            df['Time'] = df['Time'] / 1000.0
            df['Volume'] = 1000.0
            return df
    except Exception as e:
        print(f"Errore anche nel fallback CoinGecko: {e}")
        
    return None

# ==================== INDICATORI TECNICI ====================
def calcola_rsi(serie, periodo=14):
    delta = serie.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periodo).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periodo).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calcola_atr(df, periodo=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=periodo).mean()

# ==================== GENERAZIONE GRAFICO CON LIVELLI ====================
def genera_grafico_chart(df, rsi_attuale, prezzo_attuale, stato_testo, prezzo_medio=0.0, stop_loss_perc=0.0):
    """Genera un grafico a candele con livelli operativi (Prezzo Medio e Stop Loss) visibili."""
    try:
        fig = plt.figure(figsize=(10, 7.5), facecolor='white')
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1.3])
        
        # --- PANNELLO 1: GRAFICO A CANDELE & LIVELLI DI STRATEGIA ---
        ax1 = fig.add_subplot(gs[0])
        ax1.set_facecolor('white')
        
        dati_plot = df.tail(100).copy().reset_index(drop=True)
        x = range(len(dati_plot))
        
        # Disegno delle candele (Verde se Close >= Open, Viola se Close < Open)
        for i in x:
            o = dati_plot['Open'].iloc[i]
            c = dati_plot['Close'].iloc[i]
            h = dati_plot['High'].iloc[i]
            l = dati_plot['Low'].iloc[i]
            
            colore = '#26a69a' if c >= o else '#9c27b0'
            
            ax1.plot([i, i], [l, h], color=colore, linewidth=1, zorder=1)
            bottom = min(o, c)
            height = abs(c - o) if abs(c - o) > 0 else 0.01
            ax1.bar(i, height, bottom=bottom, color=colore, width=0.6, zorder=2)

        # Medie mobili
        ax1.plot(x, dati_plot['ema_veloce'], label='EMA 9 (Veloce)', color='#ff9800', linewidth=1.2, linestyle='--')
        ax1.plot(x, dati_plot['ema_lenta'], label='EMA 50 (Lenta)', color='#3f51b5', linewidth=1.2, linestyle='--')
        
        # --- DISEGNO LIVELLI STRATEGIA (SE CI SONO LOTTI ATTIVI) ---
        if prezzo_medio > 0:
            # Linea del Prezzo Medio di Carico (Azzurro / Blu chiaro)
            ax1.axhline(y=prezzo_medio, color='#0288d1', linestyle='-.', linewidth=1.5, alpha=0.8, label=f'Prezzo Medio: ${prezzo_medio:,.2f}')
            
            # Calcolo e disegno del livello di Stop Loss / Profit Lockdown sul grafico
            prezzo_sl = prezzo_medio * (1 + (stop_loss_perc / 100.0))
            colore_sl = '#2e7d32' if stop_loss_perc >= 0 else '#c62828' # Verde se profitto garantito, Rosso se Stop Loss
            etichetta_sl = f'Stop/Lockdown ({stop_loss_perc:+.1f}%): ${prezzo_sl:,.2f}'
            
            ax1.axhline(y=prezzo_sl, color=colore_sl, linestyle=':', linewidth=1.8, alpha=0.9, label=etichetta_sl)

        ultimo_idx = len(x) - 1
        ax1.scatter([ultimo_idx], [prezzo_attuale], color='#26a69a', s=45, zorder=5)
        ax1.annotate(f"${prezzo_attuale:,.2f}", 
                     xy=(ultimo_idx, prezzo_attuale), 
                     xytext=(-65, 12), textcoords='offset points',
                     color='black', fontsize=9, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.25', fc='#f0f0f0', ec='#26a69a', alpha=0.9))

        ax1.set_title('BTC-USD | Profit Lockdown & Risk-Managed Bot', color='black', fontsize=13, fontweight='bold', pad=12)
        ax1.tick_params(colors='black', labelsize=9)
        ax1.grid(True, color='#d0d0d0', linestyle='--', alpha=0.5)
        
        # Gestione etichette Asse X con orari reali
        if 'Time' in dati_plot.columns:
            orari = []
            for t in dati_plot['Time']:
                try:
                    dt = datetime.fromtimestamp(float(t), tz=timezone.utc)
                    orari.append(dt.strftime('%H:%M'))
                except:
                    orari.append('')
            
            step = max(1, len(x) // 7)
            ax1.set_xticks(list(x)[::step])
            ax1.set_xticklabels([orari[i] for i in list(x)[::step]], fontsize=8)
        
        for spine in ax1.spines.values():
            spine.set_color('#cccccc')
            
        ax1.legend(loc='upper left', facecolor='#f9f9f9', edgecolor='none', labelcolor='black', fontsize=8)

        # --- PANNELLO 2: DASHBOARD DATI UTILI IN BASSO ---
        ax2 = fig.add_subplot(gs[1])
        ax2.set_facecolor('#f4f4f4')
        ax2.axis('off')
        
        info_testo = f" 📊  PANNELLO DI CONTROLLO PROFIT LOCKDOWN & ATR\n • Prezzo Corrente: ${prezzo_attuale:,.2f}    |    • RSI: {rsi_attuale:.1f}\n • Stato Operativo: {stato_testo}"
        
        ax2.text(0.02, 0.5, info_testo, color='black', fontsize=10, family='monospace',
                 verticalalignment='center', bbox=dict(boxstyle='square,pad=0.8', fc='#e8e8e8', ec='#cccccc'))

        plt.tight_layout()
        chart_path = 'temp_chart.png'
        plt.savefig(chart_path, dpi=150, facecolor='white', edgecolor='none')
        plt.close()
        return chart_path
    except Exception as e:
        print(f"Errore nella generazione del grafico con livelli: {e}")
        return None

# ==================== INVIO TELEGRAM ====================
def invia_messaggio_telegram(testo, chart_path=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Credenziali Telegram mancanti. Messaggio non inviato.")
        return
    
    try:
        if chart_path and os.path.exists(chart_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(chart_path, 'rb') as photo:
                payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': testo, 'parse_mode': 'Markdown'}
                requests.post(url, data=payload, files={'photo': photo}, timeout=20)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': testo, 'parse_mode': 'Markdown'}
            requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

# ==================== LOGICA PRINCIPALE DEL BOT ====================
def esegui_bot():
    print("Avvio esecuzione bot BTC...")
    df = ottieni_dati_binance()
    if df is None or len(df) < 30:
        print("Dati insufficienti dalle API.")
        return

    # Calcolo indicatori
    df['ema_veloce'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['ema_lenta'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['rsi'] = calcola_rsi(df['Close'], 14)
    df['atr'] = calcola_atr(df, 14)

    ultimo_prezzo = df['Close'].iloc[-1]
    rsi_attuale = df['rsi'].iloc[-1] if not np.isnan(df['rsi'].iloc[-1]) else 50.0
    atr_attuale = df['atr'].iloc[-1] if not np.isnan(df['atr'].iloc[-1]) else (ultimo_prezzo * 0.01)
    volatilita_pct = (atr_attuale / ultimo_prezzo) * 100

    # Carica stato portafoglio persistente
    portafoglio = carica_portafoglio()
    lotti = portafoglio["lotti"]
    lotti_attivi = len(lotti)

    # Calcolo Prezzo Medio di Carico e Quantità Totale
    quantita_totale = sum(l['quantita'] for l in lotti)
    spesa_totale = sum(l['spesa'] for l in lotti)
    prezzo_medio = (spesa_totale / quantita_totale) if quantita_totale > 0 else 0.0

    # Gestione Stop Loss dinamico e Profit Lockdown di base
    stop_loss_effettivo_perc = -2.0 # Default -2%
    if lotti_attivi > 0:
        performance_corrente = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100
        if performance_corrente > 1.5:
            stop_loss_effettivo_perc = +0.5 # Profitto garantito del +0.5%
        elif performance_corrente > 3.0:
            stop_loss_effettivo_perc = +2.0

    azione_eseguita = False
    messaggio_notifica = ""
    stato_dashboard = f"Posizioni attive ({lotti_attivi} lotti in corso)"

    # --- CONTROLLO USCITA (STOP LOSS / LOCKDOWN) ---
    if lotti_attivi > 0:
        soglia_sl_prezzo = prezzo_medio * (1 + (stop_loss_effettivo_perc / 100.0))
        if ultimo_prezzo <= soglia_sl_prezzo:
            ricavo = quantita_totale * ultimo_prezzo
            profitto_operazione = ricavo - spesa_totale
            portafoglio["saldo_usd"] += ricavo
            portafoglio["lotti"] = []
            
            messaggio_notifica = (
                f"🚨 *CHIUSURA POSIZIONE (STOP / PROFIT LOCKDOWN)* 🚨\n\n"
                f"• Prezzo Chiusura: ${ultimo_prezzo:,.2f}\n"
                f"• Prezzo Medio Carico: ${prezzo_medio:,.2f}\n"
                f"• Profitto/Perdita: ${profitto_operazione:+,.2f} ({((ultimo_prezzo/prezzo_medio)-1)*100:+.2f}%)\n"
                f"• Saldo USD Aggiornato: ${portafoglio['saldo_usd']:,.2f}"
            )
            azione_eseguita = True
            lotti_attivi = 0
            prezzo_medio = 0.0

    # --- CONTROLLO INGRESSO (ACQUISTO LOTTI) ---
    if not azione_eseguita:
        if lotti_attivi == 0 and (rsi_attuale < 35 or df['ema_veloce'].iloc[-1] > df['ema_lenta'].iloc[-1]):
            if portafoglio["saldo_usd"] >= CAPITALE_PER_LOTTO:
                quantita = CAPITALE_PER_LOTTO / ultimo_prezzo
                portafoglio["saldo_usd"] -= CAPITALE_PER_LOTTO
                portafoglio["lotti"].append({
                    "id": 1,
                    "prezzo_entrata": ultimo_prezzo,
                    "quantita": quantita,
                    "spesa": CAPITALE_PER_LOTTO
                })
                
                prezzo_medio = ultimo_prezzo
                lotti_attivi = 1
                messaggio_notifica = (
                    f"🟢 *ACQUISTO LOTTO (#1)* 🟢\n\n"
                    f"• Prezzo entrata: ${ultimo_prezzo:,.2f}\n"
                    f"• Quantità acquistata: {quantita:.5f} BTC\n"
                    f"• Spesa lorda: ${CAPITALE_PER_LOTTO:,.2f}\n"
                    f"• Perché questa scelta: RSI ipervenduto ({rsi_attuale:.1f}) / Setup rialzista EMA.\n\n"
                    f"📊 Lotti attivi totali: 1\n"
                    f"💰 Saldo USD residuo: ${portafoglio['saldo_usd']:,.2f}"
                )
                azione_eseguita = True

        elif lotti_attivi == 1 and ultimo_prezzo <= (prezzo_medio * 0.985):
            if portafoglio["saldo_usd"] >= CAPITALE_PER_LOTTO:
                quantita = CAPITALE_PER_LOTTO / ultimo_prezzo
                portafoglio["saldo_usd"] -= CAPITALE_PER_LOTTO
                portafoglio["lotti"].append({
                    "id": 2,
                    "prezzo_entrata": ultimo_prezzo,
                    "quantita": quantita,
                    "spesa": CAPITALE_PER_LOTTO
                })
                
                quantita_totale = sum(l['quantita'] for l in portafoglio["lotti"])
                spesa_totale = sum(l['spesa'] for l in portafoglio["lotti"])
                prezzo_medio = spesa_totale / quantita_totale
                lotti_attivi = 2
                
                messaggio_notifica = (
                    f"🟢 *ACQUISTO LOTTO (#2) CON PROFIT LOCKDOWN* 🟢\n\n"
                    f"• Prezzo entrata: ${ultimo_prezzo:,.2f}\n"
                    f"• Quantità acquistata: {quantita:.5f} BTC\n"
                    f"• Spesa totale lorda: ${spesa_totale:,.2f}\n"
                    f"• Perché questa scelta: Ribasso controllato (ATR {volatilita_pct:.2f}%). Aggiunto lotto #2.\n\n"
                    f"📊 Lotti attivi totali: 2\n"
                    f"💰 Saldo USD residuo: ${portafoglio['saldo_usd']:,.2f}"
                )
                azione_eseguita = True

    salva_portafoglio(portafoglio)

    if not azione_eseguita:
        performance_netta = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100 if lotti_attivi > 0 else 0.0
        messaggio_notifica = (
            f"🛡️ *REPORT DI MERCATO & PROFIT LOCKDOWN* 🛡️\n\n"
            f"• Prezzo BTC: ${ultimo_prezzo:,.2f}\n\n"
            f"📌 *Analisi e Decisione del Bot:*\n"
            f"📈 Posizioni attive ({lotti_attivi} lotti in corso)\n"
            f"• Quantità totale BTC: {quantita_totale:.5f}\n"
            f"• Prezzo medio di carico: ${prezzo_medio:,.2f}\n"
            f"• Performance netta: {performance_netta:+.2f}%\n"
            f"• Protezione attiva: Stop Loss dinamico a {stop_loss_effettivo_perc:+.2f}%."
        )

    chart_path = genera_grafico_chart(df, rsi_attuale, ultimo_prezzo, stato_dashboard, prezzo_medio, stop_loss_effettivo_perc)
    invia_messaggio_telegram(messaggio_notifica, chart_path)
    print("Esecuzione completata con successo.")

if __name__ == "__main__":
    esegui_bot()
