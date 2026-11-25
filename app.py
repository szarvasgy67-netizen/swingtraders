def check_position_status(ticker, entry_price, entry_date_str):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        current_price = float(hist["Close"].iloc[-1])
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        entry_dt = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
        trading_days = len(pd.bdate_range(start=entry_dt, end=date.today())) - 1
        trading_days = max(0, trading_days)
        
        if trading_days >= config.TIME_STOP_DAYS and pnl_pct < (config.TIME_STOP_MIN_PROFIT * 100):
            status = f"🚨 TIME-STOP! ({trading_days} napja áll, zárás javasolt)"
        elif pnl_pct >= (config.TIME_STOP_MIN_PROFIT * 100):
            status = f"🟢 CÉLBAN (+{pnl_pct:.1f}%, húzd fel a stopot!)"
        else:
            status = f"⏳ FUT ({trading_days}/{config.TIME_STOP_DAYS} nap)"
            
        earnings_warning = "Nincs közeli adat"
        try:
            cal = stock.calendar
            if isinstance(cal, dict) and "Earnings Date" in cal and len(cal["Earnings Date"]) > 0:
                next_earn = cal["Earnings Date"]
                if hasattr(next_earn, "date"):
                    next_earn = next_earn.date()
                if isinstance(next_earn, date):
                    days_to_earn = (next_earn - date.today()).days
                    if 0 <= days_to_earn <= 5:
                        earnings_warning = f"⚠️ VIGYÁZAT: {days_to_earn} nap múlva jelentés ({next_earn})!"
                    elif days_to_earn > 5:
                        earnings_warning = f"✅ {next_earn} ({days_to_earn} nap múlva)"
        except Exception:
            pass

        return {
            "Ticker": ticker,
            "Belépő ($)": round(entry_price, 2),
            "Aktuális ($)": round(current_price, 2),
            "Hozam (%)": round(pnl_pct, 2),
            "Eltelt nap": trading_days,
            "Állapot": status,
            "Gyorsjelentés": earnings_warning
        }
    except Exception:
        return None

def scan_breaking_news(ticker):
    alerts = []
    try:
        stock = yf.Ticker(ticker)
        news_list = stock.news or []
        for item in news_list[:5]:
            content = item.get("content", item)
            title = content.get("title", "")
            if not title:
                continue
            title_lower = title.lower()
            flagged = any(kw in title_lower for kw in RED_FLAG_KEYWORDS)
            prefix = "🚨 [PIROS ZÁSZLÓ]" if flagged else "📰"
            alerts.append(f"{prefix} {title}")
    except Exception:
        pass
    return alerts

st.sidebar.title("⚙️ Swingtrader Beállítások")
usdhuf = get_usdhuf()
st.sidebar.metric("Élő USD/HUF", f"{usdhuf:.2f} Ft")

capital_huf = st.sidebar.number_input("Aktív tőke (HUF)", 500_000, 20_000_000, config.CURRENT_CAPITAL_HUF, 150_000)
capital_usd = capital_huf / usdhuf
risk_pct = st.sidebar.slider("Max. kockázat / trade (%)", 0.5, 2.5, config.RISK_PER_TRADE_PCT * 100, 0.25) / 100
max_risk_huf = capital_huf * risk_pct
max_risk_usd = capital_usd * risk_pct

st.sidebar.divider()
st.sidebar.write(f"**Tőke USD-ben:** `${capital_usd:,.0f}`")
st.sidebar.write(f"**Max. bukó / kötés:** `{max_risk_huf:,.0f} Ft` (`${max_risk_usd:.0f}`)")
st.sidebar.write(f"**Time-Stop szabály:** `{config.TIME_STOP_DAYS} nap` (min. `+{config.TIME_STOP_MIN_PROFIT*100:.0f}%`)")

st.title("📈 Swingtrader Co-Pilot")
st.subheader("1. Piaci Rezsim (Érdemes most kereskedni?)")
regime_data = analyze_market_regime()
cols = st.columns(len(regime_data))
for idx, (ticker, data) in enumerate(regime_data.items()):
    with cols[idx]:
        st.info(f"**{ticker}** (${data['price']:.2f})\n\n{data['regime']}\n\nSMA20 meredekség: `{data['slope']:.2f}%`")

st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("2. Napi Swing Jelöltek")
    custom_tickers = st.text_input("Figyelt részvények (vesszővel elválasztva)", ", ".join(config.DEFAULT_WATCHLIST))
    ticker_list = [x.strip().upper() for x in custom_tickers.split(",") if x.strip()]
    if st.button("🔍 Szkennelés futtatása", type="primary"):
        st.cache_data.clear()
    df_scan = scan_watchlist(ticker_list)
    if not df_scan.empty:
        st.dataframe(df_scan.sort_values(by="Setup"), use_container_width=True, hide_index=True)

