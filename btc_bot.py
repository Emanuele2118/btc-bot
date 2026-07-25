import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')

FEE_RATE = 0.005  # 0.5% di commissione per transazione

def manda_messaggio_telegram(testo):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Credenziali Telegram non configurate.")
        return
    
    url_telegram = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    # Usiamo un'immagine statica di anteprima tecnica di Bitcoin stabile e supportata dai server di Telegram
    # (Un'immagine pulita del brand/grafico o uno snapshot diretto)
    photo_url = "https://s3.coinmarketcap.com/generated/sparklines/web/7d/usd/1.png" 
    # Nota: Usiamo un grafico sparkline o un'immagine statica di fallback pulita se il link dinamico viene bloccato,
    # oppure un'immagine fissa del mercato crypto.
    
    # Se vuoi un grafico reale come immagine statica, usiamo un URL diretto che restituisce un'immagine PNG:
    chart_image_url = "https://images.coinbase.com/assets/coinbase-icon-v2.png" # Usiamo un'icona o grafica ufficiale garantita.
    
    # Proviamo un URL di grafico statico generato da servizi pubblici
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png", # Immagine ufficiale BTC pulita e stabile
        "caption": testo,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url_telegram, json=payload, timeout=20)
        
        if response.status_code != 200:
            print(f"Invio foto fallito (Codice {response.status_code}). Invio come testo.")
            url_fallback = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload_fallback = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": testo + "\n\n📊 *Grafico live:* [Apri TradingView](https://it.tradingview.com/chart/?symbol=COINBASE%3ABTCUSD)",
                "parse_mode": "Markdown"
            }
            requests.post(url_fallback, json=payload_fallback)
            
    except Exception as e:
        print(f"Errore Telegram: {e}")

def registra_su_google_sheets(data_ora, tipo, prezzo, quantita, commissione, profitto_usd, motivo):
    if not GOOGLE_SHEET_URL:
        return
    payload = {
        "Data_Ora": data_ora,
        "Tipo": tipo,
        "Prezzo": f"{prezzo:.2f}",
        "Quantita_BTC": f"{quantita:.5f}",
        "Commissione_USD": f"{commissione:.2f}",
        "Profitto_Netto_USD": f"{profitto_usd:.2f}",
        "Motivo": motivo
    }
    try:
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore Google Sheets: {e}")

