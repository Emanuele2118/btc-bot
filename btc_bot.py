import os
import json
import requests
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')

FEE_RATE = 0.005  # 0.5% di commissione per transazione

def genera_grafico_chart(df, rsi_attuale, prezzo_attuale, stato_testo):
    """Genera un grafico avanzato a due pannelli con prezzo, medie mobili e pannello dati descrittivo."""
    try:
        fig = plt.figure(figsize=(10, 7.5), facecolor='#1e1e1e')
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1.3])
        
        # --- PANNELLO 1: GRAFICO PREZZO & MEDIE MOBILI ---
        ax1 = fig.add_subplot(gs[0])
        ax1.set_facecolor('#1e1e1e')
        
        dati_plot = df.tail(100).copy()
        x = range(len(dati_plot))
        
        ax1.plot(x, dati_plot['Close'], label='Prezzo BTC', color='#00ffcc', linewidth=1.8)
        ax1.plot(x, dati_plot['ema_veloce'], label='EMA 9 (Veloce)', color='#ff00ff', linewidth=1.2, linestyle='--')
        ax1.plot(x, dati_plot['ema_lenta'], label='EMA 50 (Lenta)', color='#ffcc00', linewidth=1.2, linestyle='--')
        
        ultimo_idx = len(x) - 1
        ax1.scatter([ultimo_idx], [prezzo_attuale], color='#00ffcc', s=45, zorder=5)
        ax1.annotate(f"${prezzo_attuale:,.2f}", 
                     xy=(ultimo_idx, prezzo_attuale), 
                     xytext=(-65, 12), textcoords='offset points',
                     color='#00ffcc', fontsize=9, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.25', fc='#111111', ec='#00ffcc', alpha=0.85))

        ax1.set_title('BTC-USD | Profit Lockdown & Risk-Managed Bot', color='white', fontsize=13, fontweight='bold', pad=12)
        ax1.tick_params(colors='white', labelsize=9)
        ax1.grid(True, color='#333333', linestyle=':', alpha=0.7)
        
        for spine in ax1.spines.values():
            spine.set_color('#444444')
            
        ax1.legend(loc='upper left', facecolor='#2e2e2e', edgecolor='none', labelcolor='white', fontsize=9)

        # --- PANNELLO 2: DASHBOARD DATI UTILI IN BASSO ---
        ax2 = fig.add_subplot(gs[1])
        ax2.set_facecolor('#161616')
        ax2.axis('off')
        
        info_testo = (
            f" 📊  PANNELLO DI CONTROLLO PROFIT LOCKDOWN & ATR\n"
            f" • Prezzo Corrente: ${prezzo_attuale:,.2f}    |    • RSI: {rsi_attuale:.1f}\n"
            f" • Stato Operativo: {stato_testo}"
        )
        
        ax2.text(0.02, 0.5, info_testo, color='white', fontsize=10, family='monospace',
                 verticalalignment='center', bbox=dict(boxstyle='square,pad=0.8', fc='#222222', ec='#555555'))

        plt.tight_layout()
        chart_path = 'temp_chart.png'
        plt.savefig(chart_path, dpi=150, facecolor='#1e1e1e', edgecolor='none')
        plt.close()
        return chart_path
    except Exception as e:
        print(f"Errore nella generazione del grafico avanzato: {e}")
        return None

def manda_messaggio_telegram(testo, chart_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Credenziali Telegram non configurate.")
        return
    
    if chart_path and os.path.exists(chart_path):
        url_telegram = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        try:
            with open(chart_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": testo,
                    "parse_mode": "Markdown"
                }
                response = requests.post(url_telegram, data=data, files=files, timeout=40)
                if response.status_code == 200:
                    return
        except Exception as e:
            print(f"Errore invio foto Telegram: {e}")
            
    url_fallback = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload_fallback = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": testo,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url_fallback, json=payload_fallback, timeout=20)
    except Exception as e:
        print(f"Errore invio messaggio di testo Telegram: {e}")

def registra_su_google_sheets(data_ora, tipo, prezzo, quantita, commissione, profitto_usd, motivo):
    if not GOOGLE_SHEET_URL:
        return
    payload = {
        "Data_Ora": data_ora,
        "Tipo": tipo,
        "Prezzo": f"{prezzo:.2f}",
        "Quantita_BTC": f"{quantita:.5f}",
        "Commissione_USD": f"{commissione:.2f}",
        "Profitto_Netto_USD": f"{profitto_usd:.2f}",
        "Motivo": motivo
    }
    try:
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio a Google Sheets: {e}")

def run_bot():
    print("--- Inizio esecuzione Bot con Profit Lockdown & Risk Management ---")
    
    file_path = 'portfolio.json'
    file_backup = 'portfolio_backup.json'
    
    dati = {
        "usd": 10000.0, 
        "btc": 0.0, 
        "Lotti": [],
        "ultima_operazione": None,
        "prezzo_max_raggiunto": 0.0,
        "ultimo_invio_timestamp": 0,
        "ultima_transazione_timestamp": 0
    }
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                caricati = json.load(f)
                dati.update(caricati)
            except:
                pass

    timestamp_attuale = int(datetime.now(timezone.utc).timestamp())
    
    # Antispam report (almeno 50 secondi tra i messaggi di monitoraggio)
    if timestamp_attuale - dati.get("ultimo_invio_timestamp", 0) < 50:
        print("Esecuzione bloccata: è passato troppo poco tempo dall'ultimo messaggio.")
        return

    try:
        url_coinbase = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url_coinbase, headers=headers, timeout=10)
        
        if response.status_code == 200:
            raw_data = response.json()
            raw_data.reverse()
            df = pd.DataFrame(raw_data, columns=['Time', 'Low', 'High', 'Open', 'Close', 'Volume'])
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
        else:
            print(f"Errore Coinbase: {response.status_code}")
            return

        ultimo_prezzo = float(df['Close'].iloc[-1])
        stringa_data = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        # Indicatori Tecnici
        df['ema_veloce'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['ema_lenta'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['ema_macro'] = df['Close'].ewm(span=200, adjust=False).mean() if len(df) >= 200 else df['ema_lenta']
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df['atr'] = ranges.max(axis=1).rolling(14).mean()
        
        ema_v = float(df['ema_veloce'].iloc[-1])
        ema_l = float(df['ema_lenta'].iloc[-1])
        ema_m = float(df['ema_macro'].iloc[-1])
        rsi_attuale = float(df['rsi'].iloc[-1])
        atr_attuale = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else (ultimo_prezzo * 0.005)
        
        messaggio = None
        tot_btc = sum(lotto["quantita"] for lotto in dati["Lotti"])
        prezzo_medio = 0.0
        if tot_btc > 0:
            costo_totale = sum(lotto["quantita"] * lotto["prezzo"] for lotto in dati["Lotti"])
            prezzo_medio = costo_totale / tot_btc
            
        profitto_perc = 0.0
        if tot_btc > 0 and prezzo_medio > 0:
            profitto_perc = ((ultimo_prezzo - prezzo_medio) / prezzo_medio) * 100

        # Condizioni di mercato adattive e gestione rischio basata su ATR
        trend_favorevole = (ema_v >= (ema_l * 0.998)) and (ultimo_prezzo >= ema_m * 0.99)
        cooldown_superato = (timestamp_attuale - dati.get("ultima_transazione_timestamp", 0)) >= 180

        # Volatilità normalizzata per dimensionare il rischio
        volatilita_pct = (atr_attuale / ultimo_prezzo) * 100

        # Trailing Take Profit Dinamico
        target_iniziale_raggiunto = profitto_perc >= 0.7
        if tot_btc > 0 and target_iniziale_raggiunto:
            if ultimo_prezzo > dati["prezzo_max_raggiunto"]:
                dati["prezzo_max_raggiunto"] = ultimo_prezzo
        else:
            dati["prezzo_max_raggiunto"] = 0.0
            
        soglia_ritracciamento_perc = max(0.25, min(0.6, volatilita_pct * 1.2))
        
        trailing_scattato = False
        if tot_btc > 0 and dati["prezzo_max_raggiunto"] > 0:
            ritracciamento = ((dati["prezzo_max_raggiunto"] - ultimo_prezzo) / dati["prezzo_max_raggiunto"]) * 100
            if profitto_perc >= 0.7 and ritracciamento >= soglia_ritracciamento_perc:
                trailing_scattato = True

        minimo_recente = float(df['Low'].tail(10).min())
        stop_loss_strutturale_perc = min(-2.0, ((minimo_recente - prezzo_medio) / prezzo_medio) * 100) if prezzo_medio > 0 else -2.0

        # PROFIT LOCKDOWN DINAMICO
        stop_loss_effettivo_perc = stop_loss_strutturale_perc
        motivo_stop_loss = "Supporti strutturali"
        
        if profitto_perc >= 3.0:
            stop_loss_effettivo_perc = 1.0  # Blinda almeno +1.0% di guadagno netto garantito
            motivo_stop_loss = "Profit Lockdown livello 2 (Garantito +1%)"
        elif profitto_perc >= 1.5:
            stop_loss_effettivo_perc = 0.0  # Breakeven (zero rischi di perdita)
            motivo_stop_loss = "Profit Lockdown livello 1 (Pareggio / Breakeven)"

        # Retrospettiva
        nota_retrospettiva = ""
        if dati.get("ultima_operazione") is not None:
            op = dati["ultima_operazione"]
            tempo_minuti = (timestamp_attuale - op["timestamp"]) / 60
            if tempo_minuti >= 5:
                prezzo_op = op["prezzo"]
                diff_p = ultimo_prezzo - prezzo_op
                perc_diff = (diff_p / prezzo_op) * 100
                if op["tipo"] == "VENDITA":
                    if diff_p < 0:
                        nota_retrospettiva = f"\n🧠 *Analisi a posteriori:* Ottimo timing! Venduto a ${prezzo_op:,.2f} e il mercato è sceso del {abs(perc_diff):.2f}%."
                    else:
                        nota_retrospettiva = f"\n🧠 *Analisi a posteriori:* Il mercato ha continuato a salire (+{perc_diff:.2f}%) dopo la vendita."
                elif op["tipo"] == "ACQUISTO":
                    if diff_p > 0:
                        nota_retrospettiva = f"\n🧠 *Analisi a posteriori:* Ottima intuizione! Comprato a ${prezzo_op:,.2f} e il mercato è salito del +{perc_diff:.2f}%."
                    else:
                        nota_retrospettiva = f"\n🧠 *Analisi a posteriori:* Dopo l'acquisto il mercato è sceso temporaneamente del {perc_diff:.2f}%."
                dati["ultima_operazione"] = None

        # 1. ACQUISTO CON POSITION SIZING DINAMICO
        capitale_totale = dati["usd"] + (tot_btc * ultimo_prezzo)
        if rsi_attuale < 38 and dati["usd"] > 100 and trend_favorevole and cooldown_superato:
            if volatilita_pct > 0.4:
                peso_base = 0.20
                motivo_vol = f"Volatilità elevata (ATR {volatilita_pct:.2f}%), esposizione prudenziale"
            else:
                peso_base = 0.35
                motivo_vol = f"Volatilità contenuta (ATR {volatilita_pct:.2f}%), esposizione ottimizzata"

            if rsi_attuale < 26:
                peso_investimento = peso_base * 1.35
                motivo_rsi = f"Ipervenduto profondo ({rsi_attuale:.1f} < 26)"
            else:
                peso_investimento = peso_base
                motivo_rsi = f"Ipervenduto standard ({rsi_attuale:.1f} < 38)"

            spesa_lorda = capitale_totale * min(peso_investimento, 0.455)
            if spesa_lorda > dati["usd"]:
                spesa_lorda = dati["usd"]
                
            comm_acq = spesa_lorda * FEE_RATE
            qta = (spesa_lorda - comm_acq) / ultimo_prezzo
            
            dati["usd"] -= spesa_lorda
            dati["Lotti"].append({"quantita": qta, "prezzo": ultimo_prezzo})
            dati["ultima_operazione"] = {"tipo": "ACQUISTO", "prezzo": ultimo_prezzo, "timestamp": timestamp_attuale}
            dati["ultima_transazione_timestamp"] = timestamp_attuale
            
            numero_lotto_attuale = len(dati["Lotti"])
            motivo_acquisto = f"{motivo_rsi} | {motivo_vol}. Aggiunto lotto #{numero_lotto_attuale} bilanciando il rischio di portafoglio."
            registra_su_google_sheets(stringa_data, "ACQUISTO", ultimo_prezzo, qta, comm_acq, 0.0, f"Lotto #{numero_lotto_attuale}")
            
            messaggio = (
                f"🟢 *ACQUISTO LOTTO (#{numero_lotto_attuale}) CON PROFIT LOCKDOWN* 🟢\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• *Prezzo entrata:* ${ultimo_prezzo:,.2f}\n"
                f"• *Quantità acquistata:* {qta:.5f} BTC\n"
                f"• *Perché questa scelta:* {motivo_acquisto}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Lotti attivi totali:* {numero_lotto_attuale}\n"
                f"💰 *Saldo USD residuo:* ${dati['usd']:,.2f}"
            )

        # 2. VENDITA PARZIALE INTELLIGENTE
        elif tot_btc > 0 and (trailing_scattato or rsi_attuale > 68) and cooldown_superato:
            lotto = dati["Lotti"].pop(0)
            qta_v = lotto["quantita"]
            ricavo_lordo = qta_v * ultimo_prezzo
            comm_vend = ricavo_lordo * FEE_RATE
            ricavo_netto = ricavo_lordo - comm_vend
            profitto_usd = ricavo_netto - (qta_v * lotto["prezzo"])
            segno_p = "+" if profitto_usd >= 0 else ""
            
            dati["usd"] += ricavo_netto
            dati["prezzo_max_raggiunto"] = 0.0
            dati["ultima_operazione"] = {"tipo": "VENDITA", "prezzo": ultimo_prezzo, "timestamp": timestamp_attuale}
            dati["ultima_transazione_timestamp"] = timestamp_attuale
            
            motivo = f"Trailing Take Profit ATR (ritracciamento del {soglia_ritracciamento_perc:.2f}%)" if trailing_scattato else f"RSI ipercomprato ({rsi_attuale:.1f} > 68)"
            motivo_vendita = f"{motivo}. Blocco parziale dei profitti sul lotto più vecchio per mitigare il rischio di inversione lasciando correre le posizioni più recenti."
            
            registra_su_google_sheets(stringa_data, "VENDITA", ultimo_prezzo, qta_v, comm_vend, profitto_usd, motivo)
            rimanenti_btc = sum(l["quantita"] for l in dati["Lotti"])
            
            messaggio = (
                f"🔵 *VENDITA PARZIALE INTELLIGENTE* 🔵\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• *Prezzo uscita:* ${ultimo_prezzo:,.2f}\n"
                f"• *Quantità venduta:* {qta_v:.5f} BTC\n"
                f"• *Profitto netto:* {segno_p}${profitto_usd:,.2f}\n"
                f"• *Perché questa scelta:* {motivo_vendita}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Rimasti sul conto:* {rimanenti_btc:.5f} BTC ({len(dati['Lotti'])} lotti attivi)\n"
                f"💰 *Saldo USD:* ${dati['usd']:,.2f}"
            )

        # 3. STOP LOSS / PROFIT LOCKDOWN TRIGGER
        elif tot_btc > 0 and profitto_perc <= stop_loss_effettivo_perc:
            ricavo_tot = sum(l["quantita"] * ultimo_prezzo for l in dati["Lotti"])
            comm_tot = ricavo_tot * FEE_RATE
            risultato_usd = (ricavo_tot - comm_tot) - sum(l["quantita"] * l["prezzo"] for l in dati["Lotti"])
            
            qta_tot = tot_btc
            dati["usd"] += (ricavo_tot - comm_tot)
            dati["Lotti"] = []
            dati["prezzo_max_raggiunto"] = 0.0
            dati["ultima_operazione"] = {"tipo": "VENDITA", "prezzo": ultimo_prezzo, "timestamp": timestamp_attuale}
            dati["ultima_transazione_timestamp"] = timestamp_attuale
            
            tipo_uscita_txt = "STOP LOSS DI PROTEZIONE" if risultato_usd < 0 else "PROFIT LOCKDOWN (Chiusura in guadagno protetto)"
            icona_uscita = "🔴" if risultato_usd < 0 else "🟢"
            segno_res = "+" if risultato_usd >= 0 else ""
            
            registra_su_google_sheets(stringa_data, "STOP_LOSS_LOCKDOWN", ultimo_prezzo, qta_tot, comm_tot, risultato_usd, motivo_stop_loss)
            messaggio = (
                f"{icona_uscita} *{tipo_uscita_txt}* {icona_uscita}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"• *Criterio attivato:* {motivo_stop_loss} (Performance attuale: {profitto_perc:.2f}% vs soglia limite {stop_loss_effettivo_perc:.2f}%).\n"
                f"• *Risultato netto:* {segno_res}${risultato_usd:,.2f}\n"
                f"• *Saldo USD:* ${dati['usd']:,.2f}"
            )

        # Report Standard
        if not messaggio:
            tot_btc_agg = sum(l["quantita"] for l in dati["Lotti"])
            if tot_btc_agg > 0:
                stato = (
                    f"📈 *Posizioni attive ({len(dati['Lotti'])} lotti in corso)*\n"
                    f"• Quantità totale BTC: {tot_btc_agg:.5f}\n"
                    f"• Prezzo medio di carico: ${prezzo_medio:,.2f}\n"
                    f"• Performance netta: {profitto_perc:+.2f}%\n"
                    f"• *Protezione attiva:* Stop Loss dinamico a {stop_loss_effettivo_perc:+.2f}% ({motivo_stop_loss})."
                )
            else:
                if trend_favorevole:
                    stato = (
                        f"🟢 *In attesa attiva (Trend FAVOREVOLE)*\n"
                        f"• RSI attuale: {rsi_attuale:.1f} (soglia d'ingresso < 38)\n"
                        f"• *Perché stiamo attendendo:* La struttura macro è rialzista, ma attendiamo uno scarico più deciso dell'indicatore RSI o lo scadere del cooldown per calibrare un nuovo lotto a basso rischio."
                    )
                else:
                    stato = (
                        f"🔴 *In attesa protetta (Trend RIBASSISTA)*\n"
                        f"• RSI attuale: {rsi_attuale:.1f}\n"
                        f"• *Perché stiamo attendendo:* Il mercato mostra debolezza sotto la media mobile principale. Il bot sceglie di rimanere in USD per azzerare l'esposizione al rischio ribassista."
                    )

            messaggio = f"🛡️ *REPORT DI MERCATO & PROFIT LOCKDOWN* 🛡️\n━━━━━━━━━━━━━━━━━━━\n• *Prezzo BTC:* ${ultimo_prezzo:,.2f}\n{nota_retrospettiva}\n\n📌 *Analisi e Decisione del Bot:*\n{stato}"

        dati["ultimo_invio_timestamp"] = timestamp_attuale

        # Salvataggio con Backup di sicurezza
        with open(file_path, 'w') as f:
            json.dump(dati, f)
        with open(file_backup, 'w') as f:
            json.dump(dati, f)
            
        if tot_btc > 0:
            stato_dashboard = f"Posizioni attive (P&L: {profitto_perc:+.2f}% | SL: {stop_loss_effettivo_perc:+.2f}%)"
        else:
            stato_dashboard = "In attesa di acquisto" if trend_favorevole else "In attesa protetta"

        chart_file = genera_grafico_chart(df, rsi_attuale, ultimo_prezzo, stato_dashboard)
            
        if messaggio:
            manda_messaggio_telegram(messaggio, chart_file)
            
        if chart_file and os.path.exists(chart_file):
            try:
                os.remove(chart_file)
            except:
                pass
            
    except Exception as e:
        print(f"Errore esecuzione bot: {e}")

if __name__ == "__main__":
    run_bot()
