import os
import json
import requests
import pandas as pd
import numpy as np

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def manda_messaggio_telegram(testo):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Credenziali Telegram non configurate.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": testo,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def run_bot():
    print("--- Inizio esecuzione Bot Strategia RSI + Target Rapido (1m) ---")
    
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
            print(f"Errore nel recupero dati da Coinbase: {response.status_code}")
            return

        ultimo_prezzo = float(df['Close'].iloc[-1])
        
        df['ema'] = df['Close'].ewm(span=20, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        ema_attuale = float(df['ema'].iloc[-1])
        rsi_attuale = float(df['rsi'].iloc[-1])
        
        print(f"Prezzo BTC: ${ultimo_prezzo:.2f} | RSI: {rsi_attuale:.2f} | EMA: {ema_attuale:.2f}")
        
        file_path = 'portfolio.json'
        dati = {"usd": 10000.0, "btc": 0.0, "prezzo_acquisto": 0.0}
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    dati = json.load(f)
                    if "prezzo_acquisto" not in dati:
                        dati["prezzo_acquisto"] = 0.0
                except:
                    pass
                    
        messaggio = None
        
        profitto_perc = 0.0
        if dati["btc"] > 0 and dati["prezzo_acquisto"] > 0:
            profitto_perc = ((ultimo_prezzo - dati["prezzo_acquisto"]) / dati["prezzo_acquisto"]) * 100

        # 1. ACQUISTO
        if dati["btc"] == 0 and dati["usd"] > 100:
            if rsi_attuale < 38:
                spesa = dati["usd"] * 0.40
                quantita = spesa / ultimo_prezzo
                
                dati["usd"] -= spesa
                dati["btc"] += quantita
                dati["prezzo_acquisto"] = ultimo_prezzo
                
                messaggio = (
                    f"🟢 **ACQUISTO ESEGUITO (RSI Ipervenduto)** 🟢\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"• **Prezzo:** ${ultimo_prezzo:,.2f}\n"
                    f"• **Quantità:** {quantita:.5f} BTC\n"
                    f"• **Spesa totale:** ${spesa:,.2f}\n"
                    f"• **RSI:** {rsi_attuale:.1f} (Sotto 38)\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 **Saldo USD residuo:** ${dati['usd']:,.2f}\n"
                    f"🪙 **Saldo BTC:** {dati['btc']:.5f}"
                )

        # 2. VENDITA
        elif dati["btc"] > 0:
            condizione_vendita = False
            motivo_vendita = ""
            
            if profitto_perc >= 0.6:
                condizione_vendita = True
                motivo_vendita = f"Target di profitto raggiunto (+{profitto_perc:.2f}%)."
            elif rsi_attuale > 65:
                condizione_vendita = True
                motivo_vendita = f"RSI in ipercomprato ({rsi_attuale:.1f})."
            elif profitto_perc <= -1.5:
                condizione_vendita = True
                motivo_vendita = f"Stop Loss di protezione ({profitto_perc:.2f}%)."
                
            if condizione_vendita:
                ricavo = dati["btc"] * ultimo_prezzo
                quantita_venduta = dati["btc"]
                profitto_usd = ricavo - (quantita_venduta * dati["prezzo_acquisto"])
                segno = "+" if profitto_usd >= 0 else ""
                
                dati["usd"] += ricavo
                dati["btc"] = 0.0
                dati["prezzo_acquisto"] = 0.0
                
                messaggio = (
                    f"🔴 **VENDITA CHIUSA** 🔴\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"• **Prezzo uscita:** ${ultimo_prezzo:,.2f}\n"
                    f"• **Profitto/Perdita:** {segno}${profitto_usd:,.2f} ({segno}{profitto_perc:.2f}%)\n"
                    f"• **Motivo:** {motivo_vendita}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 **Saldo USD:** ${dati['usd']:,.2f}\n"
                    f"🪙 **Saldo BTC:** {dati['btc']}"
                )

        # Report di controllo standard
        if not messaggio:
            if dati["btc"] > 0:
                valore_attuale_btc = dati["btc"] * ultimo_prezzo
                profitto_temp = valore_attuale_btc - (dati["btc"] * dati["prezzo_acquisto"])
                segno = "+" if profitto_temp >= 0 else ""
                stato = f"📈 Posizione aperta | Perf: {segno}${profitto_temp:,.2f} ({segno}{profitto_perc:.2f}%)"
            else:
                stato = f"⏳ In attesa di ipervenduto (RSI attuale: {rsi_attuale:.1f})"

            messaggio = (
                f"🛡️ **REPORT DI CONTROLLO** 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Prezzo BTC:** ${ultimo_prezzo:,.2f}\n"
                f"• **RSI (1m):** {rsi_attuale:.1f}\n\n"
                f"📌 **Stato:**\n{stato}"
            )

        with open(file_path, 'w') as f:
            json.dump(dati, f)
            
        if messaggio:
            manda_messaggio_telegram(messaggio)
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot: {e}")

if __name__ == "__main__":
    run_bot()
