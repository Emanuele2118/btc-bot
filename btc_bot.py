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
    print("--- Inizio esecuzione Bot Formativo (15m) ---")
    
    try:
        # 1. Scarichiamo i dati a 15 minuti degli ultimi 2 giorni
        df = yf.download("BTC-USD", interval="15m", period="2d")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        
        # 2. Indicatori Tecnici (EMA 9 e 21, RSI, ATR)
        df['ema_fast'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['ema_slow'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
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
        
        print(f"Prezzo BTC: ${ultimo_prezzo:.2f} | RSI (15m): {rsi_attuale:.2f} | EMA Veloce: {ema_veloce:.2f} | EMA Lenta: {ema_lenta:.2f}")
        
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
        
        # 4. Logica di Trading con Motivazioni Dettagliate
        
        # CONDIZIONE DI ACQUISTO
        if ema_veloce > ema_lenta and rsi_attuale < 75 and dati["usd"] > 100:
            capitale_totale = dati["usd"] + (dati["btc"] * ultimo_prezzo)
            rischio_dollari = capitale_totale * 0.01 
            distanza_rischio = atr_attuale * 1.5
            if distanza_rischio == 0:
                distanza_rischio = ultimo_prezzo * 0.01
                
            quantita = rischio_dollari / distanza_rischio
            spesa = quantita * ultimo_prezzo
            
            if spesa > dati["usd"]:
                spesa = dati["usd"] * 0.30
                quantita = spesa / ultimo_prezzo
                
            bonus_testo = ""
            if rsi_attuale < 40:
                spesa *= 1.25
                quantita *= 1.25
                bonus_testo = " (Bonus ipervenduto RSI < 40 applicato!)"
                
            dati["usd"] -= spesa
            dati["btc"] += quantita
            dati["prezzo_acquisto"] = ultimo_prezzo
            
            messaggio = (
                f"🟢 **ACQUISTO ESEGUITO** 🟢\n"
                f"• **Prezzo:** ${ultimo_prezzo:,.2f}\n"
                f"• **Quantità:** {quantita:.5f} BTC\n"
                f"• **Spesa:** ${spesa:,.2f}{bonus_testo}\n\n"
                f"📊 **Perché ho comprato?**\n"
                f"- L'EMA veloce ({ema_veloce:.1f}) è sopra l'EMA lenta ({ema_lenta:.1f}): trend rialzista.\n"
                f"- L'RSI ({rsi_attuale:.1f}) è sotto 75 (mercato non in ipercomprato estremo).\n\n"
                f"💰 Saldo USD: ${dati['usd']:,.2f}\n"
                f"🪙 Saldo BTC: {dati['btc']:.5f}"
            )
            
        # CONDIZIONE DI VENDITA
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
                f"🔴 **VENDITA CHIUSA** 🔴\n"
                f"• **Prezzo uscita:** ${ultimo_prezzo:,.2f}\n"
                f"• **Profitto/Perdita:** {segno}${profitto_usd:,.2f} ({segno}{perc_operazione:.2f}%)\n\n"
                f"📊 **Perché ho venduto?**\n"
                f"- L'EMA veloce ({ema_veloce:.1f}) è scesa sotto l'EMA lenta ({ema_lenta:.1f}): inversione del trend ribassista.\n\n"
                f"💰 Saldo USD: ${dati['usd']:,.2f}\n"
                f"🪙 Saldo BTC: {dati['btc']}"
            )
            
        # NESSUN ORDINE: Spieghiamo il motivo esatto
        else:
            motivo = ""
            if dati["btc"] > 0:
                # Abbiamo una posizione aperta, spieghiamo perché la teniamo
                valore_btc_attuale = dati["btc"] * ultimo_prezzo
                valore_iniziale_btc = dati["btc"] * dati["prezzo_acquisto"]
                profitto_attuale = valore_btc_attuale - valore_iniziale_btc
                perc_profitto = (profitto_attuale / valore_iniziale_btc) * 100 if valore_iniziale_btc > 0 else 0
                segno = "+" if profitto_attuale >= 0 else ""
                
                motivo = (
                    f"📈 **Posizione aperta in corso**\n"
                    f"- Il trend è ancora favorevole o non si è ancora invertito.\n"
                    f"- Performance live: {segno}${profitto_attuale:,.2f} ({segno}{perc_profitto:.2f}%)\n"
                    f"- EMA Veloce: {ema_veloce:.1f} | EMA Lenta: {ema_lenta:.1f}"
                )
            else:
                # Siamo senza Bitcoin, spieghiamo perché non compra
                if ema_veloce <= ema_lenta:
                    motivo = f"⏳ **In attesa (Trend ribassista)**\nL'EMA veloce ({ema_veloce:.1f}) si trova sotto l'EMA lenta ({ema_lenta:.1f}). Aspetto che il trend giri al rialzo."
                elif rsi_attuale >= 75:
                    motivo = f"⚠️ **In attesa (Mercato troppo tirato)**\nL'RSI è a {rsi_attuale:.1f} (sopra 75): il prezzo è in forte ipercomprato, rischio di acquisto sui massimi evitato."
                else:
                    motivo = "🔍 **In attesa di condizioni ottimali**\nIl mercato sta consolidando."

            messaggio = (
                f"ℹ️ **REPORT DI CONTROLLO (Nessun trade)** ℹ️\n"
                f"• **Prezzo BTC:** ${ultimo_prezzo:,.2f}\n"
                f"• **RSI (15m):** {rsi_attuale:.1f}\n\n"
                f"📝 **Motivo dello stop:**\n{motivo}"
            )

        # 5. Salvataggio stato
        with open(file_path, 'w') as f:
            json.dump(dati, f)
            
        # 6. Invio notifica Telegram (ora invia SEMPRE un report educativo)
        if messaggio:
            manda_messaggio_telegram(messaggio)
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot: {e}")

if __name__ == "__main__":
    run_bot()