with col_right:
    st.subheader("3. Pozícióméretező")
    sel_ticker = st.text_input("Kiválasztott Ticker", "NVDA").upper()
    entry_price = st.number_input("Tervezett belépő ($)", min_value=1.0, value=155.0, step=0.5)
    stop_price = st.number_input("Stop-Loss szint ($)", min_value=0.5, value=147.0, step=0.5)
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
            st.warning("⚠️ Egy pozícióba a tőkéd több mint 45%-át tennéd!")
    else:
        st.error("A belépő árnak nagyobbnak kell lennie a Stop-Loss árnál!")

st.divider()
st.subheader(f"📊 {sel_ticker} Technikai Grafikon & Stop-Loss Szintek")
chart_df = get_chart_data(sel_ticker)
if not chart_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=chart_df.index, open=chart_df["Open"], high=chart_df["High"],
        low=chart_df["Low"], close=chart_df["Close"], name=sel_ticker
    ))
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["SMA20"], line=dict(color="royalblue", width=1.5), name="SMA 20"))
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["SMA50"], line=dict(color="orange", width=1.5), name="SMA 50"))
    fig.add_hline(y=entry_price, line_dash="dash", line_color="green", annotation_text=f"Belépő: ${entry_price}")
    fig.add_hline(y=stop_price, line_dash="dash", line_color="red", annotation_text=f"Stop-Loss: ${stop_price}")
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("4. Aktív Pozíciók & Pajzs (Time-Stop + Hírradar)")
default_positions = pd.DataFrame([
    {"Ticker": "ADBE", "Belépő ($)": 235.0, "Belépés dátuma": "2026-11-10"},
    {"Ticker": "NVDA", "Belépő ($)": 142.0, "Belépés dátuma": "2026-11-20"},
])
edited_df = st.data_editor(default_positions, num_rows="dynamic", use_container_width=True)

if st.button("🛡️ Pozíciók és Hírek ellenőrzése"):
    status_rows = []
    for _, row in edited_df.iterrows():
        t = str(row["Ticker"]).strip().upper()
        if t and pd.notna(row["Belépő ($)"]) and pd.notna(row["Belépés dátuma"]):
            res = check_position_status(t, float(row["Belépő ($)"]), str(row["Belépés dátuma"]))
            if res:
                status_rows.append(res)
    if status_rows:
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)
        st.markdown("#### 📡 Friss Hírradar a tartott részvényekhez")
        for r in status_rows:
            with st.expander(f"{r['Ticker']} – Legfrissebb hírek"):
                news = scan_breaking_news(r["Ticker"])
                if news:
                    for n in news:
                        st.error(n) if "PIROS ZÁSZLÓ" in n else st.write(n)
                else:
                    st.write("Nincs friss hír.")
def check_position_status(ticker, entry_price, entry_date_str):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        current_price = float(hist["Close"].iloc[-1])
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        entry_dt = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
        trading_days = len(pd.bdate_range(start=entry_dt, end=date.today())) - 1
        trading_days = max(0, trading_days)
        
        if trading_days >= config.TIME_STOP_DAYS and pnl_pct < (config.TIME_STOP_MIN_PROFIT * 100):
            status = f"🚨 TIME-STOP! ({trading_days} napja áll, zárás javasolt)"
        elif pnl_pct >= (config.TIME_STOP_MIN_PROFIT * 100):
            status = f"🟢 CÉLBAN (+{pnl_pct:.1f}%, húzd fel a stopot!)"
        else:
            status = f"⏳ FUT ({trading_days}/{config.TIME_STOP_DAYS} nap)"
            
        earnings_warning = "Nincs közeli adat"
        try:
            cal = stock.calendar
            if isinstance(cal, dict) and "Earnings Date" in cal and len(cal["Earnings Date"]) > 0:
                next_earn = cal["Earnings Date"]
                if hasattr(next_earn, "date"):
                    next_earn = next_earn.date()
                if isinstance(next_earn, date):
                    days_to_earn = (next_earn - date.today()).days
                    if 0 <= days_to_earn <= 5:
                        earnings_warning = f"⚠️ VIGYÁZAT: {days_to_earn} nap múlva jelentés ({next_earn})!"
                    elif days_to_earn > 5:
                        earnings_warning = f"✅ {next_earn} ({days_to_earn} nap múlva)"
        except Exception:
            pass

        return {
            "Ticker": ticker,
            "Belépő ($)": round(entry_price, 2),
            "Aktuális ($)": round(current_price, 2),
            "Hozam (%)": round(pnl_pct, 2),
            "Eltelt nap": trading_days,
            "Állapot": status,
            "Gyorsjelentés": earnings_warning
        }
    except Exception:
        return None

def scan_breaking_news(ticker):
    alerts = []
    try:
        stock = yf.Ticker(ticker)
        news_list = stock.news or []
        for item in news_list[:5]:
            content = item.get("content", item)
            title = content.get("title", "")
            if not title:
                continue
            title_lower = title.lower()
            flagged = any(kw in title_lower for kw in RED_FLAG_KEYWORDS)
            prefix = "🚨 [PIROS ZÁSZLÓ]" if flagged else "📰"
            alerts.append(f"{prefix} {title}")
    except Exception:
        pass
    return alerts

