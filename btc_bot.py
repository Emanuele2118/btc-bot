import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import time
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

FEE_PERCENTUALE = 0.001       # 0.10% commissione reale Taker
MAX_DAILY_DRAWDOWN_PCT = 5.0  

# ==================== GESTIONE PORTAFOGLIO & BACKUP ====================
def carica_portafoglio():
    data = None
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Errore lettura file principale portfolio: {e}")
            
    if not data or not isinstance(data, dict):
        if os.path.exists(PORTFOLIO_BACKUP_FILE):
            try:
                print("Tentativo ripristino da file di backup...")
                with open(PORTFOLIO_BACKUP_FILE, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Errore lettura file backup: {e}")

    if isinstance(data, dict):
        if "saldo_usd" not in data:
            data["saldo_usd"] = CAPITALE_INIZIALE
        if "lotti" not in data:
            data["lotti"] = []
        if "ultima_operazione_time" not in data:
            data["ultima_operazione_time"] = 0
        if "ultimo_report_time" not in data:
            data["ultimo_report_time"] = 0
        if "valore_iniziale_giornata" not in data:
            data["valore_iniziale_giornata"] = CAPITALE_INIZIALE
        if "data_ultima_registrazione" not in data:
            data["data_ultima_registrazione"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if "blocco_drawdown_fino" not in data:
            data["blocco_drawdown_fino"] = 0.0
        if "storico_operazioni" not in data:
            data["storico_operazioni"] = []
        return data
    
    return {
        "saldo_usd": CAPITALE_INIZIALE,
        "lotti": [],
        "ultima_operazione_time": 0,
        "ultimo_report_time": 0,
        "valore_iniziale_giornata": CAPITALE_INIZIALE,
        "data_ultima_registrazione": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "blocco_drawdown_fino": 0.0,
        "storico_operazioni": []
    }

def salva_portafoglio(portafoglio):
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portafoglio, f, indent=4)
        with open(PORTFOLIO_BACKUP_FILE, 'w') as f:
            json.dump(portafoglio, f, indent=4)
    except Exception as e:
        print(f"Errore nel salvataggio del portafoglio: {e}")

def registra_su_google_sheets(dati_transazione):
    if not GOOGLE_SHEET_URL:
        return
    try:
        requests.post(GOOGLE_SHEET_URL, json=dati_transazione, timeout=10)
    except Exception as e:
        print(f"Errore invio dati a Google Sheets: {e}")

# ==================== RECUPERO DATI & REGIME DI MERCATO ====================
def ottieni_dati_coinbase():
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) >= 200:
                df = pd.DataFrame(data, columns=['Time', 'Low', 'High', 'Open', 'Close', 'Volume'])
                df = df.sort_values('Time').reset_index(drop=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = df[col].astype(float)
                df['Datetime'] = pd.to_datetime(df['Time'], unit='s', utc=True)
                
                df_15m = df.set_index('Datetime').resample('15min').agg({
                    'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
                }).dropna().reset_index()
                df_15m['ema_macro_15m'] = df_15m['Close'].ewm(span=50, adjust=False).mean()
                df['ema_macro_15m'] = df_15m['ema_macro_15m'].iloc[-1] if len(df_15m) > 0 else df['Close'].mean()
                return df
    except Exception as e:
        print(f"Errore connessione Coinbase Exchange: {e}")

    print("Tentativo fallback su Binance...")
    try:
        url_binance = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=250"
        response = requests.get(url_binance, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if len(data) >= 200:
                df = pd.DataFrame(data, columns=[
                    'Time', 'Open', 'High', 'Low', 'Close', 'Volume',
                    'CloseTime', 'QuoteAssetVolume', 'NumberOfTrades',
                    'TakerBuyBaseAssetVolume', 'TakerBuyQuoteAssetVolume', 'Ignore'
                ])
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = df[col].astype(float)
                df['Datetime'] = pd.to_datetime(df['Time'], unit='ms', utc=True)
                df['ema_macro_15m'] = df['Close'].ewm(span=50, adjust=False).mean()
                return df
    except Exception as e:
        print(f"Errore fallback Binance: {e}")

    return None

# ==================== INDICATORI QUANTITATIVI & EXTRA ====================
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

def calcola_bande_bollinger(serie, periodo=20, dev_std=2):
    sma = serie.rolling(window=periodo).mean()
    std = serie.rolling(window=periodo).std()
    upper = sma + (std * dev_std)
    lower = sma - (std * dev_std)
    return upper, sma, lower

def calcola_obv(df):
    obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
    return obv

# ==================== GRAFICO A DUE PANNELLI ====================
def genera_grafico_chart(df, rsi_attuale, prezzo_attuale, stato_testo, regime_mercato):
    try:
        fig = plt.figure(figsize=(10, 7.5), facecolor='white')
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1.3])
        
        ax1 = fig.add_subplot(gs[0])
        ax1.set_facecolor('white')
        
        dati_plot = df.tail(100).copy().reset_index(drop=True)
        x = range(len(dati_plot))
        
        upper, sma, lower = calcola_bande_bollinger(dati_plot['Close'])
        ax1.plot(x, upper, color='#b0bec5', linestyle='--', alpha=0.5, label='Bande Bollinger')
        ax1.plot(x, lower, color='#b0bec5', linestyle='--', alpha=0.5)

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

        ax1.plot(x, dati_plot['ema_veloce'], label='EMA 9', color='#ff9800', linewidth=1.2, linestyle='--')
        ax1.plot(x, dati_plot['ema_lenta'], label='EMA 50', color='#3f51b5', linewidth=1.2, linestyle='--')
        
        ultimo_idx = len(x) - 1
        ax1.scatter([ultimo_idx], [prezzo_attuale], color='#26a69a', s=45, zorder=5)
        ax1.annotate(f"${prezzo_attuale:,.2f}", 
                     xy=(ultimo_idx, prezzo_attuale), 
                     xytext=(-65, 12), textcoords='offset points',
                     color='black', fontsize=9, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.25', fc='#f0f0f0', ec='#26a69a', alpha=0.9))

        ax1.set_title(f'BTC-USD | Market Report (Regime: {regime_mercato})', color='black', fontsize=13, fontweight='bold', pad=12)
        ax1.tick_params(colors='black', labelsize=9)
        ax1.grid(True, color='#e0e0e0', linestyle=':', alpha=0.7)
        
        for spine in ax1.spines.values():
            spine.set_color('#cccccc')
            
        ax1.legend(loc='upper left', facecolor='#f9f9f9', edgecolor='none', labelcolor='black', fontsize=8)

        ax2 = fig.add_subplot(gs[1])
        ax2.set_facecolor('#f4f4f4')
        ax2.axis('off')
        
        info_testo = f" 📊  MARKET DASHBOARD\n • Prezzo: ${prezzo_attuale:,.2f}    |    • RSI: {rsi_attuale:.1f}    |    • Regime: {regime_mercato}\n • Stato: {stato_testo}"
        ax2.text(0.02, 0.5, info_testo, color='black', fontsize=10, family='monospace',
                 verticalalignment='center', bbox=dict(boxstyle='square,pad=0.8', fc='#e8e8e8', ec='#cccccc'))

        plt.tight_layout()
        chart_path = 'temp_chart.png'
        plt.savefig(chart_path, dpi=150, facecolor='white', edgecolor='none')
        plt.close()
        return chart_path
    except Exception as e:
        print(f"Errore generazione grafico: {e}")
        return None

# ==================== INVIO TELEGRAM ====================
def invia_messaggio_telegram(testo, chart_path=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
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
    print("Avvio ciclo Market Bot...")
    portafoglio = carica_portafoglio()

    df = ottieni_dati_coinbase()
    if df is None or len(df) < 100:
        return

    df['ema_veloce'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['ema_lenta'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['rsi'] = calcola_rsi(df['Close'], 14)
    df['atr'] = calcola_atr(df, 14)
    df['volume_ma'] = df['Volume'].rolling(window=20).mean()
    df['obv'] = calcola_obv(df)

    ultimo_prezzo = df['Close'].iloc[-1]
    rsi_attuale = df['rsi'].iloc[-1] if not np.isnan(df['rsi'].iloc[-1]) else 50.0
    atr_attuale = df['atr'].iloc[-1] if not np.isnan(df['atr'].iloc[-1]) else (ultimo_prezzo * 0.01)
    ema_v = df['ema_veloce'].iloc[-1]
    ema_l = df['ema_lenta'].iloc[-1]
    ema_macro_15m = df['ema_macro_15m'].iloc[-1]
    volume_attuale = df['Volume'].iloc[-1]
    volume_medio = df['volume_ma'].iloc[-1] if not np.isnan(df['volume_ma'].iloc[-1]) else volume_attuale
    obv_crescente = df['obv'].iloc[-1] > df['obv'].iloc[-5]

    regime_mercato = "RANGE (Laterale)"
    if abs(ema_v - ema_l) > (atr_attuale * 0.5):
        regime_mercato = "TREND (Direzionale)"

    lotti = portafoglio.get("lotti", [])
    lotti_attivi = len(lotti)
    
    now_utc = datetime.now(timezone.utc)
    timestamp_attuale = now_utc.timestamp()
    oggi_str = now_utc.strftime("%Y-%m-%d")

    # Resoconto giornaliero & Statistiche
    data_ultima = portafoglio.get("data_ultima_registrazione", oggi_str)
    if data_ultima != oggi_str:
        valore_portafoglio_attuale = portafoglio["saldo_usd"] + sum(l['quantita'] * ultimo_prezzo for l in lotti)
        valore_ieri = portafoglio.get("valore_iniziale_giornata", CAPITALE_INIZIALE)
        diff_giornaliera = valore_portafoglio_attuale - valore_ieri
        diff_perc = (diff_giornaliera / valore_ieri) * 100 if valore_ieri > 0 else 0

        storico = portafoglio.get("storico_operazioni", [])
        vittorie = [op for op in storico if op > 0]
        perdite = [op for op in storico if op < 0]
        win_rate = (len(vittorie) / len(storico) * 100) if len(storico) > 0 else 0.0
        profit_factor = (sum(vittorie) / abs(sum(perdite))) if len(perdite) > 0 and sum(perdite) != 0 else (99.9 if len(vittorie) > 0 else 0.0)

        report_giornaliero = (
            f"📅 *RESOCONTO GIORNALIERO & STATISTICHE* 📅\n\n"
            f"• Valore Portafoglio: ${valore_portafoglio_attuale:,.2f}\n"
            f"• Variazione: ${diff_giornaliera:+,.2f} ({diff_perc:+.2f}%)\n"
            f"• Win Rate: {win_rate:.1f}%\n"
            f"• Profit Factor: {profit_factor:.2f}"
        )
        invia_messaggio_telegram(report_giornaliero)
        
        portafoglio["valore_iniziale_giornata"] = valore_portafoglio_attuale
        portafoglio["data_ultima_registrazione"] = oggi_str
        portafoglio["storico_operazioni"] = []
        salva_portafoglio(portafoglio)

    quantita_totale = sum(l.get('quantita', 0) for l in lotti)
    spesa_totale = sum(l.get('spesa', 0) for l in lotti)
    prezzo_medio = (spesa_totale / quantita_totale) if quantita_totale > 0 else 0.0
    valore_attuale_posizioni = quantita_totale * ultimo_prezzo
    valore_totale_portafoglio = portafoglio["saldo_usd"] + valore_attuale_posizioni
    profitto_P_L = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100 if lotti_attivi > 0 and prezzo_medio > 0 else 0.0

    valore_iniziale_giorno = portafoglio.get("valore_iniziale_giornata", CAPITALE_INIZIALE)
    drawdown_giornaliero_pct = ((valore_iniziale_giorno - valore_totale_portafoglio) / valore_iniziale_giorno) * 100
    if drawdown_giornaliero_pct >= MAX_DAILY_DRAWDOWN_PCT:
        portafoglio["blocco_drawdown_fino"] = timestamp_attuale + 86400
        salva_portafoglio(portafoglio)

    blocco_attivo_drawdown = timestamp_attuale < portafoglio.get("blocco_drawdown_fino", 0.0)
    azione_eseguita = False
    messaggio_notifica = ""
    stato_dashboard = f"Pos ({lotti_attivi}/{MAX_LOTTI}) | P&L: {profitto_P_L:+.2f}% | Regime: {regime_mercato}"

    tempo_ultima_op = portafoglio.get("ultima_operazione_time", 0)
    puoi_operare = (timestamp_attuale - tempo_ultima_op) >= 180

    # --- 1. TAKE PROFIT DINAMICO (CON VERIFICA COMMISSIONI REALI) ---
    if puoi_operare and not azione_eseguita and lotti_attivi > 0 and prezzo_medio > 0:
        lotti_ordinati = sorted(lotti, key=lambda x: x['prezzo_entrata'], reverse=True)
        lotto_da_vendere = lotti_ordinati[0]
        
        # Simula ricavi, commissioni di vendita e profitto netto in dollari
        ricavo_lordo_simulato = lotto_da_vendere['quantita'] * ultimo_prezzo
        fee_vendita_simulata = ricavo_lordo_simulato * FEE_PERCENTUALE
        ricavo_netto_simulato = ricavo_lordo_simulato - fee_vendita_simulata
        profitto_netto_dollari = ricavo_netto_simulato - lotto_da_vendere['spesa']
        
        # Calcola la percentuale di profitto REALE netta (ripulita da fee ingresso/uscita)
        profitto_netto_perc = (profitto_netto_dollari / lotto_da_vendere['spesa']) * 100

        soglia_profitto_richiesta = 1.5 if regime_mercato == "TREND (Direzionale)" else 1.1
        
        # Il bot chiuderà solo se la percentuale NETTA supera la soglia O se l'RSI è in ipercomprato MA con profitto netto positivo in dollari
        condizione_TP_valida = (profitto_netto_perc >= soglia_profitto_richiesta) or ((rsi_attuale > 74) and (profitto_netto_dollari > 0))

        if condizione_TP_valida:
            ricavo_lordo = lotto_da_vendere['quantita'] * ultimo_prezzo
            fee_vendita = ricavo_lordo * FEE_PERCENTUALE
            ricavo_netto = ricavo_lordo - fee_vendita
            profitto_lotto = ricavo_netto - lotto_da_vendere['spesa']
            
            portafoglio["saldo_usd"] = portafoglio.get("saldo_usd", CAPITALE_INIZIALE) + ricavo_netto
            portafoglio["lotti"] = [l for l in lotti if l['id'] != lotto_da_vendere['id']]
            portafoglio["ultima_operazione_time"] = timestamp_attuale
            portafoglio.setdefault("storico_operazioni", []).append(profitto_lotto)
            
            messaggio_notifica = (
                f"🚀 *TAKE PROFIT ESEGUITO ({regime_mercato})* 🚀\n\n"
                f"• Lotto chiuso: #{lotto_da_vendere['id']}\n"
                f"• Profitto Netto: ${profitto_lotto:+,.2f} USD ({profitto_netto_perc:+.2f}% netto)\n"
                f"• Saldo USD: ${portafoglio['saldo_usd']:,.2f}"
            )
            azione_eseguita = True
            salva_portafoglio(portafoglio)

    # --- 2. STOP LOSS & TRAILING STOP DINAMICO ---
    if not azione_eseguita and lotti_attivi > 0 and prezzo_medio > 0:
        stop_loss_effettivo_perc = -2.5
        if profitto_P_L >= 3.5:
            stop_loss_effettivo_perc = +1.5
        elif profitto_P_L >= 2.0:
            stop_loss_effettivo_perc = +0.5

        soglia_sl_prezzo = prezzo_medio * (1 + (stop_loss_effettivo_perc / 100.0))
        minimo_recente = df['Low'].tail(10).min()
        soglia_strutturale = min(soglia_sl_prezzo, minimo_recente)

        if ultimo_prezzo <= soglia_strutturale:
            ricavo_lordo = quantita_totale * ultimo_prezzo
            fee_uscita = ricavo_lordo * FEE_PERCENTUALE
            ricavo_netto = ricavo_lordo - fee_uscita
            profitto_operazione = ricavo_netto - spesa_totale
            
            portafoglio["saldo_usd"] = portafoglio.get("saldo_usd", CAPITALE_INIZIALE) + ricavo_netto
            portafoglio["lotti"] = []
            portafoglio["ultima_operazione_time"] = timestamp_attuale
            portafoglio.setdefault("storico_operazioni", []).append(profitto_operazione)
            
            messaggio_notifica = f"🚨 *CHIUSURA TOTALE (STOP / TRAILING)* 🚨\n\n• Profitto/Perdita: ${profitto_operazione:+,.2f}"
            azione_eseguita = True
            salva_portafoglio(portafoglio)

    # --- 3. INGRESSI CON FILTRI QUANTITATIVI & OBV ---
    if puoi_operare and not azione_eseguita and not blocco_attivo_drawdown:
        saldo_corrente = portafoglio.get("saldo_usd", CAPITALE_INIZIALE)
        volatilita_pct = (atr_attuale / ultimo_prezzo) * 100
        fattore_size = 0.8 if volatilita_pct > 1.5 else (1.2 if volatilita_pct < 0.5 else 1.0)
        capitale_lotto_dinamico = CAPITALE_PER_LOTTO * fattore_size

        volume_confermato = volume_attuale >= (volume_medio * 0.7)
        condizione_rsi_scarico = rsi_attuale < 35
        trend_macro_ok = ultimo_prezzo > ema_macro_15m
        
        condizione_ingresso_valida = (condizione_rsi_scarico or (ema_v > ema_l and trend_macro_ok)) and volume_confermato and obv_crescente

        if lotti_attivi == 0 and condizione_ingresso_valida:
            costo_netto_lotto = capitale_lotto_dinamico
            fee_ingresso = costo_netto_lotto * FEE_PERCENTUALE
            costo_totale_con_fee = costo_netto_lotto + fee_ingresso
            
            if saldo_corrente >= costo_totale_con_fee:
                quantita = capitale_lotto_dinamico / ultimo_prezzo
                portafoglio["saldo_usd"] = saldo_corrente - costo_totale_con_fee
                portafoglio["lotti"].append({
                    "id": 1,
                    "prezzo_entrata": ultimo_prezzo,
                    "quantita": quantita,
                    "spesa": costo_totale_con_fee
                })
                portafoglio["ultima_operazione_time"] = timestamp_attuale
                
                messaggio_notifica = f"🟢 *APERTURA LOTTO (#1/{MAX_LOTTI})* 🟢\n• Prezzo: ${ultimo_prezzo:,.2f}"
                azione_eseguita = True
                salva_portafoglio(portafoglio)

    # --- REPORT DI MERCATO PERIODICO (OGNI 5 MINUTI) ---
    tempo_ultimo_report = portafoglio.get("ultimo_report_time", 0)
    puoi_inviare_report = (timestamp_attuale - tempo_ultimo_report) >= 300

    if not azione_eseguita and puoi_inviare_report:
        strategia_desc = "Trend-Following (Inseguimento trend)" if regime_mercato == "TREND (Direzionale)" else "Mean-Reversion (Range Trading)"
        previsione_mercato = "Possibile rimbalzo tecnico in arrivo." if rsi_attuale < 40 else ("Area di ipercomprato potenziale." if rsi_attuale > 65 else "Mercato in equilibrio, in attesa di volumi.")

        dettagli_posizioni = f"• Posizioni attive: {lotti_attivi}/{MAX_LOTTI}\n• Prezzo medio: ${prezzo_medio:,.2f}\n• Performance: {profitto_P_L:+.2f}%\n" if lotti_attivi > 0 else ""

        messaggio_notifica = (
            f"📈 *REPORT DI MERCATO* 📈\n\n"
            f"• Prezzo BTC: ${ultimo_prezzo:,.2f}\n"
            f"• Regime: {regime_mercato}\n"
            f"• RSI: {rsi_attuale:.1f} | ATR: ${atr_attuale:.2f}\n\n"
            f"{dettagli_posizioni}"
            f"🛠 *Strategia in uso:*\n{strategia_desc}\n\n"
            f"🔮 *Previsione Grafico:*\n{previsione_mercato}"
        )
        portafoglio["ultimo_report_time"] = timestamp_attuale
        salva_portafoglio(portafoglio)

    # Generazione grafico e invio selettivo su Telegram
    chart_path = genera_grafico_chart(df, rsi_attuale, ultimo_prezzo, stato_dashboard, regime_mercato)
    
    if azione_eseguita:
        invia_messaggio_telegram(messaggio_notifica, chart_path)
    elif puoi_inviare_report:
        invia_messaggio_telegram(messaggio_notifica, chart_path)

if __name__ == "__main__":
    try:
        esegui_bot()
    except Exception as e:
        print(f"Errore nell'esecuzione: {e}")
