import yfinance as yf
import pandas as pd
from datetime import datetime, date
import config

RED_FLAG_KEYWORDS = [
    "ceo", "resign", "step down", "steps down", "depart", 
    "guidance", "cut", "lower", "miss", "misses", "sec", 
    "investigation", "lawsuit", "downgrade", "halt"
]

def check_position_status(ticker, entry_price, entry_date_str):
    """Ellenőrzi az aktuális árat, a hozamot, az eltelt napokat (Time-Stop) és a gyorsjelentést."""
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
                next_earn = cal["Earnings Date"][0]
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
    """Lekéri a legfrissebb híreket és piros zászlót tesz a veszélyes kulcsszavakra."""
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

