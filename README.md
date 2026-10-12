# 📈 TrendCore — Paper Trading & Indian Stock Market Simulator

> **Tagline:** *Trade. Learn. Grow.*  
> **Platform Domain:** `http://trendcore.local`  
> **Initial Paper Balance:** ₹10,00,000 (Virtual Currency)

**TrendCore** is a modern, responsive paper-trading and educational stock-market simulation platform designed for students, beginners, and aspiring investors to master Indian equities (NSE / BSE) with zero financial risk.

---

## 🌟 Key Features

1. **₹10,00,000 Virtual Capital:** Every trader starts with ₹10,00,000 in simulated paper currency to test strategies and buy blue-chip stocks risk-free.
2. **Realistic Indian Market Simulation:**
   - **Indices:** NIFTY 50, SENSEX, BANK NIFTY, NIFTY IT with live ticker tape.
   - **Equities:** RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, ITC, HINDUNILVR, LT, AXISBANK, and more.
3. **Interactive Multi-Timeframe Charts:**
   - Dynamic charts with timeframes: `1D`, `1W`, `1M`, `3M`, `6M`, `1Y`, `5Y`.
   - Real-time indicator of period high, low, and returns.
4. **Professional Buy / Sell Trading Panel:**
   - Market Orders (instant execution) & Limit Orders (price targets).
   - Dynamic quantity stepper and quick chips (`+1`, `+10`, `+50`, `+100`, `Max`).
   - Real-time cash balance and portfolio quantity validation.
5. **Portfolio & Holdings Analytics:**
   - Asset allocation donut chart.
   - Real-time P&L tracking (Invested amount, Current value, Overall returns in ₹ and %).
6. **Order Book & Open Limit Orders:**
   - Full order history with tabs: `All`, `Open`, `Completed`, `Cancelled`.
   - One-click cancellation of open limit orders with automatic escrow refund.
7. **Persistent Watchlist:**
   - Star any stock across the website to keep track of its price movements.
   - Pre-seeded with 6 Indian market leaders.
8. **TrendCore Learn Academy:**
   - Stock Market Basics (NSE, BSE, NIFTY, SENSEX).
   - Trading Basics (Market vs Limit Orders, Stop Loss, Intraday vs Delivery).
   - Investment Basics (SIP, Mutual Funds, ETFs, Diversification, Risk Management).
   - Interactive knowledge check quiz.
9. **Dark Mode & Responsive Design:**
   - High-contrast sleek financial dark theme with local preference persistence.
   - 100% responsive across mobile, tablet, laptop, and desktop viewports.
10. **Admin Dashboard:**
    - Platform trading statistics, buy vs. sell ratios, most traded stocks, user accounts registry, and market price simulation override.

---

## 🚀 Windows Local Domain Setup (`http://trendcore.local`)

TrendCore is configured to run at **`http://trendcore.local`** (without port numbers or "localhost").

### Option A: Automatic 1-Click Setup (Recommended)
1. Right-click **`setup_hosts.bat`** in the project folder and select **Run as Administrator** (or double-click; Windows UAC will prompt for elevation).
2. It will automatically add `127.0.0.1 trendcore.local` to `C:\Windows\System32\drivers\etc\hosts` and flush the DNS cache.
3. Double-click **`run.bat`** to start the server and automatically launch `http://trendcore.local` in your browser!

### Option B: Manual Setup
1. Open **Notepad** as **Administrator** (search for Notepad in Start Menu, right-click, select *Run as Administrator*).
2. Open the file: `C:\Windows\System32\drivers\etc\hosts`.
3. Add the following line at the end:
   ```
   127.0.0.1 trendcore.local
   ```
4. Save the file.
5. In VS Code terminal or PowerShell, run:
   ```powershell
   python app.py
   ```
6. Open your browser and navigate to:
   ```
   http://trendcore.local
   ```

---

## 🔑 Demo Accounts & Pre-Loaded Capital

You can sign in immediately using the pre-configured demo accounts or click the **"⚡ Instant Demo Trader"** button on the landing or login pages:

| Role | Email | Password | Pre-Loaded Balance |
| :--- | :--- | :--- | :--- |
| **Demo Trader** | `trader@trendcore.com` | `trendcore123` | **₹10,00,000.00** |
| **Administrator** | `admin@trendcore.com` | `admin123` | **₹10,00,000.00** |

You can also register a new account on `/signup`; every newly registered user automatically receives **₹10,00,000** in virtual paper money!

---

## 📁 Project Architecture

```
TrendCore/
│
├── app.py                  # Main Flask application, routes, auth, trade engine
├── models.py               # SQLite schema, db connection, initial seeder
├── market_service.py       # Live & simulated stock data, chart timeframe generator
├── config.py               # App configuration, domain, ports, initial balance
├── requirements.txt        # Python package dependencies
├── database.db             # Local SQLite database
│
├── setup_hosts.bat         # 1-Click Windows hosts configuration script
├── setup_domain.ps1        # PowerShell equivalent script
├── run.bat                 # 1-Click launcher
│
├── static/
│   ├── css/
│   │   └── style.css       # Clean design system, Tailwind-like styling, dark mode
│   ├── js/
│   │   └── app.js          # Interactive Chart.js, search modal, trade math, toasts
│   └── images/
│       ├── logo.svg        # TrendCore brand logo
│       └── favicon.svg     # Browser tab favicon
│
└── templates/
    ├── base.html           # Header, navbar, ticker tape, search modal, footer
    ├── index.html          # Public landing showcase
    ├── dashboard.html      # Main trader dashboard with balance & market overview
    ├── markets.html        # Indian equities directory with sector filters
    ├── stock.html          # Stock details, timeframe charts & Buy/Sell panel
    ├── portfolio.html      # Holdings table & allocation donut chart
    ├── orders.html         # Order history & cancel pending limit orders
    ├── watchlist.html      # Starred stocks with live quotes
    ├── learn.html          # Educational academy modules & interactive quiz
    ├── profile.html        # User settings & virtual funds reset button
    ├── login.html          # Login screen + 1-click demo login
    ├── signup.html         # Registration with ₹10 Lakh virtual credit
    └── admin.html          # Admin analytics & platform management
```

---

## ⚖️ Educational Paper Trading Disclaimer

TrendCore is an educational paper-trading simulator created for learning stock market principles and evaluating trading strategies. All currencies, stocks, portfolios, and orders are purely simulated and have no real financial value. No real money can ever be deposited, traded, or withdrawn.
