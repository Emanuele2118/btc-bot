import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ==================== CONFIGURAZIONE ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")

PORTFOLIO_FILE = "portfolio.json"

CAPITALE_INIZIALE = 10000.0  
CAPITALE_PER_LOTTO = 2500.0   
MAX_LOTTI = 4                 

# ==================== GESTIONE PORTAFOGLIO ====================
def carica_portafoglio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "saldo_usd" not in data:
                        data["saldo_usd"] = CAPITALE_INIZIALE
                    if "lotti" not in data:
                        data["lotti"] = []
                    return data
        except Exception as e:
            print(f"Errore nella lettura del portafoglio: {e}")
    
    return {
        "saldo_usd": CAPITALE_INIZIALE,
        "lotti": []
    }

def salva_portafoglio(portafoglio):
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portafoglio, f, indent=4)
        print("Portfolio salvato correttamente in locale (verrà committato dall'Action).")
    except Exception as e:
        print(f"Errore nel salvataggio del portafoglio: {e}")

# ==================== RECUPERO DATI (TIMEFRAME 1 MINUTO) ====================
def ottieni_dati_binance():
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=120"
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
                df['Datetime'] = pd.to_datetime(df['Time'], unit='ms', utc=True)
                return df
    except Exception as e:
        print(f"Errore connessione Binance: {e}")

    print("Tentativo fallback su CoinGecko...")
    try:
        url_cg = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc?vs_currency=usd&days=1"
        resp = requests.get(url_cg, timeout=10)
        if resp.status_code == 200:
            cg_data = resp.json()
            df = pd.DataFrame(cg_data, columns=['Time', 'Open', 'High', 'Low', 'Close'])
            df['Datetime'] = pd.to_datetime(df['Time'], unit='ms', utc=True)
            df['Volume'] = 1000.0
            return df
    except Exception as e:
        print(f"Errore fallback CoinGecko: {e}")
        
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
    low_close = np.abs(df['Low'] - df['Low'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=periodo).mean()

# ==================== GENERAZIONE GRAFICO ====================
def genera_grafico_chart(df, rsi_attuale, prezzo_attuale, stato_testo, prezzo_medio=0.0, stop_loss_perc=0.0):
    try:
        fig = plt.figure(figsize=(10, 7.5), facecolor='white')
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1.3])
        
        ax1 = fig.add_subplot(gs[0])
        ax1.set_facecolor('white')
        
        dati_plot = df.tail(90).copy().reset_index(drop=True)
        x = range(len(dati_plot))
        
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

        ax1.plot(x, dati_plot['ema_veloce'], label='EMA 9 (Veloce)', color='#ff9800', linewidth=1.2, linestyle='--')
        ax1.plot(x, dati_plot['ema_lenta'], label='EMA 50 (Lenta)', color='#3f51b5', linewidth=1.2, linestyle='--')
        
        if prezzo_medio > 0:
            ax1.axhline(y=prezzo_medio, color='#0288d1', linestyle='-.', linewidth=1.5, alpha=0.9, label=f'Prezzo Medio: ${prezzo_medio:,.2f}')
            prezzo_sl = prezzo_medio * (1 + (stop_loss_perc / 100.0))
            colore_sl = '#2e7d32' if stop_loss_perc >= 0 else '#c62828'
            etichetta_sl = f'Stop/Lockdown ({stop_loss_perc:+.1f}%): ${prezzo_sl:,.2f}'
            ax1.axhline(y=prezzo_sl, color=colore_sl, linestyle=':', linewidth=1.8, alpha=0.9, label=etichetta_sl)

        ultimo_idx = len(x) - 1
        ax1.scatter([ultimo_idx], [prezzo_attuale], color='#26a69a', s=45, zorder=5)
        ax1.annotate(f"${prezzo_attuale:,.2f}", 
                     xy=(ultimo_idx, prezzo_attuale), 
                     xytext=(-65, 12), textcoords='offset points',
                     color='black', fontsize=9, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.25', fc='#f0f0f0', ec='#26a69a', alpha=0.9))

        ax1.set_title('BTC-USD (1m) | Profit Lockdown & Risk-Managed Bot', color='black', fontsize=13, fontweight='bold', pad=12)
        ax1.tick_params(colors='black', labelsize=9)
        ax1.grid(True, color='#d0d0d0', linestyle='--', alpha=0.5)
        
        if 'Datetime' in dati_plot.columns:
            orari = [dt.strftime('%H:%M') for dt in dati_plot['Datetime']]
            step = max(1, len(x) // 6)
            ax1.set_xticks(list(x)[::step])
            ax1.set_xticklabels([orari[i] for i in list(x)[::step]], fontsize=8)
        
        for spine in ax1.spines.values():
            spine.set_color('#cccccc')
            
        ax1.legend(loc='upper left', facecolor='#f9f9f9', edgecolor='none', labelcolor='black', fontsize=8)

        ax2 = fig.add_subplot(gs[1])
        ax2.set_facecolor('#f4f4f4')
        ax2.axis('off')
        
        info_testo = f" 📊  PANNELLO DI CONTROLLO (1m | MAX {MAX_LOTTI} LOTTI)\n • Prezzo Corrente: ${prezzo_attuale:,.2f}    |    • RSI: {rsi_attuale:.1f}\n • Stato Operativo: {stato_testo}"
        ax2.text(0.02, 0.5, info_testo, color='black', fontsize=10, family='monospace',
                 verticalalignment='center', bbox=dict(boxstyle='square,pad=0.8', fc='#e8e8e8', ec='#cccccc'))

        plt.tight_layout()
        chart_path = 'temp_chart.png'
        plt.savefig(chart_path, dpi=150, facecolor='white', edgecolor='none')
        plt.close()
        return chart_path
    except Exception as e:
        print(f"Errore nella generazione del grafico: {e}")
        return None

# ==================== INVIO TELEGRAM ====================
def invia_messaggio_telegram(testo, chart_path=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Credenziali Telegram mancanti.")
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
    print("Avvio esecuzione bot BTC (1m)...")
    df = ottieni_dati_binance()
    if df is None or len(df) < 30:
        print("Dati insufficienti dalle API.")
        return

    df['ema_veloce'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['ema_lenta'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['rsi'] = calcola_rsi(df['Close'], 14)
    df['atr'] = calcola_atr(df, 14)

    ultimo_prezzo = df['Close'].iloc[-1]
    rsi_attuale = df['rsi'].iloc[-1] if not np.isnan(df['rsi'].iloc[-1]) else 50.0
    atr_attuale = df['atr'].iloc[-1] if not np.isnan(df['atr'].iloc[-1]) else (ultimo_prezzo * 0.01)

    portafoglio = carica_portafoglio()
    lotti = portafoglio.get("lotti", [])
    lotti_attivi = len(lotti)

    quantita_totale = sum(l.get('quantita', 0) for l in lotti)
    spesa_totale = sum(l.get('spesa', 0) for l in lotti)
    prezzo_medio = (spesa_totale / quantita_totale) if quantita_totale > 0 else 0.0

    stop_loss_effettivo_perc = -2.0 
    if lotti_attivi > 0 and prezzo_medio > 0:
        performance_corrente = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100
        if performance_corrente > 1.5:
            stop_loss_effettivo_perc = +0.5 
        elif performance_corrente > 3.0:
            stop_loss_effettivo_perc = +2.0

    azione_eseguita = False
    messaggio_notifica = ""
    stato_dashboard = f"Posizioni attive ({lotti_attivi}/{MAX_LOTTI} lotti)"

    # --- CONTROLLO USCITA (STOP LOSS / LOCKDOWN) ---
    if lotti_attivi > 0 and prezzo_medio > 0:
        soglia_sl_prezzo = prezzo_medio * (1 + (stop_loss_effettivo_perc / 100.0))
        if ultimo_prezzo <= soglia_sl_prezzo:
            ricavo = quantita_totale * ultimo_prezzo
            profitto_operazione = ricavo - spesa_totale
            portafoglio["saldo_usd"] = portafoglio.get("saldo_usd", CAPITALE_INIZIALE) + ricavo
            portafoglio["lotti"] = []
            
            messaggio_notifica = (
                f"🚨 *CHIUSURA POSIZIONE (STOP / PROFIT LOCKDOWN)* 🚨\n\n"
                f"• Prezzo Chiusura: ${ultimo_prezzo:,.2f}\n"
                f"• Prezzo Medio Carico: ${prezzo_medio:,.2f}\n"
                f"• Profitto/Perdita: ${profitto_operazione:+,.2f} ({((ultimo_prezzo/prezzo_medio)-1)*100:+.2f}%)\n"
                f"• Saldo USD Aggiornato: ${portafoglio['saldo_usd']:,.2f}"
            )
            azione_eseguita = True
            salva_portafoglio(portafoglio)
            lotti_attivi = 0
            prezzo_medio = 0.0

    # --- CONTROLLO INGRESSO (FINO A 4 LOTTI) ---
    if not azione_eseguita:
        saldo_corrente = portafoglio.get("saldo_usd", CAPITALE_INIZIALE)
        
        # Primo lotto
        if lotti_attivi == 0 and (rsi_attuale < 35 or df['ema_veloce'].iloc[-1] > df['ema_lenta'].iloc[-1]):
            if saldo_corrente >= CAPITALE_PER_LOTTO:
                quantita = CAPITALE_PER_LOTTO / ultimo_prezzo
                portafoglio["saldo_usd"] = saldo_corrente - CAPITALE_PER_LOTTO
                portafoglio["lotti"].append({
                    "id": 1,
                    "prezzo_entrata": ultimo_prezzo,
                    "quantita": quantita,
                    "spesa": CAPITALE_PER_LOTTO
                })
                
                prezzo_medio = ultimo_prezzo
                lotti_attivi = 1
                messaggio_notifica = (
                    f"🟢 *ACQUISTO LOTTO (#1/{MAX_LOTTI}) [1m]* 🟢\n\n"
                    f"• Prezzo entrata: ${ultimo_prezzo:,.2f}\n"
                    f"• Quantità: {quantita:.5f} BTC\n"
                    f"• Spesa: ${CAPITALE_PER_LOTTO:,.2f}\n"
                    f"• Motivazione: RSI ({rsi_attuale:.1f}) / Setup EMA.\n\n"
                    f"📊 Lotti attivi: 1/{MAX_LOTTI}\n"
                    f"💰 Saldo USD: ${portafoglio['saldo_usd']:,.2f}"
                )
                azione_eseguita = True
                salva_portafoglio(portafoglio)

        # Lotti successivi (fino a 4) se il prezzo scende dell'1.5% dal prezzo medio
        elif 0 < lotti_attivi < MAX_LOTTI and prezzo_medio > 0 and ultimo_prezzo <= (prezzo_medio * 0.985):
            if saldo_corrente >= CAPITALE_PER_LOTTO:
                nuovo_id = lotti_attivi + 1
                quantita = CAPITALE_PER_LOTTO / ultimo_prezzo
                portafoglio["saldo_usd"] = saldo_corrente - CAPITALE_PER_LOTTO
                portafoglio["lotti"].append({
                    "id": nuovo_id,
                    "prezzo_entrata": ultimo_prezzo,
                    "quantita": quantita,
                    "spesa": CAPITALE_PER_LOTTO
                })
                
                quantita_totale = sum(l.get('quantita', 0) for l in portafoglio["lotti"])
                spesa_totale = sum(l.get('spesa', 0) for l in portafoglio["lotti"])
                prezzo_medio = spesa_totale / quantita_totale
                lotti_attivi = nuovo_id
                
                messaggio_notifica = (
                    f"🟢 *ACQUISTO LOTTO (#{nuovo_id}/{MAX_LOTTI}) CON PROFIT LOCKDOWN* 🟢\n\n"
                    f"• Prezzo entrata: ${ultimo_prezzo:,.2f}\n"
                    f"• Quantità acquistata: {quantita:.5f} BTC\n"
                    f"• Spesa totale lorda: ${spesa_totale:,.2f}\n"
                    f"• Motivazione: Ribasso dal prezzo medio ({((ultimo_prezzo/prezzo_medio)-1)*100:.2f}%). Lotto #{nuovo_id} aggiunto.\n\n"
                    f"📊 Lotti attivi totali: {nuovo_id}\n"
                    f"💰 Saldo USD residuo: ${portafoglio['saldo_usd']:,.2f}"
                )
                azione_eseguita = True
                salva_portafoglio(portafoglio)

    if not azione_eseguita:
        performance_netta = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100 if lotti_attivi > 0 and prezzo_medio > 0 else 0.0
        messaggio_notifica = (
            f"🛡️ *REPORT DI MERCATO & PROFIT LOCKDOWN* 🛡️\n\n"
            f"• Prezzo BTC: ${ultimo_prezzo:,.2f}\n\n"
            f"📌 *Analisi e Decisione del Bot:*\n"
            f"📈 Posizioni attive ({lotti_attivi} lotti in corso)\n"
            f"• Quantità totale BTC: {quantita_totale:.5f}\n"
            f"• Prezzo medio di carico: ${prezzo_medio:,.2f}\n"
            f"• Performance netta: {performance_netta:+.2f}%\n"
            f"• Protezione attiva: Stop Loss dinamico a {stop_loss_effettivo_perc:+.2f}% (Supporti strutturali)."
        )

    chart_path = genera_grafico_chart(df, rsi_attuale, ultimo_prezzo, stato_dashboard, prezzo_medio, stop_loss_effettivo_perc)
    invia_messaggio_telegram(messaggio_notifica, chart_path)
    print("Esecuzione completata con successo.")

if __name__ == "__main__":
    esegui_bot()
