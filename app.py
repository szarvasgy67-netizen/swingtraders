import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import config
from modules import guards


st.set_page_config(page_title="Swingtrader Co-Pilot", page_icon="📈", layout="wide")

# --- SEGÉDFÜGGVÉNYEK ---
@st.cache_data(ttl=3600)
def get_usdhuf():
    try:
        df = yf.download("HUF=X", period="5d", progress=False)
        return float(df["Close"].iloc[-1])
    except Exception:
        return 385.0  # Tartalék árfolyam

@st.cache_data(ttl=1800)
def analyze_market_regime():
    results = {}
    for ticker in config.BENCHMARK_TICKERS:
        df = yf.download(ticker, period="6mo", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df["SMA20"] = df["Close"].rolling(20).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        
        last_close = float(df["Close"].iloc[-1])
        sma20 = float(df["SMA20"].iloc[-1])
        sma50 = float(df["SMA50"].iloc[-1])
        sma20_slope = (sma20 - float(df["SMA20"].iloc[-5])) / float(df["SMA20"].iloc[-5]) * 100
        
        if last_close > sma20 > sma50 and sma20_slope > 0.2:
            regime = "🟢 TRENDELŐ (Zöld lámpa - 100% tőke)"
        elif last_close > sma50:
            regime = "🟡 ÓVATOS / VEGYES (Sárga - 50% tőke)"
        else:
            regime = "🔴 OLDALAZÓ / ESŐ (Piros - Ne erőltesd!)"
            
        results[ticker] = {
            "price": last_close,
            "sma20": sma20,
            "sma50": sma50,
            "slope": sma20_slope,
            "regime": regime
        }
    return results

@st.cache_data(ttl=1800)
def scan_watchlist(tickers):
    candidates = []
    for t in tickers:
        try:
            df = yf.download(t, period="6mo", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) < 60:
                continue
                
            df["SMA20"] = df["Close"].rolling(20).mean()
            df["SMA50"] = df["Close"].rolling(50).mean()
            
            # RSI számítás
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            # ATR (14 napos átlagos napi mozgástér)
            high_low = df["High"] - df["Low"]
            high_close = np.abs(df["High"] - df["Close"].shift())
            low_close = np.abs(df["Low"] - df["Close"].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df["ATR"] = tr.rolling(14).mean()
            
            close = float(df["Close"].iloc[-1])
            sma20 = float(df["SMA20"].iloc[-1])
            sma50 = float(df["SMA50"].iloc[-1])
            rsi = float(df["RSI"].iloc[-1])
            atr_pct = (float(df["ATR"].iloc[-1]) / close) * 100
            
            # Swing setup: Fő trend felfelé (Close > SMA50), visszahúzás (RSI < 55 vagy közel az SMA20-hoz)
            dist_sma20 = ((close - sma20) / sma20) * 100
            
            if close > sma50 and abs(dist_sma20) <= 3.5 and atr_pct >= 1.8:
                setup = "🎯 Visszahúzás SMA20-hoz"
            elif close > sma20 > sma50 and 50 <= rsi <= 68:
                setup = "🚀 Lendület (Momentum)"
            else:
                setup = "⚪ Várakozás"
                
            candidates.append({
                "Ticker": t,
                "Ár ($)": round(close, 2),
                "Setup": setup,
                "RSI (14)": round(rsi, 1),
                "SMA20 táv (%)": round(dist_sma20, 2),
                "Napi mozgás ATR (%)": round(atr_pct, 2)
            })
        except Exception:
            continue
    return pd.DataFrame(candidates)

# --- OLDALSÁV (TŐKE & KOCKÁZAT BEÁLLÍTÁSOK) ---
st.sidebar.title("⚙️ Swingtrader Beállítások")
usdhuf = get_usdhuf()
st.sidebar.metric("Élő USD/HUF", f"{usdhuf:.2f} Ft")

capital_huf = st.sidebar.number_input(
    "Aktív tőke (HUF)", 
    min_value=500_000, 
    max_value=20_000_000, 
    value=config.CURRENT_CAPITAL_HUF, 
    step=150_000
)
capital_usd = capital_huf / usdhuf
risk_pct = st.sidebar.slider("Max. kockázat / trade (%)", 0.5, 2.5, config.RISK_PER_TRADE_PCT * 100, 0.25) / 100
max_risk_huf = capital_huf * risk_pct
max_risk_usd = capital_usd * risk_pct

st.sidebar.divider()
st.sidebar.write(f"**Tőke USD-ben:** `${capital_usd:,.0f}`")
st.sidebar.write(f"**Max. bukó / kötés:** `{max_risk_huf:,.0f} Ft` (`${max_risk_usd:.0f}`)")
st.sidebar.write(f"**Time-Stop szabály:** `{config.TIME_STOP_DAYS} nap` (min. `+{config.TIME_STOP_MIN_PROFIT*100:.0f}%`)")

# --- FŐ FELÜLET ---
st.title("📈 Swingtrader Co-Pilot")

# 1. PIACI IDŐJÁRÁS-JELENTÉS
st.subheader("1. Piaci Rezsim (Érdemes most kereskedni?)")
regime_data = analyze_market_regime()
cols = st.columns(len(regime_data))
for idx, (ticker, data) in enumerate(regime_data.items()):
    with cols[idx]:
        st.info(f"**{ticker}** (${data['price']:.2f})\n\n{data['regime']}\n\nSMA20 meredekség: `{data['slope']:.2f}%`")

st.divider()

# 2. SWING SZKENNER & POZÍCIÓMÉRETEZŐ
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("2. Napi Swing Jelöltek")
    custom_tickers = st.text_input("Figyelt részvények (vesszővel elválasztva)", ", ".join(config.DEFAULT_WATCHLIST))
    ticker_list = [x.strip().upper() for x in custom_tickers.split(",") if x.strip()]
    
    if st.button("🔍 Szkennelés futtatása", type="primary"):
        st.cache_data.clear()
        
    df_scan = scan_watchlist(ticker_list)
    if not df_scan.empty:
        # Kiemeljük az aktív setupokat előre
        df_scan = df_scan.sort_values(by="Setup")
        st.dataframe(df_scan, use_container_width=True, hide_index=True)

with col_right:
    st.subheader("3. Pozícióméretező")
    sel_ticker = st.text_input("Kiválasztott Ticker", "NVDA").upper()
    entry_price = st.number_input("Tervezett belépő ($)", min_value=1.0, value=140.0, step=0.5)
    stop_price = st.number_input("Stop-Loss szint ($)", min_value=0.5, value=133.0, step=0.5)
    
    if entry_price > stop_price:
        risk_per_share = entry_price - stop_price
        shares = int(max_risk_usd // risk_per_share)
        pos_value_usd = shares * entry_price
        pos_value_huf = pos_value_usd * usdhuf
        
        st.success(f"**Vásárolható mennyiség: {shares} db**")
        st.write(f"• Pozíció értéke: **{pos_value_huf:,.0f} Ft** (`${pos_value_usd:,.0f}`)")
        st.write(f"• Tőke arányában: **{(pos_value_huf / capital_huf)*100:.1f}%**")
        st.write(f"• Kockáztatott összeg: **{shares * risk_per_share * usdhuf:,.0f} Ft**")
        
        if pos_value_huf > capital_huf * 0.45:
            st.warning("⚠️ Egy pozícióba a tőkéd több mint 45%-át tennéd! Húzd kijjebb a stopot vagy csökkentsd a darabszámot.")
    else:
        st.error("A belépő árnak nagyobbnak kell lennie a Stop-Loss árnál!")
st.divider()

# 4. AKTÍV POZÍCIÓK FIGYELŐJE (TIME-STOP & EARNINGS PAJZS)
st.subheader("4. Aktív Pozíciók & Pajzs (Time-Stop + Hírradar)")
st.caption("Írd be a jelenleg nyitott pozícióidat (vagy tesztelj egyet), és az app figyeli a 10 napos időkorlátot és a veszélyes híreket.")

# Egyszerű szerkeszthető táblázat a nyitott kötéseidhez
default_positions = pd.DataFrame([
    {"Ticker": "ADBE", "Belépő ($)": 480.0, "Belépés dátuma": "2026-11-10"},
    {"Ticker": "NVDA", "Belépő ($)": 142.0, "Belépés dátuma": "2026-11-20"},
])

edited_df = st.data_editor(default_positions, num_rows="dynamic", use_container_width=True)

if st.button("🛡️ Pozíciók és Hírek ellenőrzése"):
    status_rows = []
    for _, row in edited_df.iterrows():
        t = str(row["Ticker"]).strip().upper()
        if t and pd.notna(row["Belépő ($)"]) and pd.notna(row["Belépés dátuma"]):
            res = guards.check_position_status(t, float(row["Belépő ($)"]), str(row["Belépés dátuma"]))
            if res:
                status_rows.append(res)
                
    if status_rows:
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)
        
        # Hírfigyelő az aktív részvényekhez
        st.markdown("#### 📡 Friss Hírradar a tartott részvényekhez")
        for r in status_rows:
            with st.expander(f"{r['Ticker']} – Legfrissebb hírek"):
                news = guards.scan_breaking_news(r["Ticker"])
                if news:
                    for n in news:
                        if "PIROS ZÁSZLÓ" in n:
                            st.error(n)
                        else:
                            st.write(n)
                else:
                    st.write("Nincs friss hír.")