st.sidebar.title("⚙️ Swingtrader Beállítások")
usdhuf = get_usdhuf()
st.sidebar.metric("Élő USD/HUF", f"{usdhuf:.2f} Ft")

capital_huf = st.sidebar.number_input("Aktív tőke (HUF)", 500_000, 20_000_000, config.CURRENT_CAPITAL_HUF, 150_000)
capital_usd = capital_huf / usdhuf
risk_pct = st.sidebar.slider("Max. kockázat / trade (%)", 0.5, 2.5, config.RISK_PER_TRADE_PCT * 100, 0.25) / 100
max_risk_huf = capital_huf * risk_pct
max_risk_usd = capital_usd * risk_pct

st.sidebar.divider()
st.sidebar.write(f"**Tőke USD-ben:** `${capital_usd:,.0f}`")
st.sidebar.write(f"**Max. bukó / kötés:** `{max_risk_huf:,.0f} Ft` (`${max_risk_usd:.0f}`)")
st.sidebar.write(f"**Time-Stop szabály:** `{config.TIME_STOP_DAYS} nap` (min. `+{config.TIME_STOP_MIN_PROFIT*100:.0f}%`)")

st.title("📈 Swingtrader Co-Pilot")
st.subheader("1. Piaci Rezsim (Érdemes most kereskedni?)")
regime_data = analyze_market_regime()
cols = st.columns(len(regime_data))
for idx, (ticker, data) in enumerate(regime_data.items()):
    with cols[idx]:
        st.info(f"**{ticker}** (${data['price']:.2f})\n\n{data['regime']}\n\nSMA20 meredekség: `{data['slope']:.2f}%`")

st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("2. Napi Swing Jelöltek")
    custom_tickers = st.text_input("Figyelt részvények (vesszővel elválasztva)", ", ".join(config.DEFAULT_WATCHLIST))
    ticker_list = [x.strip().upper() for x in custom_tickers.split(",") if x.strip()]
    if st.button("🔍 Szkennelés futtatása", type="primary"):
        st.cache_data.clear()
    df_scan = scan_watchlist(ticker_list)
    if not df_scan.empty:
        st.dataframe(df_scan.sort_values(by="Setup"), use_container_width=True, hide_index=True)

with col_right:
    st.subheader("3. Pozícióméretező")
    sel_ticker = st.text_input("Kiválasztott Ticker", "NVDA").upper()
    entry_price = st.number_input("Tervezett belépő ($)", min_value=1.0, value=155.0, step=0.5)
    stop_price = st.number_input("Stop-Loss szint ($)", min_value=0.5, value=147.0, step=0.5)
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
            st.warning("⚠️ Egy pozícióba a tőkéd több mint 45%-át tennéd!")
    else:
        st.error("A belépő árnak nagyobbnak kell lennie a Stop-Loss árnál!")

st.divider()
st.subheader(f"📊 {sel_ticker} Technikai Grafikon & Stop-Loss Szintek")
chart_df = get_chart_data(sel_ticker)
if not chart_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=chart_df.index, open=chart_df["Open"], high=chart_df["High"],
        low=chart_df["Low"], close=chart_df["Close"], name=sel_ticker
    ))
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["SMA20"], line=dict(color="royalblue", width=1.5), name="SMA 20"))
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["SMA50"], line=dict(color="orange", width=1.5), name="SMA 50"))
    fig.add_hline(y=entry_price, line_dash="dash", line_color="green", annotation_text=f"Belépő: ${entry_price}")
    fig.add_hline(y=stop_price, line_dash="dash", line_color="red", annotation_text=f"Stop-Loss: ${stop_price}")
    fig.update_layout(height=450, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("4. Aktív Pozíciók & Pajzs (Time-Stop + Hírradar)")
default_positions = pd.DataFrame([
    {"Ticker": "ADBE", "Belépő ($)": 235.0, "Belépés dátuma": "2026-11-10"},
    {"Ticker": "NVDA", "Belépő ($)": 142.0, "Belépés dátuma": "2026-11-20"},
])
edited_df = st.data_editor(default_positions, num_rows="dynamic", use_container_width=True)

if st.button("🛡️ Pozíciók és Hírek ellenőrzése"):
    status_rows = []
    for _, row in edited_df.iterrows():
        t = str(row["Ticker"]).strip().upper()
        if t and pd.notna(row["Belépő ($)"]) and pd.notna(row["Belépés dátuma"]):
            res = check_position_status(t, float(row["Belépő ($)"]), str(row["Belépés dátuma"]))
            if res:
                status_rows.append(res)
    if status_rows:
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)
        st.markdown("#### 📡 Friss Hírradar a tartott részvényekhez")
        for r in status_rows:
            with st.expander(f"{r['Ticker']} – Legfrissebb hírek"):
                news = scan_breaking_news(r["Ticker"])
                if news:
                    for n in news:
                        st.error(n) if "PIROS ZÁSZLÓ" in n else st.write(n)
                else:
                    st.write("Nincs friss hír.")
