# Alapbeállítások (HUF)
CURRENT_CAPITAL_HUF = 2_850_000   # Jelenlegi egyenleged (~2,85M Ft)
MAX_CAPITAL_HUF = 6_000_000       # Tervezett emelt keret

# Kockázatkezelés
RISK_PER_TRADE_PCT = 0.01         # Max. 1% kockázat kötésenként (~28.500 Ft)
MAX_POSITIONS = 3                 # Egyszerre max. 3 pozíció (~950e Ft / pozíció)
MIN_EXPECTED_MOVE_PCT = 0.04      # Min. 4% elvárt elmozdulás (jutalékvédelem)

# Időalapú Stop-Loss (Time-Stop) - A "beragadás" ellen
TIME_STOP_DAYS = 10               # Max. 10 kereskedési nap (2 hét)
TIME_STOP_MIN_PROFIT = 0.03       # Ennyi idő alatt min. +3%-ot kell hoznia

# Figyelt indexek a piaci rezsimhez
BENCHMARK_TICKERS = ["SPY", "QQQ"]

# Alapértelmezett figyelőlista (Watchlist)
DEFAULT_WATCHLIST = [
    "NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA", 
    "AMD", "AVGO", "CRM", "ADBE", "NFLX", "PLTR", "SMCI"
]
