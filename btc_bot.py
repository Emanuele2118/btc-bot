import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ==================== CONFIGURAZIONE ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL")

PORTFOLIO_FILE = "portfolio.json"
PORTFOLIO_BACKUP_FILE = "portfolio_backup.json"

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
                    if "ultima_operazione_time" not in data:
                        data["ultima_operazione_time"] = 0
                    if "ultimo_report_time" not in data:
                        data["ultimo_report_time"] = 0
                    return data
        except Exception as e:
            print(f"Errore nella lettura del portafoglio: {e}")
    
    return {
        "saldo_usd": CAPITALE_INIZIALE,
        "lotti": [],
        "ultima_operazione_time": 0,
        "ultimo_report_time": 0
    }

def salva_portafoglio(portafoglio):
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portafoglio, f, indent=4)
        with open(PORTFOLIO_BACKUP_FILE, 'w') as f:
            json.dump(portafoglio, f, indent=4)
        print("Portfolio salvato correttamente in locale con backup.")
    except Exception as e:
        print(f"Errore nel salvataggio del portafoglio: {e}")

def registra_su_google_sheets(dati_transazione):
    if not GOOGLE_SHEET_URL:
        return
    try:
        requests.post(GOOGLE_SHEET_URL, json=dati_transazione, timeout=10)
    except Exception as e:
        print(f"Errore invio dati a Google Sheets: {e}")