def run_bot():
    print("--- Inizio esecuzione Bot ---")
    try:
        url_coinbase = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url_coinbase, headers=headers, timeout=10)
        
        if response.status_code == 200:
            raw_data = response.json()
            raw_data.reverse()
            df = pd.DataFrame(raw_data, columns=['Time', 'Low', 'High', 'Open', 'Close', 'Volume'])
            df = df[['Open', 'High', 'Low', 'Close']].astype(float)
        else:
            return

        ultimo_prezzo = float(df['Close'].iloc[-1])
        timestamp_attuale = int(datetime.now(timezone.utc).timestamp())
        stringa_data = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        df['ema_veloce'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['ema_lenta'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        ema_v = float(df['ema_veloce'].iloc[-1])
        ema_l = float(df['ema_lenta'].iloc[-1])
        rsi_attuale = float(df['rsi'].iloc[-1])
        
        file_path = 'portfolio.json'
        dati = {"usd": 10000.0, "btc": 0.0, "Lotti": [], "ultima_operazione": None, "prezzo_max_raggiunto": 0.0}
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    dati = json.load(f)
                    if "Lotti" not in dati: dati["Lotti"] = []
                    if "ultima_operazione" not in dati: dati["ultima_operazione"] = None
                    if "prezzo_max_raggiunto" not in dati: dati["prezzo_max_raggiunto"] = 0.0
                except:
                    pass
                    
        messaggio = None
        tot_btc = sum(l["quantita"] for l in dati["Lotti"])
        prezzo_medio = (sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"]) / tot_btc) if tot_btc > 0 else 0.0
        profitto_perc = (((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100) if (tot_btc > 0 and prezzo_medio > 0) else 0.0
        trend_favorevole = ema_v >= (ema_l * 0.998)
        
        # Logica di trading invariata
        target_iniziale_raggiunto = profitto_perc >= 0.8
        if tot_btc > 0 and target_iniziale_raggiunto:
            if ultimo_prezzo > dati["prezzo_max_raggiunto"]:
                dati["prezzo_max_raggiunto"] = ultimo_prezzo
        else:
            dati["prezzo_max_raggiunto"] = 0.0
            
        trailing_scattato = False
        if tot_btc > 0 and dati["prezzo_max_raggiunto"] > 0:
            ritracciamento = ((dati["prezzo_max_raggiunto"] - ultimo_prezzo) / dati["prezzo_max_raggiunto"]) * 100
            if profitto_perc >= 0.8 and ritracciamento >= 0.3:
                trailing_scattato = True

        nota_retrospettiva = ""
        if dati["ultima_operazione"] is not None:
            op = dati["ultima_operazione"]
            tempo_minuti = (timestamp_attuale - op["timestamp"]) / 60
            if tempo_minuti >= 5:
                diff = ultimo_prezzo - op["prezzo"]
                perc_diff = (diff / op["prezzo"]) * 100
                if op["tipo"] == "VENDITA":
                    nota_retrospettiva = f"\n🧠 *Analisi a posteriori:* Vendita a ${op['prezzo']:,.2f} (Mercato: {perc_diff:+.2f}%)."
                else:
                    nota_retrospettiva = f"\n🧠 *Analisi a posteriori:* Acquisto a ${op['prezzo']:,.2f} (Mercato: {perc_diff:+.2f}%)."
                dati["ultima_operazione"] = None

        capitale_totale = dati["usd"] + (tot_btc * ultimo_prezzo)
        if rsi_attuale < 35 and dati["usd"] > 100 and len(dati["Lotti"]) < 3 and trend_favorevole:
            spesa_lorda = min(capitale_totale * 0.30, dati["usd"])
            comm = spesa_lorda * FEE_RATE
            qta = (spesa_lorda - comm) / ultimo_prezzo
            dati["usd"] -= spesa_lorda
            dati["Lotti"].append({"quantita": qta, "prezzo": ultimo_prezzo})
            dati["ultima_operazione"] = {"tipo": "ACQUISTO", "prezzo": ultimo_prezzo, "timestamp": timestamp_attuale}
            num_lotto = len(dati["Lotti"])
            registra_su_google_sheets(stringa_data, "ACQUISTO", ultimo_prezzo, qta, comm, 0.0, f"Lotto #{num_lotto}")
            messaggio = f"🟢 *ACQUISTO LOTTO #{num_lotto}*\n• Prezzo: ${ultimo_prezzo:,.2f}\n• Qta: {qta:.5f} BTC\n• RSI: {rsi_attuale:.1f}\n💰 USD: ${dati['usd']:,.2f}"

        elif tot_btc > 0 and (trailing_scattato or rsi_attuale > 65):
            lotto = dati["Lotti"].pop(0)
            ricavo = (lotto["quantita"] * ultimo_prezzo)
            comm = ricavo * FEE_RATE
            ricavo_netto = ricavo - comm
            profitto = ricavo_netto - (lotto["quantita"] * lotto["prezzo"])
            dati["usd"] += ricavo_netto
            dati["prezzo_max_raggiunto"] = 0.0
            dati["ultima_operazione"] = {"tipo": "VENDITA", "prezzo": ultimo_prezzo, "timestamp": timestamp_attuale}
            motivo = "Trailing Take Profit" if trailing_scattato else f"RSI ipercomprato ({rsi_attuale:.1f})"
            registra_su_google_sheets(stringa_data, "VENDITA", ultimo_prezzo, lotto["quantita"], comm, profitto, motivo)
            messaggio = f"🔵 *VENDITA PARZIALE*\n• Prezzo: ${ultimo_prezzo:,.2f}\n• Profitto: ${profitto:+,.2f}\n• Motivo: {motivo}\n💰 USD: ${dati['usd']:,.2f}"

        elif tot_btc > 0 and profitto_perc <= -1.8:
            ricavo_tot = sum(l["quantita"] * ultimo_prezzo for l in dati["Lotti"])
            comm = ricavo_tot * FEE_RATE
            perdita = (ricavo_tot - comm) - sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"])
            qta_tot = tot_btc
            dati["usd"] += (ricavo_tot - comm)
            dati["Lotti"] = []
            dati["prezzo_max_raggiunto"] = 0.0
            registra_su_google_sheets(stringa_data, "STOP_LOSS", ultimo_prezzo, qta_tot, comm, perdita, "Stop loss")
            messaggio = f"🔴 *STOP LOSS ATTUATO*\n• Perdita: -${abs(perdita):,.2f}\n💰 USD: ${dati['usd']:,.2f}"

        if not messaggio:
            if tot_btc > 0:
                valore = tot_btc * ultimo_prezzo
                p_temp = valore - sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"])
                stato = f"📈 *Posizione attiva*\n• Prezzo medio: ${prezzo_medio:,.2f}\n• Performance: ${p_temp:+,.2f} ({profitto_perc:+.2f}%)"
            else:
                stato = f"🟢 *In attesa (Trend Favorevole)*\n• RSI attuale: {rsi_attuale:.1f} (Target < 35)" if trend_favorevole else f"🔴 *In attesa protetta (Trend Ribassista)*"

            messaggio = f"🛡️ *REPORT DI MERCATO*\n• Prezzo BTC: ${ultimo_prezzo:,.2f}\n{nota_retrospettiva}\n\n{stato}"

        with open(file_path, 'w') as f:
            json.dump(dati, f)
            
        if messaggio:
            manda_messaggio_telegram(messaggio)
            
    except Exception as e:
        print(f"Errore esecuzione: {e}")

if __name__ == "__main__":
    run_bot()
