import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
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
CAPITALE_PER_LOTTO = 600.0   # Ridotto per consentire più lotti attivi
MAX_LOTTI = 15               # Aumentato a 15 lotti massimi
FEE_PERCENTUALE = 0.001        
MAX_DAILY_DRAWDOWN_PCT = 4.0  

# ==================== 1. DATA ENGINE ====================
class DataEngine:
    @staticmethod
    def ottieni_dati():
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
            print(f"Errore connessione Coinbase: {e}")

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

# ==================== 2. RISK MANAGEMENT ENGINE ====================
class RiskManagementEngine:
    @staticmethod
    def calcola_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Low'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=periodo).mean()

    @staticmethod
    def verifica_drawdown_giornaliero(portafoglio, valore_totale_portafoglio, timestamp_attuale):
        valore_iniziale_giorno = portafoglio.get("valore_iniziale_giornata", CAPITALE_INIZIALE)
        drawdown_giornaliero_pct = ((valore_iniziale_giorno - valore_totale_portafoglio) / valore_iniziale_giorno) * 100
        
        if drawdown_giornaliero_pct >= MAX_DAILY_DRAWDOWN_PCT:
            portafoglio["blocco_drawdown_fino"] = timestamp_attuale + 86400
            return True
        return timestamp_attuale < portafoglio.get("blocco_drawdown_fino", 0.0)