# ==================== RECUPERO DATI COINBASE ====================
def ottieni_dati_coinbase():
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) >= 50:
                # Coinbase formato: [time, low, high, open, close, volume]
                df = pd.DataFrame(data, columns=['Time', 'Low', 'High', 'Open', 'Close', 'Volume'])
                df = df.sort_values('Time').reset_index(drop=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = df[col].astype(float)
                df['Datetime'] = pd.to_datetime(df['Time'], unit='s', utc=True)
                return df
    except Exception as e:
        print(f"Errore connessione Coinbase Exchange: {e}")

    # Fallback su Binance se Coinbase fallisce
    print("Tentativo fallback su Binance...")
    try:
        url_binance = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=150"
        response = requests.get(url_binance, timeout=10)
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
        print(f"Errore fallback Binance: {e}")

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

# ==================== GENERAZIONE GRAFICO A DUE PANNELLI ====================
def genera_grafico_chart(df, rsi_attuale, prezzo_attuale, stato_testo):
    """Genera un grafico avanzato a candele con sfondo bianco, due pannelli e dashboard in basso."""
    try:
        fig = plt.figure(figsize=(10, 7.5), facecolor='white')
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1.3])
        
        # --- PANNELLO 1: GRAFICO A CANDELE & MEDIE MOBILI ---
        ax1 = fig.add_subplot(gs[0])
        ax1.set_facecolor('white')
        
        dati_plot = df.tail(100).copy().reset_index(drop=True)
        x = range(len(dati_plot))
        
        for i in x:
            o = dati_plot['Open'].iloc[i]
            c = dati_plot['Close'].iloc[i]
            h = dati_plot['High'].iloc[i]
            l = dati_plot['Low'].iloc[i]
            
            colore = '#26a69a' if c >= o else '#9c27b0' # Verde acqua per salita, Viola per discesa
            
            ax1.plot([i, i], [l, h], color=colore, linewidth=1, zorder=1)
            bottom = min(o, c)
            height = abs(c - o) if abs(c - o) > 0 else 0.01
            ax1.bar(i, height, bottom=bottom, color=colore, width=0.6, zorder=2)

        ax1.plot(x, dati_plot['ema_veloce'], label='EMA 9 (Veloce)', color='#ff9800', linewidth=1.2, linestyle='--')
        ax1.plot(x, dati_plot['ema_lenta'], label='EMA 50 (Lenta)', color='#3f51b5', linewidth=1.2, linestyle='--')
        ax1.plot(x, dati_plot['ema_macro'], label='EMA 200 (Macro)', color='#00bcd4', linewidth=1.2, linestyle=':')
        
        ultimo_idx = len(x) - 1
        ax1.scatter([ultimo_idx], [prezzo_attuale], color='#26a69a', s=45, zorder=5)
        ax1.annotate(f"${prezzo_attuale:,.2f}", 
                     xy=(ultimo_idx, prezzo_attuale), 
                     xytext=(-65, 12), textcoords='offset points',
                     color='black', fontsize=9, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.25', fc='#f0f0f0', ec='#26a69a', alpha=0.9))

        ax1.set_title('BTC-USD | Profit Lockdown & Risk-Managed Bot', color='black', fontsize=13, fontweight='bold', pad=12)
        ax1.tick_params(colors='black', labelsize=9)
        ax1.grid(True, color='#e0e0e0', linestyle=':', alpha=0.7)
        
        for spine in ax1.spines.values():
            spine.set_color('#cccccc')
            
        ax1.legend(loc='upper left', facecolor='#f9f9f9', edgecolor='none', labelcolor='black', fontsize=9)

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
        print(f"Errore nella generazione del grafico a candele: {e}")
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
    print("Avvio esecuzione bot Profit Maximizer / REPORT DI MERCATO...")
    df = ottieni_dati_coinbase()
    if df is None or len(df) < 50:
        print("Dati insufficienti dalle API.")
        return

    df['ema_veloce'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['ema_lenta'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['ema_macro'] = df['Close'].ewm(span=200, adjust=False).mean()
    df['rsi'] = calcola_rsi(df['Close'], 14)
    df['atr'] = calcola_atr(df, 14)

    ultimo_prezzo = df['Close'].iloc[-1]
    rsi_attuale = df['rsi'].iloc[-1] if not np.isnan(df['rsi'].iloc[-1]) else 50.0
    atr_attuale = df['atr'].iloc[-1] if not np.isnan(df['atr'].iloc[-1]) else (ultimo_prezzo * 0.01)
    ema_v = df['ema_veloce'].iloc[-1]
    ema_l = df['ema_lenta'].iloc[-1]
    ema_m = df['ema_macro'].iloc[-1]

    portafoglio = carica_portafoglio()
    lotti = portafoglio.get("lotti", [])
    lotti_attivi = len(lotti)
    timestamp_attuale = datetime.now(timezone.utc).timestamp()

    quantita_totale = sum(l.get('quantita', 0) for l in lotti)
    spesa_totale = sum(l.get('spesa', 0) for l in lotti)
    prezzo_medio = (spesa_totale / quantita_totale) if quantita_totale > 0 else 0.0

    profitto_P_L = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100 if lotti_attivi > 0 and prezzo_medio > 0 else 0.0
    
    # Profit Lockdown Dinamico (Stop Loss Evolutivo)
    stop_loss_effettivo_perc = -2.0 
    if lotti_attivi > 0 and prezzo_medio > 0:
        if profitto_P_L >= 3.0:
            stop_loss_effettivo_perc = +1.0
        elif profitto_P_L >= 1.5:
            stop_loss_effettivo_perc = 0.0

    azione_eseguita = False
    messaggio_notifica = ""
    stato_dashboard = f"Pos ({lotti_attivi}/{MAX_LOTTI}) | P&L: {profitto_P_L:+.2f}% | SL: {stop_loss_effettivo_perc:+.1f}%"

    # Controllo Cooldown Antispam Operazioni (180 secondi)
    tempo_ultima_op = portafoglio.get("ultima_operazione_time", 0)
    puoi_operare = (timestamp_attuale - tempo_ultima_op) >= 180

    # --- 1. VENDITA PARZIALE / TRAILING TAKE PROFIT ---
    if puoi_operare and not azione_eseguita and lotti_attivi > 0 and prezzo_medio > 0:
        condizione_take_profit = (profitto_P_L >= 0.7 and ultimo_prezzo <= (df['High'].tail(5).max() - (atr_attuale * 0.8))) or (rsi_attuale > 68)
        if condizione_take_profit:
            lotti_ordinati = sorted(lotti, key=lambda x: x['prezzo_entrata'], reverse=True)
            lotto_da_vendere = lotti_ordinati[0]
            
            ricavo_parziale = lotto_da_vendere['quantita'] * ultimo_prezzo
            profitto_lotto = ricavo_parziale - lotto_da_vendere['spesa']
            
            portafoglio["saldo_usd"] = portafoglio.get("saldo_usd", CAPITALE_INIZIALE) + ricavo_parziale
            portafoglio["lotti"] = [l for l in lotti if l['id'] != lotto_da_vendere['id']]
            portafoglio["ultima_operazione_time"] = timestamp_attuale
            
            messaggio_notifica = (
                f"🎯 *VENDITA PARZIALE TAKE PROFIT (Lotto #{lotto_da_vendere['id']})* 🎯\n\n"
                f"• Prezzo Vendita: ${ultimo_prezzo:,.2f}\n"
                f"• Profitto realizzato: ${profitto_lotto:+,.2f} ({((ultimo_prezzo/lotto_da_vendere['prezzo_entrata'])-1)*100:+.2f}%)\n"
                f"• Saldo USD Aggiornato: ${portafoglio['saldo_usd']:,.2f}\n"
                f"• Lotti rimanenti: {len(portafoglio['lotti'])}/{MAX_LOTTI}"
            )
            azione_eseguita = True
            salva_portafoglio(portafoglio)
            registra_su_google_sheets({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tipo": "VENDITA",
                "prezzo": ultimo_prezzo,
                "quantita": lotto_da_vendere['quantita'],
                "profitto": profitto_lotto,
                "motivazione": "Take Profit / RSI Ipercomprato"
            })

    # --- 2. STOP LOSS / PROFIT LOCKDOWN ---
    if not azione_eseguita and lotti_attivi > 0 and prezzo_medio > 0:
        soglia_sl_prezzo = prezzo_medio * (1 + (stop_loss_effettivo_perc / 100.0))
        minimo_recente = df['Low'].tail(10).min()
        soglia_strutturale = min(soglia_sl_prezzo, minimo_recente)

        if ultimo_prezzo <= soglia_strutturale:
            ricavo = quantita_totale * ultimo_prezzo
            profitto_operazione = ricavo - spesa_totale
            portafoglio["saldo_usd"] = portafoglio.get("saldo_usd", CAPITALE_INIZIALE) + ricavo
            portafoglio["lotti"] = []
            portafoglio["ultima_operazione_time"] = timestamp_attuale
            
            messaggio_notifica = (
                f"🚨 *CHIUSURA TOTALE (PROFIT LOCKDOWN / STOP STRUCTURAL)* 🚨\n\n"
                f"• Prezzo Chiusura: ${ultimo_prezzo:,.2f}\n"
                f"• Prezzo Medio Carico: ${prezzo_medio:,.2f}\n"
                f"• Profitto/Perdita Totale: ${profitto_operazione:+,.2f} ({profitto_P_L:+.2f}%)\n"
                f"• Saldo USD Disponibile: ${portafoglio['saldo_usd']:,.2f}"
            )
            azione_eseguita = True
            salva_portafoglio(portafoglio)
            registra_su_google_sheets({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tipo": "STOP_LOSS",
                "prezzo": ultimo_prezzo,
                "quantita": quantita_totale,
                "profitto": profitto_operazione,
                "motivazione": "Profit Lockdown / Stop Strutturale"
            })

    # --- 3. INGRESSI MULTI-LOTTO & POSITION SIZING ATR ---
    if puoi_operare and not azione_eseguita:
        saldo_corrente = portafoglio.get("saldo_usd", CAPITALE_INIZIALE)
        
        # Position sizing dinamico basato su ATR
        volatilita_pct = (atr_attuale / ultimo_prezzo) * 100
        fattore_size = 1.0
        if volatilita_pct > 1.5:
            fattore_size = 0.8 # Riduce esposizione con alta volatilità
        elif volatilita_pct < 0.5:
            fattore_size = 1.2 # Ottimizza con bassa volatilità

        capitale_lotto_dinamico = CAPITALE_PER_LOTTO * fattore_size

        condizione_rsi_scarico = rsi_attuale < 38
        condizione_trend = (ema_v > ema_l) and (ultimo_prezzo > ema_m)

        if lotti_attivi == 0 and (condizione_rsi_scarico or condizione_trend):
            if saldo_corrente >= capitale_lotto_dinamico:
                quantita = capitale_lotto_dinamico / ultimo_prezzo
                portafoglio["saldo_usd"] = saldo_corrente - capitale_lotto_dinamico
                portafoglio["lotti"].append({
                    "id": 1,
                    "prezzo_entrata": ultimo_prezzo,
                    "quantita": quantita,
                    "spesa": capitale_lotto_dinamico
                })
                portafoglio["ultima_operazione_time"] = timestamp_attuale
                
                lotti_attivi = 1
                motivo_ingresso = "RSI in ipervenduto (<38)" if condizione_rsi_scarico else "Trend favorevole (EMA 9>50 e Prezzo>EMA 200)"
                
                messaggio_notifica = (
                    f"🟢 *APERTURA PRIMO LOTTO (#1/{MAX_LOTTI})* 🟢\n\n"
                    f"• Prezzo Entrata: ${ultimo_prezzo:,.2f}\n"
                    f"• Spesa Effettuata: ${capitale_lotto_dinamico:,.2f} USD\n"
                    f"• Quantità: {quantita:.5f} BTC\n"
                    f"• Saldo USD Rimanente: ${portafoglio['saldo_usd']:,.2f}\n\n"
                    f"🔍 *Motivo Ingresso:* {motivo_ingresso} (RSI: {rsi_attuale:.1f})\n"
                    f"📋 *Strategia:* DCA Multi-lotto con Risk Management ATR."
                )
                azione_eseguita = True
                salva_portafoglio(portafoglio)
                registra_su_google_sheets({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tipo": "ACQUISTO",
                    "prezzo": ultimo_prezzo,
                    "quantita": quantita,
                    "profitto": 0.0,
                    "motivazione": motivo_ingresso
                })

        elif 0 < lotti_attivi < MAX_LOTTI and prezzo_medio > 0:
            ultimo_lotto_prezzo = lotti[-1]['prezzo_entrata']
            distanza_richiesta_atr = atr_attuale * 1.2
            
            if ultimo_prezzo <= (ultimo_lotto_prezzo - distanza_richiesta_atr):
                if saldo_corrente >= capitale_lotto_dinamico:
                    nuovo_id = lotti_attivi + 1
                    quantita = capitale_lotto_dinamico / ultimo_prezzo
                    portafoglio["saldo_usd"] = saldo_corrente - capitale_lotto_dinamico
                    portafoglio["lotti"].append({
                        "id": nuovo_id,
                        "prezzo_entrata": ultimo_prezzo,
                        "quantita": quantita,
                        "spesa": capitale_lotto_dinamico
                    })
                    portafoglio["ultima_operazione_time"] = timestamp_attuale
                    
                    quantita_totale = sum(l.get('quantita', 0) for l in portafoglio["lotti"])
                    spesa_totale = sum(l.get('spesa', 0) for l in portafoglio["lotti"])
                    prezzo_medio = spesa_totale / quantita_totale
                    lotti_attivi = nuovo_id
                    
                    messaggio_notifica = (
                        f"🟢 *INCREMENTO POSIZIONE: LOTTO (#{nuovo_id}/{MAX_LOTTI})* 🟢\n\n"
                        f"• Prezzo Ingresso: ${ultimo_prezzo:,.2f}\n"
                        f"• Spesa Effettuata: ${capitale_lotto_dinamico:,.2f} USD\n"
                        f"• Nuovo Prezzo Medio: ${prezzo_medio:,.2f}\n"
                        f"• Saldo USD Rimanente: ${portafoglio['saldo_usd']:,.2f}\n\n"
                        f"🔍 *Motivo Ingresso:* Ribasso ATR (${distanza_richiesta_atr:.2f}).\n"
                        f"📋 *Strategia:* Mediazione al ribasso (DCA Grid dinamica)."
                    )
                    azione_eseguita = True
                    salva_portafoglio(portafoglio)
                    registra_su_google_sheets({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "tipo": "ACQUISTO",
                        "prezzo": ultimo_prezzo,
                        "quantita": quantita,
                        "profitto": 0.0,
                        "motivazione": "Incremento DCA ATR"
                    })

    # --- REPORT DI MERCATO E MONITORAGGIO (CON PROTEZIONE ANTISPAM MESSAGGI) ---
    tempo_ultimo_report = portafoglio.get("ultimo_report_time", 0)
    puoi_inviare_report = (timestamp_attuale - tempo_ultimo_report) >= 50

    if not azione_eseguita and puoi_inviare_report:
        motivo_attesa = f"RSI attuale ({rsi_attuale:.1f}) in attesa di condizioni ottimali."
        if lotti_attivi > 0:
            motivo_attesa = f"In attesa di take profit o ribasso ATR (${atr_attuale:.2f})."

        dettagli_posizioni = ""
        if lotti_attivi > 0:
            dettagli_posizioni = (
                f"• Posizioni attive: {lotti_attivi}/{MAX_LOTTI} lotti\n"
                f"• Prezzo medio: ${prezzo_medio:,.2f}\n"
                f"• Performance: {profitto_P_L:+.2f}%\n"
            )

        messaggio_notifica = (
            f"📈 *REPORT DI MERCATO* 📈\n\n"
            f"• Prezzo BTC: ${ultimo_prezzo:,.2f}\n"
            f"• RSI: {rsi_attuale:.1f} | ATR: ${atr_attuale:.2f}\n\n"
            f"{dettagli_posizioni}"
            f"• Stato: {motivo_attesa}"
        )
        portafoglio["ultimo_report_time"] = timestamp_attuale
        salva_portafoglio(portafogloss:=portafoglio)

    chart_path = genera_grafico_chart(df, rsi_attuale, ultimo_prezzo, stato_dashboard)
    
    if azione_eseguita or puoi_inviare_report:
        invia_messaggio_telegram(messaggio_notifica, chart_path)
        print("Notifica / Report inviato correttamente su Telegram.")

if __name__ == "__main__":
    esegui_bot()
