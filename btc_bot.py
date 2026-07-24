import os
import ccxt
import pandas as pd
import numpy as np
import yfinance as yf

def run_trading_bot():
    print("--- Inizio esecuzione Bot di Trading Automatizzato ---")
    
    try:
        # 1. Scarichiamo i dati di prezzo aggiornati da Yahoo Finance per i calcoli
        print("Scaricamento dati storici...")
        df = yf.download("BTC-USD", interval="1h", period="5d")
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.dropna()
        
        # 2. Calcolo Indicatori (EMA e RSI)
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
        
        # 3. Inizializziamo la connessione all'Exchange (es. Kraken) tramite CCXT
        # Per testare senza rischi, puoi abilitare la modalità sandbox se l'exchange la supporta
        exchange = ccxt.kraken({
            'apiKey': os.environ.get('EXCHANGE_API_KEY'),
            'secret': os.environ.get('EXCHANGE_SECRET_KEY'),
            'enableRateLimit': True,
        })
        
        symbol = 'BTC/USDT' # o BTC/USD a seconda dell'exchange
        
        # 4. Logica delle decisioni di trading
        if ema_veloce > ema_lenta and rsi_attuale < 70:
            print("SEGNALE DI ACQUISTO (LONG) RILEVATO!")
            
            # ATTENZIONE: Decommenta le righe sotto solo quando hai configurato le chiavi API su GitHub Secrets
            # amount_to_buy = 0.001  # Quantità di BTC da acquistare
            # order = exchange.create_market_buy_order(symbol, amount_to_buy)
            # print(f"Ordine di acquisto eseguito: {order}")
            
        elif ema_veloce < ema_lenta:
            print("SEGNALE DI VENDITA / NEUTRO RILEVATO.")
            
            # ATTENZIONE: Decommenta le righe sotto per abilitare la vendita automatica
            # balance = exchange.fetch_balance()
            # btc_balance = balance['free'].get('BTC', 0)
            # if btc_balance > 0.0001:
            #     order = exchange.create_market_sell_order(symbol, btc_balance)
            #     print(f"Ordine di vendita eseguito: {order}")
        else:
            print("Mercato in fase di indecisione. Nessuna azione eseguita.")
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot: {e}")
        
    print("--- Fine esecuzione ---")

if __name__ == "__main__":
    run_trading_bot()