# ==================== 3. STRATEGY ENGINE ====================
class StrategyEngine:
    @staticmethod
    def analizza_mercato(df):
        df['ema_veloce'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['ema_lenta'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['atr'] = RiskManagementEngine.calcola_atr(df, 14)
        df['volume_ma'] = df['Volume'].rolling(window=20).mean()
        df['obv'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        
        ultimo_prezzo = df['Close'].iloc[-1]
        rsi_attuale = df['rsi'].iloc[-1] if not np.isnan(df['rsi'].iloc[-1]) else 50.0
        atr_attuale = df['atr'].iloc[-1] if not np.isnan(df['atr'].iloc[-1]) else (ultimo_prezzo * 0.01)
        ema_v = df['ema_veloce'].iloc[-1]
        ema_l = df['ema_lenta'].iloc[-1]
        volume_attuale = df['Volume'].iloc[-1]
        volume_medio = df['volume_ma'].iloc[-1] if not np.isnan(df['volume_ma'].iloc[-1]) else volume_attuale
        obv_crescente = df['obv'].iloc[-1] > df['obv'].iloc[-5]

        regime = "RANGE (Difensivo)"
        if abs(ema_v - ema_l) > (atr_attuale * 0.4) and ema_v > ema_l and obv_crescente:
            regime = "TREND (Aggressivo)"
            
        return ultimo_prezzo, rsi_attuale, atr_attuale, ema_v, ema_l, volume_attuale, volume_medio, obv_crescente, regime

# ==================== 4. EXECUTION & NOTIFICATION ENGINE ====================
class ExecutionEngine:
    @staticmethod
    def carica_portafoglio():
        data = None
        if os.path.exists(PORTFOLIO_FILE):
            try:
                with open(PORTFOLIO_FILE, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Errore lettura file: {e}")
                
        if not data and os.path.exists(PORTFOLIO_BACKUP_FILE):
            try:
                with open(PORTFOLIO_BACKUP_FILE, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Errore lettura backup: {e}")

        if isinstance(data, dict):
            if "saldo_usd" not in data: data["saldo_usd"] = CAPITALE_INIZIALE
            if "lotti" not in data: data["lotti"] = []
            if "ultima_operazione_time" not in data: data["ultima_operazione_time"] = 0
            if "ultimo_report_time" not in data: data["ultimo_report_time"] = 0.0
            if "valore_iniziale_giornata" not in data: data["valore_iniziale_giornata"] = CAPITALE_INIZIALE
            if "data_ultima_registrazione" not in data: data["data_ultima_registrazione"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if "blocco_drawdown_fino" not in data: data["blocco_drawdown_fino"] = 0.0
            if "storico_operazioni" not in data: data["storico_operazioni"] = []
            return data
        
        return {
            "saldo_usd": CAPITALE_INIZIALE, "lotti": [], "ultima_operazione_time": 0,
            "ultimo_report_time": 0.0, "valore_iniziale_giornata": CAPITALE_INIZIALE,
            "data_ultima_registrazione": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "blocco_drawdown_fino": 0.0, "storico_operazioni": []
        }

    @staticmethod
    def salva_portafoglio(portafoglio):
        try:
            with open(PORTFOLIO_FILE, 'w') as f: json.dump(portafoglio, f, indent=4)
            with open(PORTFOLIO_BACKUP_FILE, 'w') as f: json.dump(portafoglio, f, indent=4)
        except Exception as e:
            print(f"Errore salvataggio: {e}")

    @staticmethod
    def invia_telegram(testo, chart_path=None):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        try:
            if chart_path and os.path.exists(chart_path):
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                with open(chart_path, 'rb') as photo:
                    requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': testo, 'parse_mode': 'Markdown'}, files={'photo': photo}, timeout=20)
            else:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': testo, 'parse_mode': 'Markdown'}, timeout=10)
        except Exception as e:
            print(f"Errore Telegram: {e}")

    @staticmethod
    def genera_grafico(df, rsi, prezzo, stato, regime):
        try:
            fig = plt.figure(figsize=(10, 7.5), facecolor='white')
            gs = fig.add_gridspec(2, 1, height_ratios=[4, 1.3])
            ax1 = fig.add_subplot(gs[0])
            ax1.set_facecolor('white')
            
            dati_plot = df.tail(100).copy().reset_index(drop=True)
            x = range(len(dati_plot))
            
            for i in x:
                o, c, h, l = dati_plot['Open'].iloc[i], dati_plot['Close'].iloc[i], dati_plot['High'].iloc[i], dati_plot['Low'].iloc[i]
                colore = '#26a69a' if c >= o else '#9c27b0'
                ax1.plot([i, i], [l, h], color=colore, linewidth=1, zorder=1)
                ax1.bar(i, abs(c - o) if abs(c - o) > 0 else 0.01, bottom=min(o, c), color=colore, width=0.6, zorder=2)

            ax1.plot(x, dati_plot['ema_veloce'], label='EMA 9', color='#ff9800', linewidth=1.2, linestyle='--')
            ax1.plot(x, dati_plot['ema_lenta'], label='EMA 50', color='#3f51b5', linewidth=1.2, linestyle='--')
            
            ultimo_idx = len(x) - 1
            ax1.scatter([ultimo_idx], [prezzo], color='#26a69a', s=45, zorder=5)
            ax1.set_title(f'BTC-USD | Pro Architecture Engine ({regime})', color='black', fontsize=13, fontweight='bold', pad=12)
            ax1.grid(True, color='#e0e0e0', linestyle=':', alpha=0.7)
            ax1.legend(loc='upper left', facecolor='#f9f9f9', edgecolor='none', labelcolor='black', fontsize=8)

            ax2 = fig.add_subplot(gs[1])
            ax2.set_facecolor('#f4f4f4')
            ax2.axis('off')
            info_testo = f" PRO ENGINE DASHBOARD\n • Prezzo: ${prezzo:,.2f}    |    • RSI: {rsi:.1f}    |    • Regime: {regime}\n • Stato: {stato}"
            ax2.text(0.02, 0.5, info_testo, color='black', fontsize=10, family='monospace', verticalalignment='center', bbox=dict(boxstyle='square,pad=0.8', fc='#e8e8e8', ec='#cccccc'))

            plt.tight_layout()
            path = 'temp_chart.png'
            plt.savefig(path, dpi=150, facecolor='white', edgecolor='none')
            plt.close()
            return path
        except Exception as e:
            print(f"Errore grafico: {e}")
            return None

# ==================== WEB SERVER PER RENDER (WEB SERVICE) ====================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Bot is active and running 24/7!</h1></body></html>")
    
    def log_message(self, format, *args):
        return

def avvia_server_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# ==================== MAIN PIPELINE ====================
def esegui_ciclo():
    portafoglio = ExecutionEngine.carica_portafoglio()
    df = DataEngine.ottieni_dati()
    if df is None or len(df) < 100: return

    prezzo, rsi, atr, ema_v, ema_l, vol, vol_med, obv_cresc, regime = StrategyEngine.analizza_mercato(df)
    
    lotti = portafoglio.get("lotti", [])
    lotti_attivi = len(lotti)
    now_utc = datetime.now(timezone.utc)
    ts = now_utc.timestamp()
    oggi_str = now_utc.strftime("%Y-%m-%d")

    if portafoglio.get("data_ultima_registrazione", oggi_str) != oggi_str:
        val_portafoglio = portafoglio["saldo_usd"] + sum(l['quantita'] * prezzo for l in lotti)
        val_ieri = portafoglio.get("valore_iniziale_giornata", CAPITALE_INIZIALE)
        diff = val_portafoglio - val_ieri
        diff_p = (diff / val_ieri) * 100 if val_ieri > 0 else 0
        
        storico = portafoglio.get("storico_operazioni", [])
        vittorie = [op for op in storico if op > 0]
        win_rate = (len(vittorie) / len(storico) * 100) if len(storico) > 0 else 0.0

        msg_giorno = (
            f"📅 *RESOCONTO GIORNALIERO SMART* 📅\n\n"
            f"Portafoglio totale a ${val_portafoglio:,.2f}, "
            f"siamo a ${diff:+,.2f} ({diff_p:+.2f}%).\n"
            f"Win rate del {win_rate:.1f}%."
        )
        ExecutionEngine.invia_telegram(msg_giorno)
        portafoglio["valore_iniziale_giornata"] = val_portafoglio
        portafoglio["data_ultima_registrazione"] = oggi_str
        portafoglio["storico_operazioni"] = []
        ExecutionEngine.salva_portafoglio(portafoglio)

    q_tot = sum(l['quantita'] for l in lotti)
    spesa_tot = sum(l['spesa'] for l in lotti)
    prezzo_medio = (spesa_tot / q_tot) if q_tot > 0 else 0.0
    valore_pos = q_tot * prezzo
    valore_totale = portafoglio["saldo_usd"] + valore_pos
    pnl_perc = ((prezzo - prezzo_medio) / prezzo_medio) * 100 if lotti_attivi > 0 and prezzo_medio > 0 else 0.0

    blocco_dd = RiskManagementEngine.verifica_drawdown_giornaliero(portafoglio, valore_totale, ts)
    if blocco_dd:
        ExecutionEngine.salva_portafoglio(portafoglio)
        return

    azione_eseguita = False
    messaggio = ""
    stato_dash = f"Pos ({lotti_attivi}/{MAX_LOTTI}) | P&L: {pnl_perc:+.2f}% | Regime: {regime}"
    puoi_operare = (ts - portafoglio.get("ultima_operazione_time", 0)) >= 900  

    # 1. TAKE PROFIT
    if puoi_operare and not azione_eseguita and lotti_attivi > 0 and prezzo_medio > 0:
        lotto = sorted(lotti, key=lambda x: x['prezzo_entrata'], reverse=True)[0]
        ricavo_lordo = lotto['quantita'] * prezzo
        fee_v = ricavo_lordo * FEE_PERCENTUALE
        netto_sim = ricavo_lordo - fee_v
        profitto_dollari = netto_sim - lotto['spesa']
        profitto_p = (profitto_dollari / lotto['spesa']) * 100

        soglia_tp = 2.0 if regime == "TREND (Aggressivo)" else 1.1
        if (profitto_p >= soglia_tp) or (rsi > 74 and profitto_dollari > 0):
            portafoglio["saldo_usd"] += netto_sim
            portafoglio["lotti"] = [l for l in lotti if l['id'] != lotto['id']]
            portafoglio["ultima_operazione_time"] = ts
            portafoglio.setdefault("storico_operazioni", []).append(profitto_dollari)
            
            messaggio = (
                f"🚀 *TAKE PROFIT ({regime})* 🚀\n\n"
                f"Chiuso il lotto #{lotto['id']} in positivo. "
                f"Profitto: ${profitto_dollari:+,.2f} netti ({profitto_p:+.2f}%).\n"
                f"💰 *Saldo attuale:* ${portafoglio['saldo_usd']:,.2f}"
            )
            azione_eseguita = True
            ExecutionEngine.salva_portafoglio(portafoglio)

    # 2. STOP LOSS
    if not azione_eseguita and lotti_attivi > 0 and prezzo_medio > 0:
        sl_perc = -2.2 if regime == "TREND (Aggressivo)" else -2.8
        if pnl_perc >= 3.5: sl_perc = 1.5
        elif pnl_perc >= 2.0: sl_perc = 0.5

        soglia_prezzo = prezzo_medio * (1 + (sl_perc / 100.0))
        soglia_atr_dinamica = prezzo - (atr * 1.8)
        soglia_finale = min(soglia_prezzo, soglia_atr_dinamica)

        if prezzo <= soglia_finale:
            ricavo_tot = q_tot * prezzo
            fee_uscita = ricavo_tot * FEE_PERCENTUALE
            netto_uscita = ricavo_tot - fee_uscita
            profitto_op = netto_uscita - spesa_tot
            
            portafoglio["saldo_usd"] += netto_uscita
            portafoglio["lotti"] = []
            portafoglio["ultima_operazione_time"] = ts
            portafoglio.setdefault("storico_operazioni", []).append(profitto_op)
            
            messaggio = (
                f"🚨 *CHIUSURA DIFENSIVA (STOP LOSS)* 🚨\n\n"
                f"Chiuso tutto con ${profitto_op:+,.2f}.\n"
                f"💰 *Saldo attuale:* ${portafoglio['saldo_usd']:,.2f}"
            )
            azione_eseguita = True
            ExecutionEngine.salva_portafoglio(portafoglio)

    # 3. INGRESSI DINAMICI
    if puoi_operare and not azione_eseguita:
        saldo = portafoglio.get("saldo_usd", CAPITALE_INIZIALE)
        fattore = (1.25 if lotti_attivi == 0 else 1.1) if regime == "TREND (Aggressivo)" else 0.85
        capitale_lotto = CAPITALE_PER_LOTTO * fattore

        vol_ok = vol >= (vol_med * (0.6 if regime == "TREND (Aggressivo)" else 0.8))
        cond_ingr = (ema_v > ema_l and prezzo > df['ema_macro_15m'] and vol_ok and obv_cresc) if regime == "TREND (Aggressivo)" else (rsi < 38 and vol_ok)

        if lotti_attivi < MAX_LOTTI and cond_ingr:
            costo_netto = capitale_lotto
            costo_tot = costo_netto + (costo_netto * FEE_PERCENTUALE)
            
            if saldo >= costo_tot:
                quantita = capitale_lotto / prezzo
                portafoglio["saldo_usd"] = saldo - costo_tot
                nuovo_id = len(portafoglio["lotti"]) + 1
                
                portafoglio["lotti"].append({
                    "id": nuovo_id, 
                    "prezzo_entrata": prezzo, 
                    "quantita": quantita, 
                    "spesa": costo_tot
                })
                portafoglio["ultima_operazione_time"] = ts
                
                messaggio = (
                    f"🟢 *APERTURA LOTTO SMART (#{nuovo_id}/{MAX_LOTTI} - {regime})* 🟢\n\n"
                    f"• Prezzo d'ingresso: ${prezzo:,.2f}\n"
                    f"💰 *Saldo residuo:* ${portafoglio['saldo_usd']:,.2f}"
                )
                azione_eseguita = True
                ExecutionEngine.salva_portafoglio(portafoglio)

    # REPORT PERIODICO (BLINDATO CON TIMER RIGOROSO)
    ultimo_rep = portafoglio.get("ultimo_report_time", 0.0)
    if ultimo_rep is None:
        ultimo_rep = 0.0
        
    tempo_trascorso = ts - ultimo_rep
    puoi_report = tempo_trascorso >= 300

    if not azione_eseguita and puoi_report:
        dett_pos = f"• Posizioni attive: {lotti_attivi}/{MAX_LOTTI}\n• Prezzo medio: ${prezzo_medio:,.2f}\n• Rendimento (P&L): {pnl_perc:+.2f}%\n" if lotti_attivi > 0 else "• Nessun lotto attivo.\n"

        messaggio = (
            f"📈 *REPORT SMART DI MERCATO* 📈\n\n"
            f"• Bitcoin: ${prezzo:,.2f}\n"
            f"• Situazione: {regime}\n"
            f"• RSI: {rsi:.1f} | ATR: ${atr:.2f}\n\n"
            f"{dett_pos}"
        )
        portafoglio["ultimo_report_time"] = ts
        ExecutionEngine.salva_portafoglio(portafoglio)
        
        chart = ExecutionEngine.genera_grafico(df, rsi, prezzo, stato_dash, regime)
        ExecutionEngine.invia_telegram(messaggio, chart)

if __name__ == "__main__":
    print("Avvio del server web per Render...")
    server_thread = threading.Thread(target=avvia_server_web, daemon=True)
    server_thread.start()

    print("Bot avviato in modalità cloud 24/7...")
    while True:
        try:
            esegui_ciclo()
        except Exception as e:
            print(f"Errore nel ciclo: {e}")
        time.sleep(300)
