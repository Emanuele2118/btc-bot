import os
import json
import requests
import pandas as pd
import numpy as np
import yfinance as yf

# Configurazioni Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def manda_messaggio_telegram(testo):
    """Funzione per inviare notifiche su Telegram"""
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
    print("--- Inizio esecuzione Bot con Position Sizing Professionale ---")
    
    try:
        # 1. Scarichiamo i dati orari degli ultimi 5 giorni di Bitcoin
        df = yf.download("BTC-USD", interval="1h", period="5d")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        # 2. Calcoliamo gli indicatori tecnici:
        # - Medie Mobili Esp.", (EMA 20 e 50) per la direzione del trend
        df['ema_fast'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['ema_slow'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        # - RSI (Indice di Forza Relativa) a 14 periodi per individuare ipercomprato/ipervenduto
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # - ATR (Average True Range) per misurare la volatilità e il rischio di mercato
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=14).mean()
        
        ultimo_prezzo = float(df['Close'].iloc[-1])
        ema_veloce = float(df['ema_fast'].iloc[-1])
        ema_lenta = float(df['ema_slow'].iloc[-1])
        rsi_attuale = float(df['rsi'].iloc[-1])
        atr_attuale = float(df['atr'].iloc[-1])
        
        print(f"Prezzo BTC: ${ultimo_prezzo:.2f} | RSI: {rsi_attuale:.2f} | ATR: {atr_attuale:.2f}")
        
        # 3. Gestione del portafoglio virtuale tramite file JSON
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
        
        # 4. Strategia di Trading Principale
        # CONDIZIONE DI ACQUISTO: Trend rialzista (EMA veloce > EMA lenta) e RSI non in ipercomprato (>70)
        if ema_veloce > ema_lenta and rsi_attuale < 70 and dati["usd"] > 100:
            
            # --- POSITION SIZING MATEMATICO (Gestione del rischio avanzata) ---
            capitale_totale = dati["usd"] + (dati["btc"] * ultimo_prezzo)
            
            # Rischio massimo consentito per trade: fissato all'1.5% del patrimonio totale
            rischio_dollari = capitale_totale * 0.015 
            
            # Distanza di sicurezza basata sulla volatilità reale (ATR moltiplicato per 2)
            distanza_rischio = atr_attuale * 2
            if distanza_rischio == 0:
                distanza_rischio = ultimo_prezzo * 0.02 # fallback di sicurezza del 2%
                
            # Calcolo preciso della quantità di Bitcoin in base al rischio calcolato
            quantita = rischio_dollari / distanza_rischio
            spesa = quantita * ultimo_prezzo
            
            # Controllo di sicurezza: se la spesa supera i dollari disponibili, usiamo al massimo il 25% del cash
            if spesa > dati["usd"]:
                spesa = dati["usd"] * 0.25
                quantita = spesa / ultimo_prezzo
                
            # Bonus di acquisto se c'è un forte ipervenduto (RSI < 35): aumentiamo del 20% l'investimento
            if rsi_attuale < 35:
                spesa *= 1.2
                quantita *= 1.2
                
            dati["usd"] -= spesa
            dati["btc"] += quantita
            dati["prezzo_acquisto"] = ultimo_prezzo
            
            messaggio = (
                f"🟢 **ACQUISTO PRECISO (Risk-Managed)** 🟢\n"
                f"- Prezzo: ${ultimo_prezzo:,.2f}\n"
                f"- Quantità: {quantita:.5f} BTC\n"
                f"- Spesa calcolata: ${spesa:,.2f}\n"
                f"- Volatilità (ATR): ${atr_attuale:.2f}\n\n"
                f"💰 Saldo USD: ${dati['usd']:,.2f}\n"
                f"🪙 Saldo BTC: {dati['btc']:.5f}"
            )
            print("Segnale di acquisto preciso eseguito.")
            
        # CONDIZIONE DI VENDITA: Trend ribassista (EMA veloce < EMA lenta) se possediamo Bitcoin
        elif ema_veloce < ema_lenta and dati["btc"] > 0:
            ricavo = dati["btc"] * ultimo_prezzo
            quantita_venduta = dati["btc"]
            
            profitto_usd = ricavo - (quantita_venduta * dati["prezzo_acquisto"])
            segno = "+" if profitto_usd >= 0 else ""
            perc_operazione = (profitto_usd / (quantita_venduta * dati["prezzo_acquisto"])) * 100 if dati["prezzo_acquisto"] > 0 else 0
            
            # Liquidazione totale della posizione in Bitcoin, convertendo tutto in USD
            dati["usd"] += ricavo
            dati["btc"] = 0.0
            dati["prezzo_acquisto"] = 0.0
            
            messaggio = (
                f"🔴 **VENDITA CHIUSA** 🔴\n"
                f"- Prezzo di vendita: ${ultimo_prezzo:,.2f}\n"
                f"- Quantità venduta: {quantita_venduta:.5f} BTC\n"
                f"- Ricavo: ${ricavo:,.2f}\n"
                f"- Profitto/Perdita: {segno}${profitto_usd:,.2f} ({segno}{perc_operazione:.2f}%)\n\n"
                f"💰 Saldo USD: ${dati['usd']:,.2f}\n"
                f"🪙 Saldo BTC: ${dati['btc']}"
            )
            print("Segnale di vendita eseguito.")
            
        else:
            print("Nessun segnale di trade. Controllo posizione aperta...")
            # Se non ci sono segnali di compravendita ma abbiamo una posizione aperta, invia un report live
            if dati["btc"] > 0:
                valore_btc_attuale = dati["btc"] * ultimo_prezzo
                valore_iniziale_btc = dati["btc"] * dati["prezzo_acquisto"]
                profitto_attuale = valore_btc_attuale - valore_iniziale_btc
                perc_profitto = (profitto_attuale / valore_iniziale_btc) * 100 if valore_iniziale_btc > 0 else 0
                segno = "+" if profitto_attuale >= 0 else ""
                
                patrimonio_totale = dati["usd"] + valore_btc_attuale
                
                messaggio = (
                    f"📊 **REPORT POSIZIONE ATTUALE** 📊\n"
                    f"- Prezzo BTC: ${ultimo_prezzo:,.2f}\n"
                    f"- Prezzo d'ingresso: ${dati['prezzo_acquisto']:,.2f}\n"
                    f"- Performance live: {segno}${profitto_attuale:,.2f} ({segno}{perc_profitto:.2f}%)\n\n"
                    f"💼 Patrimonio Totale: ${patrimonio_totale:,.2f}\n"
                    f"🤖 RSI: {rsi_attuale:.1f}"
                )

        # 5. Salvataggio automatico dello stato aggiornato nel file JSON
        with open(file_path, 'w') as f:
            json.dump(dati, f)
            
        # 6. Invio della notifica Telegram (se è presente un messaggio da inviare)
        if messaggio:
            manda_messaggio_telegram(messaggio)
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot: {e}")
        
    print("--- Fine esecuzione ---")

if __name__ == "__main__":
    run_bot()
