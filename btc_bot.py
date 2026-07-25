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
    print("--- Inizio esecuzione Bot Dinamico Frazionato (1m) ---")
    
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
        # Struttura dati avanzata per gestire acquisti multipli
        dati = {
            "usd": 10000.0, 
            "btc": 0.0, 
            "prezzo_acquisto": 0.0,
            "Lotti": [] # Storico dei singoli lotti acquistati
        }
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    dati = json.load(f)
                    if "Lotti" not in dati:
                        dati["Lotti"] = []
                        if dati["btc"] > 0 and dati["prezzo_acquisto"] > 0:
                            # Retrocompatibilità se c'era già un vecchio lotto unico
                            dati["Lotti"].append({"quantita": dati["btc"], "prezzo": dati["prezzo_acquisto"]})
                except:
                    pass
                    
        messaggio = None
        
        # Calcoliamo il prezzo medio di carico ponderato
        tot_btc = sum(lotto["quantita"] for lotto in dati["Lotti"])
        prezzo_medio = 0.0
        if tot_btc > 0:
            costo_totale = sum(lotto["quantita"] * lotto["prezzo"] for lotto in dati["Lotti"])
            prezzo_medio = costo_totale / tot_btc
            
        profitto_perc = 0.0
        if tot_btc > 0 and prezzo_medio > 0:
            profitto_perc = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100

        # --- LOGICA DINAMICA FRAZIONATA ---
        
        # 1. ACQUISTO AGGIUNTIVO (Se l'RSI è in ipervenduto e abbiamo USD)
        # Permette di comprare fino a un massimo di 4 lotti separati se il mercato scende a ondate
        if rsi_attuale < 38 and dati["usd"] > 100 and len(dati["Lotti"]) < 4:
            # Controlliamo anche che l'ultimo lotto non sia stato preso proprio allo stesso prezzo esatto (evita spam nello stesso minuto)
            ultimo_prezzo_lotto = dati["Lotti"][-1]["prezzo"] if len(dati["Lotti"]) > 0 else 0
            
            if ultimo_prezzo_lotto == 0 or abs(ultimo_prezzo_lotto - ultimo_prezzo) > (ultimo_prezzo * 0.001):
                spesa = dati["usd"] * 0.25 # Impegna il 25% del capitale rimanente per questo lotto
                quantita = spesa / ultimo_prezzo
                
                dati["usd"] -= spesa
                dati["Lotti"].append({"quantita": quantita, "prezzo": ultimo_prezzo})
                dati["btc"] = sum(l.get("quantita", 0) for l in dati["Lotti"])
                dati["prezzo_acquisto"] = prezzo_medio # Aggiornato per compattezza
                
                num_lotto = len(dati["Lotti"])
                messaggio = (
                    f"🟢 **ACQUISTO LOTTO #{num_lotto} (Dinamico)** 🟢\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"• **Prezzo attuale:** ${ultimo_prezzo:,.2f}\n"
                    f"• **Quantità lotto:** {quantita:.5f} BTC\n"
                    f"• **Spesa:** ${spesa:,.2f}\n"
                    f"• **RSI:** {rsi_attuale:.1f} (Ipervenduto)\n\n"
                    f"📊 **Stato Portafoglio:**\n"
                    f"• **Prezzo medio carico:** ${prezzo_medio:,.2f}\n"
                    f"• **Totale BTC accumulati:** {dati['btc']:.5f}\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 **Saldo USD residuo:** ${dati['usd']:,.2f}"
                )

        # 2. VENDITA PARZIALE (Se siamo in profitto del +0.5% o l'RSI è in ipercomprato > 65, vendiamo metà dei lotti per capitalizzare)
        elif tot_btc > 0 and (profitto_perc >= 0.5 or rsi_attuale > 65):
            # Vendiamo il lotto più vecchio (il primo della lista) per realizzare il profitto e liberare liquidità
            lotto_da_vendere = dati["Lotti"].pop(0)
            quantita_venduta = lotto_da_vendere["quantita"]
            prezzo_carico_lotto = lotto_da_vendere["prezzo"]
            
            ricavo = quantita_venduta * ultimo_prezzo
            profitto_lotto_usd = ricavo - (quantita_venduta * prezzo_carico_lotto)
            perc_lotto = ((ultimo_prezzo - prezzo_carico_lotto) / prezzo_carico_lotto) * 100
            segno = "+" if profitto_lotto_usd >= 0 else ""
            
            dati["usd"] += ricavo
            dati["btc"] = sum(l.get("quantita", 0) for l in dati["Lotti"])
            
            motivo = f"Target profitto raggiunto (+{perc_lotto:.2f}%)" if profitto_perc >= 0.5 else f"RSI in ipercomprato ({rsi_attuale:.1f})"
            
            messaggio = (
                f"🔵 **VENDITA PARZIALE (Prelievo Profitto)** 🔵\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Prezzo uscita:** ${ultimo_prezzo:,.2f}\n"
                f"• **Quantità venduta:** {quantita_venduta:.5f} BTC\n"
                f"• **Profitto sul lotto:** {segno}${profitto_lotto_usd:,.2f} ({segno}{perc_lotto:.2f}%)\n"
                f"• **Motivo:** {motivo}\n\n"
                f"📊 **Stato residuo:**\n"
                f"• **Lotti ancora attivi:** {len(dati['Lotti'])}\n"
                f"• **Totale BTC rimasti:** {dati['btc']:.5f}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **Saldo USD:** ${dati['usd']:,.2f}"
            )

        # 3. STOP LOSS TOTALE DI EMERGENZA (Se il portafoglio globale perde oltre l'-2.0%)
        elif tot_btc > 0 and profitto_perc <= -2.0:
            ricavo_totale = sum(l["quantita"] * ultimo_prezzo for l in dati["Lotti"])
            costo_totale_iniziale = sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"])
            perdita_usd = ricavo_totale - costo_totale_iniziale
            
            dati["usd"] += ricavo_totale
            dati["Lotti"] = []
            dati["btc"] = 0.0
            
            messaggio = (
                f"🔴 **STOP LOSS DI EMERGENZA** 🔴\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Prezzo uscita totale:** ${ultimo_prezzo:,.2f}\n"
                f"• **Perdita registrata:** -${abs(perdita_usd):,.2f} ({profitto_perc:.2f}%)\n"
                f"• **Motivo:** Chiusura di protezione per ribasso prolungato.\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **Saldo USD:** ${dati['usd']:,.2f}\n"
                f"🪙 **Saldo BTC:** 0.0"
            )

        # Report di controllo dettagliato se non ci sono azioni di compravendita immediate
        if not messaggio:
            if tot_btc > 0:
                valore_attuale = tot_btc * ultimo_prezzo
                profitto_temp = valore_attuale - sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"])
                segno = "+" if profitto_temp >= 0 else ""
                stato = (
                    f"📈 **Posizione attiva ({len(dati['Lotti'])} lotti accumulati)**\n"
                    f"• Prezzo medio carico: ${prezzo_medio:,.2f}\n"
                    f"• Performance live: {segno}${profitto_temp:,.2f} ({segno}{profitto_perc:.2f}%)\n"
                    f"• RSI attuale: {rsi_attuale:.1f}"
                )
            else:
                stato = f"⏳ **In attesa di ipervenduto** (RSI attuale: {rsi_attuale:.1f} | Nessun lotto attivo)"

            messaggio = (
                f"🛡️ **REPORT DI CONTROLLO DINAMICO** 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Prezzo BTC:** ${ultimo_prezzo:,.2f}\n"
                f"• **RSI (1m):** {rsi_attuale:.1f}\n\n"
                f"📌 **Analisi di mercato:**\n{stato}"
            )

        with open(file_path, 'w') as f:
            json.dump(dati, f)
            
        if messaggio:
            manda_messaggio_telegram(messaggio)
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot: {e}")

if __name__ == "__main__":
    run_bot()
