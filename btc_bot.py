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

def gestisci_portafoglio(azione, prezzo, quantita=0):
    """Gestisce il portafoglio virtuale salvandolo in un file JSON"""
    file_path = 'portfolio.json'
    
    # Valori di default se il file non esiste
    dati = {"usd": 10000.0, "btc": 0.0}
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                dati = json.load(f)
            except:
                pass
                
    messaggio = ""
    
    if azione == "COMPRA" and dati["usd"] >= (prezzo * quantita):
        spesa = prezzo * quantita
        dati["usd"] -= spesa
        dati["btc"] += quantita
        messaggio = f"🟢 **ACQUISTO SIMULATO** 🟢\n- Prezzo: ${prezzo:,.2f}\n- Quantità: {quantita} BTC\n- Spesa: ${spesa:,.2f}\n\n💰 Saldo USD: ${dati['usd']:,.2f}\n🪙 Saldo BTC: {dati['btc']}"
        
    elif azione == "VENDI" and dati["btc"] > 0:
        ricavo = dati["btc"] * prezzo
        dati["usd"] += ricavo
        quantita_venduta = dati["btc"]
        dati["btc"] = 0.0
        messaggio = f"🔴 **VENDITA SIMULATA** 🔴\n- Prezzo: ${prezzo:,.2f}\n- Quantità venduta: {quantita_venduta} BTC\n- Ricavo: ${ricavo:,.2f}\n\n💰 Saldo USD: ${dati['usd']:,.2f}\n🪙 Saldo BTC: {dati['btc']}"
        
    else:
        messaggio = None
        
    # Salva il nuovo stato
    with open(file_path, 'w') as f:
        json.dump(dati, f)
        
    return messaggio

def run_bot():
    print("--- Inizio esecuzione Bot con Paper Trading Interno ---")
    
    try:
        df = yf.download("BTC-USD", interval="1h", period="5d")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        # Indicatori
        df['ema_fast'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['ema_slow'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        ultimo_prezzo = float(df['Close'].iloc[-1])
        ema_veloce = float(df['ema_fast'].iloc[-1])
        ema_lenta = float(df['ema_slow'].iloc[-1])
        rsi_attuale = float(df['rsi'].iloc[-1])
        
        print(f"Prezzo BTC: ${ultimo_prezzo:.2f} | RSI: {rsi_attuale:.2f}")
        
        # Leggiamo il portafoglio attuale per vedere se abbiamo già BTC o USD
        file_path = 'portfolio.json'
        dati_correnti = {"usd": 10000.0, "btc": 0.0}
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                dati_correnti = json.load(f)
                
        # Logica di trading
        if ema_veloce > ema_lenta and rsi_attuale < 70 and dati_correnti["usd"] > 100:
            print("Segnale di acquisto rilevato.")
            msg = gestisci_portafoglio("COMPRA", ultimo_prezzo, quantita=0.005)
            if msg:
                manda_messaggio_telegram(msg)
                
        elif ema_veloce < ema_lenta and dati_correnti["btc"] > 0:
            print("Segnale di vendita rilevato.")
            msg = gestisci_portafoglio("VENDI", ultimo_prezzo)
            if msg:
                manda_messaggio_telegram(msg)
        else:
            print("Nessuna azione necessaria in questo momento.")
            
    except Exception as e:
        print(f"Errore: {e}")
        
    print("--- Fine esecuzione ---")

if __name__ == "__main__":
    run_bot()
