import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

FEE_RATE = 0.005  # 0.5% di commissione

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
    print("--- Inizio esecuzione Bot (Report Dettagliato in Attesa) ---")
    
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
        timestamp_attuale = int(datetime.now(timezone.utc).timestamp())
        
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
        dati = {
            "usd": 10000.0, 
            "btc": 0.0, 
            "prezzo_acquisto": 0.0,
            "Lotti": [],
            "ultima_operazione": None
        }
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    dati = json.load(f)
                    if "Lotti" not in dati:
                        dati["Lotti"] = []
                    if "ultima_operazione" not in dati:
                        dati["ultima_operazione"] = None
                except:
                    pass
                    
        messaggio = None
        
        tot_btc = sum(lotto["quantita"] for lotto in dati["Lotti"])
        prezzo_medio = 0.0
        if tot_btc > 0:
            costo_totale = sum(lotto["quantita"] * lotto["prezzo"] for lotto in dati["Lotti"])
            prezzo_medio = costo_totale / tot_btc
            
        profitto_perc = 0.0
        if tot_btc > 0 and prezzo_medio > 0:
            profitto_perc = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100

        trend_favorevole = ema_v >= (ema_l * 0.998)
        
        nota_retrospettiva = ""
        if dati["ultima_operazione"] is not None:
            op = dati["ultima_operazione"]
            tempo_trascorso_minuti = (timestamp_attuale - op["timestamp"]) / 60
            
            if tempo_trascorso_minuti >= 5:
                prezzo_operazione = op["prezzo"]
                differenza_prezzo = ultimo_prezzo - prezzo_operazione
                perc_diff = (differenza_prezzo / prezzo_operazione) * 100
                
                if op["tipo"] == "VENDITA":
                    if differenza_prezzo < 0:
                        nota_retrospettiva = f"\n🧠 **Analisi a posteriori:** Ottimo timing! Ho venduto a ${prezzo_operazione:,.2f} e nei minuti successivi il grafico è sceso del {abs(perc_diff):.2f}%."
                    else:
                        nota_retrospettiva = f"\n🧠 **Analisi a posteriori:** Il grafico ha continuato a salire (+{perc_diff:.2f}%) dopo la vendita."
                elif op["tipo"] == "ACQUISTO":
                    if differenza_prezzo > 0:
                        nota_retrospettiva = f"\n🧠 **Analisi a posteriori:** Ottima intuizione! Ho comprato a ${prezzo_operazione:,.2f} e il grafico è salito del +{perc_diff:.2f}%."
                    else:
                        nota_retrospettiva = f"\n🧠 **Analisi a posteriori:** Dopo l'acquisto il grafico è sceso temporaneamente del {perc_diff:.2f}%."
                
                dati["ultima_operazione"] = None

        # 1. ACQUISTO FRAZIONATO
        if rsi_attuale < 35 and dati["usd"] > 100 and len(dati["Lotti"]) < 3 and trend_favorevole:
            spesa_lorda = dati["usd"] * 0.30
            commissione_acquisto = spesa_lorda * FEE_RATE
            spesa_netta = spesa_lorda - commissione_acquisto
            quantita = spesa_netta / ultimo_prezzo
            
            dati["usd"] -= spesa_lorda
            dati["Lotti"].append({"quantita": quantita, "prezzo": ultimo_prezzo})
            dati["btc"] = sum(l.get("quantita", 0) for l in dati["Lotti"])
            
            dati["ultima_operazione"] = {
                "tipo": "ACQUISTO",
                "prezzo": ultimo_prezzo,
                "timestamp": timestamp_attuale
            }
            
            num_lotto = len(dati["Lotti"])
            messaggio = (
                f"🟢 **ACQUISTO LOTTO #{num_lotto} ESEGUITO** 🟢\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Prezzo:** ${ultimo_prezzo:,.2f}\n"
                f"• **Quantità netta:** {quantita:.5f} BTC\n"
                f"• **Spesa lorda:** ${spesa_lorda:,.2f}\n"
                f"• **Fee (0.5%):** -${commissione_acquisto:,.2f}\n"
                f"• **RSI:** {rsi_attuale:.1f}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **Saldo USD residuo:** ${dati['usd']:,.2f}"
            )

        # 2. VENDITA PARZIALE
        elif tot_btc > 0 and (profitto_perc >= 0.8 or rsi_attuale > 65):
            lotto_da_vendere = dati["Lotti"].pop(0)
            quantita_venduta = lotto_da_vendere["quantita"]
            prezzo_carico_lotto = lotto_da_vendere["prezzo"]
            
            ricavo_lordo = quantita_venduta * ultimo_prezzo
            commissione_vendita = ricavo_lordo * FEE_RATE
            ricavo_netto = ricavo_lordo - commissione_vendita
            
            costo_iniziale_lotto = quantita_venduta * prezzo_carico_lotto
            profitto_usd = ricavo_netto - costo_iniziale_lotto
            perc_lotto_netta = (profitto_usd / costo_iniziale_lotto) * 100
            segno = "+" if profitto_usd >= 0 else ""
            
            dati["usd"] += ricavo_netto
            dati["btc"] = sum(l.get("quantita", 0) for l in dati["Lotti"])
            
            dati["ultima_operazione"] = {
                "tipo": "VENDITA",
                "prezzo": ultimo_prezzo,
                "timestamp": timestamp_attuale
            }
            
            motivo = f"Target profitto raggiunto (+{perc_lotto_netta:.2f}% netto)" if profitto_perc >= 0.8 else f"RSI ipercomprato ({rsi_attuale:.1f})"
            
            messaggio = (
                f"🔵 **VENDITA PARZIALE ESEGUITA** 🔵\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Prezzo uscita:** ${ultimo_prezzo:,.2f}\n"
                f"• **Profitto netto:** {segno}${profitto_usd:,.2f} ({segno}{perc_lotto_netta:.2f}%)\n"
                f"• **Motivo:** {motivo}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **Saldo USD:** ${dati['usd']:,.2f}"
            )

        # 3. STOP LOSS RIGIDO
        elif tot_btc > 0 and profitto_perc <= -1.8:
            ricavo_lordo_totale = sum(l["quantita"] * ultimo_prezzo for l in dati["Lotti"])
            fee_totali = ricavo_lordo_totale * FEE_RATE
            ricavo_netto_totale = ricavo_lordo_totale - fee_totali
            costo_totale_iniziale = sum(l["quantita"] * l["perzzo"] for l in dati["Lotti"]) if "perzzo" in locals() else sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"])
            perdita_usd = ricavo_netto_totale - costo_totale_iniziale
            
            dati["usd"] += ricavo_netto_totale
            dati["Lotti"] = []
            dati["btc"] = 0.0
            
            dati["ultima_operazione"] = {
                "tipo": "VENDITA",
                "prezzo": ultimo_prezzo,
                "timestamp": timestamp_attuale
            }
            
            messaggio = (
                f"🔴 **STOP LOSS DI PROTEZIONE** 🔴\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Perdita netta:** -${abs(perdita_usd):,.2f} ({profitto_perc:.2f}%)\n"
                f"• **Motivo:** Chiusura di salvaguardia.\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **Saldo USD:** ${dati['usd']:,.2f}"
            )

        # Report di controllo avanzato con spiegazione dettagliata dell'attesa
        if not messaggio:
            if tot_btc > 0:
                valore_attuale = tot_btc * ultimo_prezzo
                profitto_temp = valore_attuale - sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"])
                segno = "+" if profitto_temp >= 0 else ""
                stato = (
                    f"📈 **Posizione attiva ({len(dati['Lotti'])} lotti)**\n"
                    f"• Prezzo medio: ${prezzo_medio:,.2f}\n"
                    f"• Performance netta: {segno}${profitto_temp:,.2f} ({segno}{profitto_perc:.2f}%)"
                )
            else:
                # Spiegazione dettagliata di cosa sta aspettando il bot
                if trend_favorevole:
                    spiegazione_attesa = (
                        f"🟢 **In attesa di acquisto (Trend FAVOREVOLE)**\n"
                        f"• Il mercato sta salendo bene, quindi il semaforo è VERDE per comprare.\n"
                        f"• **Cosa aspetto?** L'RSI è a {rsi_attuale:.1f} (obiettivo < 35). "
                        f"Sto aspettando un calo temporaneo del prezzo per non comprare sui massimi."
                    )
                else:
                    spiegazione_attesa = (
                        f"🔴 **In attesa protetta (Trend RIBASSISTA)**\n"
                        f"• Il mercato sta scendendo o è debole, il filtro anti-crollo ha bloccato gli acquisti.\n"
                        f"• **Cosa aspetto?** Che le medie mobili tornino a incrociarsi al rialzo per sbloccare le operazioni in sicurezza."
                    )
                stato = spiegazione_attesa

            messaggio = (
                f"🛡️ **REPORT DI MERCATO** 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• **Prezzo BTC:** ${ultimo_prezzo:,.2f}\n"
                f"{nota_retrospettiva}\n\n"
                f"📌 **Analisi:**\n{stato}"
            )

        with open(file_path, 'w') as f:
            json.dump(dati, f)
            
        if messaggio:
            manda_messaggio_telegram(messaggio)
            
    except Exception as e:
        print(f"Errore durante l'esecuzione del bot: {e}")

if __name__ == "__main__":
    run_bot()
