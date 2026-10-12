import sqlite3
import os
from werkzeug.security import generate_password_hash
from config import DATABASE_PATH, DEFAULT_VIRTUAL_BALANCE

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mobile TEXT,
        password_hash TEXT NOT NULL,
        virtual_balance REAL NOT NULL DEFAULT 1000000.0,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Stocks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        sector TEXT NOT NULL,
        current_price REAL NOT NULL,
        change_amount REAL NOT NULL DEFAULT 0.0,
        change_pct REAL NOT NULL DEFAULT 0.0,
        day_high REAL NOT NULL,
        day_low REAL NOT NULL,
        high_52w REAL NOT NULL,
        low_52w REAL NOT NULL,
        volume INTEGER NOT NULL DEFAULT 0,
        pe_ratio REAL NOT NULL DEFAULT 0.0,
        market_cap TEXT NOT NULL,
        description TEXT,
        exchange TEXT DEFAULT 'NSE/BSE',
        isin TEXT DEFAULT '',
        series TEXT DEFAULT 'EQ'
    );
    """)

    # Ensure exchange, isin, series columns exist if table was already created
    stock_cols = [c[1] for c in cursor.execute("PRAGMA table_info(stocks)").fetchall()]
    if 'exchange' not in stock_cols:
        cursor.execute("ALTER TABLE stocks ADD COLUMN exchange TEXT DEFAULT 'NSE/BSE'")
    if 'isin' not in stock_cols:
        cursor.execute("ALTER TABLE stocks ADD COLUMN isin TEXT DEFAULT ''")
    if 'series' not in stock_cols:
        cursor.execute("ALTER TABLE stocks ADD COLUMN series TEXT DEFAULT 'EQ'")

    # Holdings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        stock_symbol TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        avg_buy_price REAL NOT NULL,
        total_invested REAL NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(user_id, stock_symbol)
    );
    """)

    # Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        stock_symbol TEXT NOT NULL,
        order_type TEXT NOT NULL,
        action TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        target_price REAL,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    # Watchlist table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        stock_symbol TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(user_id, stock_symbol)
    );
    """)

    # Transactions ledger
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_code TEXT,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        balance_after REAL NOT NULL,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    # Notifications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    conn.commit()

    # Seed Initial Data if not present
    seed_data(cursor, conn)
    conn.close()

def seed_data(cursor, conn):
    # Check if users already exist
    cursor.execute("SELECT COUNT(*) as count FROM users")
    user_count = cursor.fetchone()['count']
    
    if user_count == 0:
        # Default Demo User
        demo_pass = generate_password_hash("trendcore123")
        admin_pass = generate_password_hash("admin123")

        cursor.execute("""
        INSERT INTO users (name, email, mobile, password_hash, virtual_balance, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Trader Rahul", "trader@trendcore.com", "+91 9876543210", demo_pass, DEFAULT_VIRTUAL_BALANCE, 0))
        demo_user_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO users (name, email, mobile, password_hash, virtual_balance, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("TrendCore Admin", "admin@trendcore.com", "+91 9811122233", admin_pass, DEFAULT_VIRTUAL_BALANCE, 1))

        # Initial Welcome notification for Demo User
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, ?)
        """, (demo_user_id, "Welcome to TrendCore", "Your account has been credited with ₹10,00,000 in virtual paper-trading capital. Trade, Learn, Grow!", "success"))

        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, ?)
        """, (demo_user_id, "Market Opened", "NSE & BSE regular trading session is open. Explore Indian top equities now.", "market"))

        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, ?)
        """, (demo_user_id, "Watchlist Ready", "6 top Indian market leaders (RELIANCE, TCS, INFY, HDFCBANK, ITC, SBIN) added to your watchlist.", "info"))

    # Seed Stocks
    cursor.execute("SELECT COUNT(*) as count FROM stocks")
    stock_count = cursor.fetchone()['count']

    if stock_count == 0:
        initial_stocks = [
            ("RELIANCE", "Reliance Industries Ltd.", "Energy & Telecom", 1420.50, 12.40, 0.88, 1435.00, 1405.20, 1608.80, 1180.00, 14820900, 26.4, "₹19.2 Lakh Cr", "India's premier conglomerate with leading market presence in energy, petrochemicals, telecommunications (Jio), and retail."),
            ("TCS", "Tata Consultancy Services Ltd.", "Information Technology", 4185.00, 32.60, 0.78, 4210.00, 4140.50, 4585.00, 3450.00, 3420800, 31.8, "₹15.1 Lakh Cr", "Global leader in IT services, consulting, and business solutions with decades of tech innovation."),
            ("INFY", "Infosys Limited", "Information Technology", 1875.20, -14.10, -0.75, 1898.00, 1860.00, 1990.00, 1358.00, 7810500, 27.2, "₹7.8 Lakh Cr", "Next-generation digital services and consulting multinational enabling global clients to navigate digital transformation."),
            ("HDFCBANK", "HDFC Bank Limited", "Banking & Finance", 1640.75, 18.25, 1.12, 1655.00, 1618.00, 1794.00, 1363.00, 19850000, 19.5, "₹12.5 Lakh Cr", "India's largest private sector bank renowned for robust retail lending and nationwide financial infrastructure."),
            ("ICICIBANK", "ICICI Bank Limited", "Banking & Finance", 1215.30, 8.40, 0.70, 1228.00, 1202.00, 1300.00, 930.00, 14200000, 18.2, "₹8.6 Lakh Cr", "Leading private sector bank offering a wide range of banking products and digital financial services."),
            ("SBIN", "State Bank of India", "Banking & Finance", 812.40, -4.60, -0.56, 824.00, 808.00, 912.00, 555.00, 22100000, 10.4, "₹7.2 Lakh Cr", "Fortune 500 public sector bank and financial services statutory body with historic roots in India."),
            ("ITC", "ITC Limited", "FMCG & Conglomerate", 485.60, 3.10, 0.64, 491.00, 481.50, 520.00, 399.00, 16400000, 28.5, "₹6.1 Lakh Cr", "Diversified conglomerate with leadership in FMCG, hotels, paperboards, packaging, and agri-business."),
            ("HINDUNILVR", "Hindustan Unilever Ltd.", "FMCG", 2690.00, -18.50, -0.68, 2720.00, 2675.00, 3035.00, 2170.00, 2100000, 58.1, "₹6.3 Lakh Cr", "India's largest consumer goods enterprise touching 9 out of 10 Indian households daily."),
            ("LT", "Larsen & Toubro Ltd.", "Infrastructure & Engineering", 3620.00, 45.00, 1.26, 3650.00, 3560.00, 3919.00, 2870.00, 2980000, 34.0, "₹4.9 Lakh Cr", "Technology, engineering, construction, and manufacturing conglomerate driving mega infrastructure projects."),
            ("AXISBANK", "Axis Bank Limited", "Banking & Finance", 1180.20, -6.80, -0.57, 1195.00, 1172.00, 1339.00, 951.00, 9200000, 14.8, "₹3.6 Lakh Cr", "Third largest private sector bank in India covering the entire spectrum of financial services."),
            ("BHARTIARTL", "Bharti Airtel Ltd.", "Telecom", 1610.50, 21.30, 1.34, 1628.00, 1585.00, 1715.00, 880.00, 6700000, 45.3, "₹9.2 Lakh Cr", "Global telecommunications giant with 5G connectivity spanning South Asia and Africa."),
            ("TATAMOTORS", "Tata Motors Limited", "Automobile", 970.30, 15.60, 1.63, 982.00, 950.00, 1179.00, 600.00, 11400000, 11.2, "₹3.5 Lakh Cr", "Automobile pioneer leading India's electric mobility revolution alongside luxury brand Jaguar Land Rover."),
            ("MARUTI", "Maruti Suzuki India Ltd.", "Automobile", 12450.00, -85.00, -0.68, 12600.00, 12380.00, 13680.00, 9735.00, 540000, 27.6, "₹3.9 Lakh Cr", "Market leader in the Indian passenger car segment with unparalleled brand trust and distribution."),
            ("BAJFINANCE", "Bajaj Finance Limited", "Financial Services", 7140.00, 58.00, 0.82, 7210.00, 7060.00, 8192.00, 6160.00, 1120000, 30.1, "₹4.4 Lakh Cr", "Largest non-banking financial institution (NBFC) driving digital consumer finance and lending in India."),
            ("SUNPHARMA", "Sun Pharmaceutical Ind.", "Healthcare & Pharma", 1830.00, 12.00, 0.66, 1855.00, 1810.00, 1960.00, 1110.00, 2450000, 38.4, "₹4.3 Lakh Cr", "Leading specialty pharmaceutical company delivering affordable high-quality medicines globally.")
        ]

        cursor.executemany("""
        INSERT INTO stocks (symbol, name, sector, current_price, change_amount, change_pct, day_high, day_low, high_52w, low_52w, volume, pe_ratio, market_cap, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_stocks)

        # Seed default watchlist for Trader Rahul (user_id 1)
        cursor.execute("SELECT id FROM users WHERE email = 'trader@trendcore.com'")
        trader = cursor.fetchone()
        if trader:
            u_id = trader['id']
            default_watch = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC", "SBIN"]
            for sym in default_watch:
                cursor.execute("INSERT OR IGNORE INTO watchlist (user_id, stock_symbol) VALUES (?, ?)", (u_id, sym))

    conn.commit()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully at:", DATABASE_PATH)
