import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'trendcore-secret-super-secure-key-2026')
DATABASE_PATH = os.path.join(BASE_DIR, 'database.db')

DEFAULT_VIRTUAL_BALANCE = 1000000.0  # ₹10,00,000 Starting Virtual Capital
APP_DOMAIN = os.environ.get('APP_DOMAIN', 'trendcore.local')
DEFAULT_PORT = int(os.environ.get('PORT', 80))
FALLBACK_PORT = 5000

MARKET_INDICES = [
    {"symbol": "NIFTY50", "name": "NIFTY 50", "base_price": 24150.80, "change_pct": 0.42},
    {"symbol": "SENSEX", "name": "SENSEX", "base_price": 79620.40, "change_pct": 0.38},
    {"symbol": "BANKNIFTY", "name": "BANK NIFTY", "base_price": 52410.25, "change_pct": -0.18},
    {"symbol": "NIFTYIT", "name": "NIFTY IT", "base_price": 41830.15, "change_pct": 0.74},
]
