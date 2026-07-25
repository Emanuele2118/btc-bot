import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
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
                    if "ultima_attesa" not in data:
                        data["ultima_attesa"] = None
                    return data
        except Exception as e:
            print(f"Errore nella lettura del portafoglio: {e}")
    
    return {
        "saldo_usd": CAPITALE_INIZIALE,
        "lotti": [],
        "ultima_attesa": None
    }

def salva_portafoglio(portafoglio):
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portafoglio, f, indent=4)
        print("Portfolio salvato correttamente in locale.")
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

# ==================== GENERAZIONE GRAFICO OTTIMIZZATA & PULITA ====================
def genera_grafico_chart(df, rsi_attuale, prezzo_attuale, stato_testo, lotti_correnti, prezzo_medio=0.0, stop_loss_perc=0.0):
    try:
        fig, ax1 = plt.subplots(figsize=(11, 7), facecolor='white')
        ax1.set_facecolor('white')
        
        dati_plot = df.tail(90).copy().reset_index(drop=True)
        x_dates = dati_plot['Datetime']
        x_nums = mdates.date2num(x_dates)
        
        for i in range(len(dati_plot)):
            o = dati_plot['Open'].iloc[i]
            c = dati_plot['Close'].iloc[i]
            h = dati_plot['High'].iloc[i]
            l = dati_plot['Low'].iloc[i]
            
            colore = '#00897b' if c >= o else '#8e24aa'
            
            ax1.plot([x_nums[i], x_nums[i]], [l, h], color=colore, linewidth=1, zorder=1)
            bottom = min(o, c)
            height = abs(c - o) if abs(c - o) > 0 else 0.01
            ax1.bar(x_nums[i], height, bottom=bottom, color=colore, width=0.0004, zorder=2)

        ax1.plot(x_nums, dati_plot['ema_veloce'], label='EMA 9 (Veloce)', color='#fb8c00', linewidth=1.2, linestyle='--')
        ax1.plot(x_nums, dati_plot['ema_lenta'], label='EMA 50 (Lenta)', color='#3949ab', linewidth=1.2, linestyle='--')
        
        # Livelli strategici attivi
        if prezzo_medio > 0:
            ax1.axhline(y=prezzo_medio, color='#0288d1', linestyle='-.', linewidth=1.5, alpha=0.9, label=f'Prezzo Medio: ${prezzo_medio:,.2f}')
            prezzo_sl = prezzo_medio * (1 + (stop_loss_perc / 100.0))
            colore_sl = '#2e7d32' if stop_loss_perc >= 0 else '#c62828'
            etichetta_sl = f'Stop/Lockdown ({stop_loss_perc:+.1f}%): ${prezzo_sl:,.2f}'
            ax1.axhline(y=prezzo_sl, color=colore_sl, linestyle=':', linewidth=1.8, alpha=0.9, label=etichetta_sl)

        # Lotti correnti
        if lotti_correnti:
            for lotto in lotti_correnti:
                p_entrata = lotto.get("prezzo_entrata")
                id_lotto = lotto.get("id")
                ax1.axhline(y=p_entrata, color='#ffb300', linestyle=':', alpha=0.6, linewidth=1)
                ax1.text(x_nums[2], p_entrata, f' L{id_lotto} (${p_entrata:,.2f})', color='#b26a00', fontsize=8, fontweight='bold', va='bottom')

        # Prezzo attuale evidenziato a destra
        ultimo_x = x_nums[-1]
        ax1.scatter([ultimo_x], [prezzo_attuale], color='#00897b', s=60, zorder=5)
        ax1.annotate(f"${prezzo_attuale:,.2f}", 
                     xy=(ultimo_x, prezzo_attuale), 
                     xytext=(-70, 15), textcoords='offset points',
                     color='black', fontsize=9, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.3', fc='#f5f5f5', ec='#00897b', alpha=0.9))

        ax1.set_title('BTC-USD | Profit Lockdown & Strategy Map (1m)', color='black', fontsize=13, fontweight='bold', pad=15)
        ax1.tick_params(colors='black', labelsize=9)
        ax1.grid(True, color='#e0e0e0', linestyle='--', alpha=0.5)
        
        # Gestione pulita delle date sull'asse X (evita sovrapposizioni)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
        fig.autofmt_xdate(rotation=0, ha='center')
        
        for spine in ax1.spines.values():
            spine.set_color('#cccccc')
            
        # Legenda in alto a sinistra
        ax1.legend(loc='upper left', facecolor='#fafafa', edgecolor='#cccccc', labelcolor='black', fontsize=8, framealpha=0.9)

        # Pannello di controllo pulito dentro il grafico in basso a sinistra
        props = dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#ced4da', alpha=0.95)
        info_testo = f"PANNELLO CONTROLLO:\n• Prezzo: ${prezzo_attuale:,.2f} | RSI: {rsi_attuale:.1f}\n• {stato_testo}"
        ax1.text(0.02, 0.03, info_testo, transform=ax1.transAxes, fontsize=8.5, family='sans-serif', verticalalignment='bottom', bbox=props, zorder=6)

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
    profitto_P_L = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100 if lotti_attivi > 0 and prezzo_medio > 0 else 0.0
    stato_dashboard = f"Posizioni attive ({lotti_attivi}/{MAX_LOTTI}) | P&L: {profitto_P_L:+.2f}% | SL: {stop_loss_effettivo_perc:+.1f}%"

    # --- CONTROLLO USCITA (STOP LOSS / LOCKDOWN) ---
    if lotti_attivi > 0 and prezzo_medio > 0:
        soglia_sl_prezzo = prezzo_medio * (1 + (stop_loss_effettivo_perc / 100.0))
        if ultimo_prezzo <= soglia_sl_prezzo:
            ricavo = quantita_totale * ultimo_prezzo
            profitto_operazione = ricavo - spesa_totale
            portafoglio["saldo_usd"] = portafoglio.get("saldo_usd", CAPITALE_INIZIALE) + ricavo
            portafoglio["lotti"] = []
            portafoglio["ultima_attesa"] = None
            
            messaggio_notifica = (
                f"🚨 *CHIUSURA POSIZIONE (STOP / PROFIT LOCKDOWN)* 🚨\n\n"
                f"• Prezzo Chiusura: ${ultimo_prezzo:,.2f}\n"
                f"• Prezzo Medio Carico: ${prezzo_medio:,.2f}\n"
                f"• Motivo: Raggiunto il livello di protezione/stop fissato al {stop_loss_effettivo_perc:+.1f}% sul prezzo medio.\n"
                f"• Profitto/Perdita: ${profitto_operazione:+,.2f} ({((ultimo_prezzo/prezzo_medio)-1)*100:+.2f}%)\n"
                f"• Saldo USD Aggiornato: ${portafoglio['saldo_usd']:,.2f}"
            )
            azione_eseguita = True
            salva_portafoglio(portafoglio)

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
                portafoglio["ultima_attesa"] = None
                
                prezzo_medio = ultimo_prezzo
                lotti_attivi = 1
                messaggio_notifica = (
                    f"🟢 *APERTURA PRIMO LOTTO (#1/{MAX_LOTTI})* 🟢\n\n"
                    f"• Prezzo Entrata: ${ultimo_prezzo:,.2f}\n"
                    f"• Quantità: {quantita:.5f} BTC\n"
                    f"• Spesa: ${CAPITALE_PER_LOTTO:,.2f}\n"
                    f"• Motivo: RSI a {rsi_attuale:.1f} (in zona d'ingresso favorevole) e incrocio EMA veloce sopra la lenta.\n\n"
                    f"📊 Lotti attivi: 1/{MAX_LOTTI}\n"
                    f"💰 Saldo USD residuo: ${portafoglio['saldo_usd']:,.2f}"
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
                portafoglio["ultima_attesa"] = None
                
                quantita_totale = sum(l.get('quantita', 0) for l in portafoglio["lotti"])
                spesa_totale = sum(l.get('spesa', 0) for l in portafoglio["lotti"])
                prezzo_medio = spesa_totale / quantita_totale
                lotti_attivi = nuovo_id
                
                messaggio_notifica = (
                    f"🟢 *INCREMENTO POSIZIONE: LOTTO (#{nuovo_id}/{MAX_LOTTI})* 🟢\n\n"
                    f"• Prezzo Ingresso Lotto: ${ultimo_prezzo:,.2f}\n"
                    f"• Motivo: Il prezzo è sceso del {((ultimo_prezzo/prezzo_medio)-1)*100:.2f}% rispetto al prezzo medio di carico, attivando la mediazione controllata del lotto #{nuovo_id}.\n"
                    f"• Nuovo Prezzo Medio: ${prezzo_medio:,.2f}\n"
                    f"• Spesa Totale Investita: ${spesa_totale:,.2f}\n\n"
                    f"📊 Lotti attivi totali: {nuovo_id}/{MAX_LOTTI}\n"
                    f"💰 Saldo USD residuo: ${portafoglio['saldo_usd']:,.2f}"
                )
                azione_eseguita = True
                salva_portafoglio(portafoglio)

    # --- ANALISI A POSTERIORI DELL'ATTESA PRECEDENTE ---
    analisi_a_posteriori = ""
    ultima_attesa = portafoglio.get("ultima_attesa")
    
    if not azione_eseguita:
        if ultima_attesa:
            prezzo_precedente = ultima_attesa.get("prezzo", ultimo_prezzo)
            differenza_perc = ((ultimo_prezzo - prezzo_precedente) / prezzo_precedente) * 100
            
            if lotti_attivi == 0:
                if differenza_perc < -0.2:
                    analisi_a_posteriori = f"🧠 *Analisi a posteriori:* Ottima intuizione! Al controllo precedente il prezzo era a ${prezzo_precedente:,.2f} ed è stato evitato l'ingresso: il mercato è sceso del {differenza_perc:+.2f}%, confermando che l'attesa ha evitato un prezzo d'acquisto anticipato."
                elif differenza_perc > 0.2:
                    analisi_a_posteriori = f"🧠 *Analisi a posteriori:* Occasione persa. Al controllo precedente il prezzo era a ${prezzo_precedente:,.2f} e si è scelto di attendere: il mercato è salito del {differenza_perc:+.2f}%, lasciandosi sfuggire un punto d'ingresso più basso."
                else:
                    analisi_a_posteriori = f"🧠 *Analisi a posteriori:* Scelta di attesa prudente. Il prezzo è rimasto stabile (${prezzo_precedente:,.2f} ➔ ${ultimo_prezzo:,.2f}), confermando la fase di consolidamento."
            else:
                if differenza_perc > 0.2:
                    analisi_a_posteriori = f"🧠 *Analisi a posteriori:* Scelta saggia. Si è evitato di mediare a ${prezzo_precedente:,.2f} e il mercato è risalito del {differenza_perc:+.2f}%, evitando di appesantire l'esposizione in un momento sfavorevole."
                elif differenza_perc < -0.2:
                    analisi_a_posteriori = f"🧠 *Analisi a posteriori:* Attesa prematura. Si è scelto di non mediare a ${prezzo_precedente:,.2f} ma il mercato è sceso di un ulteriore {differenza_perc:+.2f}%, mancando un'occasione di accumulo più profondo."
                else:
                    analisi_a_posteriori = f"🧠 *Analisi a posteriori:* Mercato laterale rispetto al controllo precedente (${prezzo_precedente:,.2f}). Posizioni monitorate senza variazioni di rilievo."

        portafoglio["ultima_attesa"] = {
            "prezzo": ultimo_prezzo,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        salva_portafoglio(portafoglio)

        motivo_attesa = f"RSI attuale ({rsi_attuale:.1f}) non è ancora sotto la soglia d'ingresso o manca il ribasso richiesto."
        if lotti_attivi > 0:
            motivo_attesa = f"Posizioni aperte ({lotti_attivi} lotti). Il prezzo non ha ancora raggiunto la soglia di ribasso dell'1.5% per il lotto successivo e il target di profitto non è attivo."

        dettagli_posizioni = ""
        if lotti_attivi > 0:
            dettagli_posizioni = (
                f"• Posizioni attive: {lotti_attivi}/{MAX_LOTTI} lotti\n"
                f"• Prezzo medio di carico: ${prezzo_medio:,.2f}\n"
                f"• Performance netta: {profitto_P_L:+.2f}%\n"
            )

        messaggio_notifica = (
            f"🛡️ *REPORT DI MERCATO & PROFIT LOCKDOWN* 🛡️\n\n"
            f"• Prezzo BTC: ${ultimo_prezzo:,.2f}\n\n"
            f"{analisi_a_posteriori}\n\n"
            f"📌 *Analisi e Decisione del Bot (In Attesa):*\n"
            f"• RSI attuale: {rsi_attuale:.1f}\n"
            f"{dettagli_posizioni}"
            f"• Motivo dell'attesa attuale: {motivo_attesa}"
        )

    chart_path = genera_grafico_chart(df, rsi_attuale, ultimo_prezzo, stato_dashboard, portafoglio.get("lotti", []), prezzo_medio, stop_loss_effettivo_perc)
    invia_messaggio_telegram(messaggio_notifica, chart_path)
    print("Report inviato con successo su Telegram.")

if __name__ == "__main__":
    esegui_bot()
