import ccxt
import pandas as pd
import numpy as np

def run_trading_bot():
    print("--- Inizio esecuzione Bot BTC/USDT ---")
    
    # Usiamo Kraken al posto di Binance per evitare restrizioni geografiche sui server cloud
    exchange = ccxt.kraken({
        'enableRateLimit': True,
    })
    
    symbol = 'BTC/USDT'
    timeframe = '1h'
    
    try:
        print(f"Scaricamento dati storici per {symbol} ({timeframe})...")
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['ema_fast'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=50, adjust=False).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        ultimo_prezzo = df['close'].iloc[-1]
        ema_veloce = df['ema_fast'].iloc[-1]
        ema_lenta = df['ema_slow'].iloc[-1]
        rsi_attuale = df['rsi'].iloc[-1]
        
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
    print("--- Fine esecuzione ---")

if __name__ == "__main__":
    run_trading_bot()
