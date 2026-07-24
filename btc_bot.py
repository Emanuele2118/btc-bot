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
    print("--- Inizio esecuzione Bot Day Trader (15m) ---")
    
    try:
        # 1. Scarichiamo i dati a 15 minuti degli ultimi 2 giorni (perfetto per il day trading rapido)
        df = yf.download("BTC-USD", interval="15m", period="2d")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        # 2. Indicatori Tecnici veloci per il Day Trading:
        # - Medie Mobili più reattive (EMA 9 e EMA 21)
        df['ema_fast'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['ema_slow'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        # - RSI a 14 periodi per trovare i micro-ipervenduti repentini
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # - ATR a 14 periodi per misurare la volatilità immediata
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
        
        print(f"Prezzo BTC: ${ultimo_prezzo:.2f} | RSI (15m): {rsi_attuale:.2f} | ATR: {atr_attuale:.2f}")
        
        # 3. Gestione portafoglio virtuale
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
        
        # 4. Strategia Day Trading: Reattiva e veloce
        # CONDIZIONE DI ACQUISTO: EMA veloce > EMA lenta sul grafico a 15m e RSI non tiratissimo (<75)
        if ema_veloce > ema_lenta and rsi_attuale < 75 and dati["usd"] > 100:
            
            capitale_totale = dati["usd"] + (dati["btc"] * ultimo_prezzo)
            
            # Rischio calibrato per il day trading (1% del capitale per singola operazione rapida)
            rischio_dollari = capitale_totale * 0.01 
            
            # Stop loss virtuale basato sulla volatilità stretta a 15 minuti
            distanza_rischio = atr_attuale * 1.5
            if distanza_rischio == 0:
                distanza_rischio = ultimo_prezzo * 0.01
                
            quantita = rischio_dollari / distanza_rischio
            spesa = quantita * ultimo_prezzo
            
            if spesa > dati["usd"]:
                spesa = dati["usd"] * 0.30 # Permettiamo di sfruttare fino al 30% del cash per essere più attivi
                quantita = spesa / ultimo_prezzo
                
            # Extra sprint se scatta un micro-ipervenduto a 15m (RSI < 40)
            if rsi_attuale < 40:
                spesa *= 1.25
                quantita *= 1.25
                
            dati["usd"] -= spesa
            dati["btc"] += quantita
            dati["prezzo_acquisto"] = ultimo_prezzo
            
            messaggio = (
                f"⚡ **DAY TRADE: ACQUISTO RAPIDO** ⚡\n"
                f"- Prezzo: ${ultimo_prezzo:,.2f}\n"
                f"- Quantità: {quantita:.5f} BTC\n"
                f"- Spesa: ${spesa:,.2f}\n"
                f"- RSI (15m): {rsi_attuale:.1f}\n\n"
                f"💰 Saldo USD: ${dati['usd']:,.2f}\n"
                f"🪙 Saldo BTC: {dati['btc']:.5f}"
            )
            print("Segnale di day trade (acquisto) eseguito.")
            
        # CONDIZIONE DI CHIUSURA: Non appena il micro-trend si gira al ribasso (EMA 9 < EMA 21)
        elif ema_veloce < ema_lenta and dati["btc"] > 0:
            ricavo = dati["btc"] * ultimo_prezzo
            quantita_venduta = dati["btc"]
            
            profitto_usd = ricavo - (quantita_venduta * dati["prezzo_acquisto"])
            segno = "+" if profitto_usd >= 0 else ""
            perc_operazione = (profitto_usd / (quantita_venduta * dati["prezzo_acquisto"])) * 100 if dati["prezzo_acquisto"] > 0 else 0
            
            dati["usd"] += ricavo
            dati["btc"] = 0.0
            dati["prezzo_acquisto"] = 0.0
            
            messaggio = (
                f"🎯 **DAY TRADE: POSIZIONE CHIUSA** 🎯\n"
                f"- Prezzo di uscita: ${ultimo_prezzo:,.2f}\n"
                f"- Quantità: {quantita_venduta:.5f} BTC\n"
                f"- Ricavo: ${ricavo:,.2f}\n"
                f"- Profitto/Perdita: {segno}${profitto_usd:,.2f} ({segno}{perc_operazione:.2f}%)\n\n"
                f"💰 Saldo USD: ${dati['usd']:,.2f}\n"
                f"🪙 Saldo BTC: ${dati['btc']}"
            )
            print("Segnale di chiusura day trade eseguito.")
            
        else:
            print("Nessun segnale di day trade in corso...")
            if dati["btc"] > 0:
                valore_btc_attuale = dati["btc"] * ultimo_prezzo
                valore_iniziale_btc = dati["btc"] * dati["prezzo_acquisto"]
                profitto_attuale = valore_btc_attuale - valore_iniziale_btc
                perc_profitto = (profitto_attuale / valore_iniziale_btc) * 100 if valore_iniziale_btc > 0 else 0
                segno = "+" if profitto_attuale >= 0 else ""
                
                patrimonio_totale = dati["usd"] + valore_btc_attuale
                
                messaggio = (
                    f"📊 **REPORT DAY TRADING LIVE** 📊\n"
                    f"- Prezzo BTC: ${ultimo_prezzo:,.2f}\n"
                    f"- Ingresso: ${dati['prezzo_acquisto']:,.2f}\n"
                    f"- Performance: {segno}${profitto_attuale:,.2f} ({segno}{perc_profitto:.2f}%)\n\n"
                    f"💼 Patrimonio: ${patrimonio_totale:,.2f}\n"
                    f"⚡ RSI (15m): {rsi_attuale:.1f}"
                )

        with open(file_path, 'w') as f:
            json.dump(dati, f)
            
        if messaggio:
            manda_messaggio_telegram(messaggio)
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot day trader: {e}")
        
    print("--- Fine esecuzione ---")

if __name__ == "__main__":
    run_bot()
