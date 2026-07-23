import pandas as pd
import numpy as np
import yfinance as yf

def run_trading_bot():
    print("--- Inizio esecuzione Bot BTC-USD ---")
    
    try:
        print("Scaricamento dati storici da Yahoo Finance...")
        # Scarica gli ultimi dati storici di Bitcoin (BTC-USD) a intervalli di 1 ora
        df = yf.download("BTC-USD", interval="1h", period="5d")
        
        # Pulizia della struttura dati
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.dropna()
        
        # Calcolo degli indicatori tecnici
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
        
        print(f"Prezzo attuale BTC: ${ultimo_prezzo:.2f}")
        print(f"EMA Veloce: {ema_veloce:.2f} | EMA Lenta: {ema_lenta:.2f} | RSI: {rsi_attuale:.2f}")
        
        if ema_veloce > ema_lenta and rsi_attuale < 70:
            print("SEGNALE DI ACQUISTO (LONG) RILEVATO!")
        elif ema_veloce < ema_lenta:
            print("SEGNALE DI VENDITA / NEUTRO RILEVATO.")
        else:
            print("Mercato in fase di indecisione. Il bot resta in attesa.")
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot: {e}")
        
    print("--- Fine esecuzione ---")

if __name__ == "__main__":
    run_trading_bot()
