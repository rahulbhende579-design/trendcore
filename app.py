import os
import sys
import random
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import SECRET_KEY, DEFAULT_VIRTUAL_BALANCE, APP_DOMAIN, DEFAULT_PORT, FALLBACK_PORT
from models import get_db, init_db
from market_service import MarketService

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Ensure DB is initialized
init_db()

# --- Custom Jinja Filters ---
@app.template_filter('inr')
def format_inr(value):
    """Format number into Indian numbering system (e.g., 10,00,000.00)."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return "₹0.00"
    
    is_neg = val < 0
    val = abs(val)
    
    parts = f"{val:.2f}".split(".")
    integer_part = parts[0]
    decimal_part = parts[1]
    
    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        # Group in pairs of 2 from right to left
        grouped = []
        while len(remaining) > 2:
            grouped.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            grouped.insert(0, remaining)
        formatted = ",".join(grouped) + "," + last_three
        
    return f"{'-' if is_neg else ''}₹{formatted}.{decimal_part}"

@app.template_filter('inr_compact')
def format_inr_compact(value):
    """Format large numbers into Cr / Lakh (e.g. ₹10 Lakh)."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return "₹0"
    if abs(val) >= 10000000:
        return f"₹{val/10000000:.2f} Cr"
    elif abs(val) >= 100000:
        return f"₹{val/100000:.2f} Lakh"
    else:
        return format_inr(value)

# --- Context Processor (Global template variables) ---
@app.context_processor
def inject_global_data():
    user = None
    notifications = []
    unread_count = 0
    watchlist_symbols = []
    
    user_id = session.get('user_id')
    if user_id:
        db = get_db()
        user_row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user_row:
            user = dict(user_row)
            # Fetch notifications
            notif_rows = db.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 8", (user_id,)).fetchall()
            notifications = [dict(n) for n in notif_rows]
            unread_count = sum(1 for n in notifications if not n['is_read'])
            
            # Fetch watchlist symbols
            wl_rows = db.execute("SELECT stock_symbol FROM watchlist WHERE user_id = ?", (user_id,)).fetchall()
            watchlist_symbols = [r['stock_symbol'] for r in wl_rows]
        db.close()
        
    ticker_items = MarketService.get_ticker_items()
    indices = MarketService.get_indices()
    
    # Check limit orders execution on view
    MarketService.check_and_execute_limit_orders()

    return {
        'current_user': user,
        'notifications': notifications,
        'unread_notifications_count': unread_count,
        'user_watchlist_symbols': watchlist_symbols,
        'ticker_items': ticker_items,
        'global_indices': indices,
        'APP_DOMAIN': APP_DOMAIN
    }

# --- Authentication Helpers ---
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Auto-login to demo trader if not logged in so reviewing the app is seamless
            db = get_db()
            trader = db.execute("SELECT id FROM users WHERE email = 'trader@trendcore.com'").fetchone()
            db.close()
            if trader:
                session['user_id'] = trader['id']
                session['user_name'] = "Trader Rahul"
                session['is_admin'] = 0
            else:
                return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash("Admin access required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/demo-login')
def demo_login():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = 'trader@trendcore.com'").fetchone()
    db.close()
    if user:
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['is_admin'] = bool(user['is_admin'])
        flash("Logged into Demo Trader account! ₹10,00,000 virtual balance is loaded.", "success")
        return redirect(url_for('dashboard'))
    flash("Demo account not found.", "danger")
    return redirect(url_for('login'))

@app.route('/')
def index():

    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    featured_stocks = MarketService.get_all_stocks(limit=6)['stocks']
    indices = MarketService.get_indices()
    return render_template('index.html', featured_stocks=featured_stocks, indices=indices)

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    # Calculate holdings value and P&L
    holdings_rows = db.execute("""
        SELECT h.*, s.name, s.current_price, s.change_pct, s.change_amount
        FROM holdings h
        JOIN stocks s ON h.stock_symbol = s.symbol
        WHERE h.user_id = ?
    """, (user_id,)).fetchall()
    
    total_invested = 0.0
    current_holdings_value = 0.0
    today_pnl = 0.0
    
    for h in holdings_rows:
        total_invested += h['total_invested']
        curr_val = h['quantity'] * h['current_price']
        current_holdings_value += curr_val
        today_pnl += h['quantity'] * h['change_amount']
        
    overall_pnl = current_holdings_value - total_invested
    overall_pnl_pct = (overall_pnl / total_invested * 100.0) if total_invested > 0 else 0.0
    portfolio_value = user['virtual_balance'] + current_holdings_value

    # Recent orders
    recent_orders = db.execute("""
        SELECT * FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC LIMIT 5
    """, (user_id,)).fetchall()

    # Top market gainers and losers
    gainers = db.execute("SELECT * FROM stocks WHERE change_pct > 0 ORDER BY change_pct DESC LIMIT 4").fetchall()
    losers = db.execute("SELECT * FROM stocks WHERE change_pct < 0 ORDER BY change_pct ASC LIMIT 4").fetchall()

    db.close()

    # Dynamic time-of-day greeting
    hour = datetime.datetime.now().hour
    if hour < 12:
        greeting = "Good Morning"
    elif hour < 17:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"

    return render_template('dashboard.html',
                           user=user,
                           greeting=greeting,
                           portfolio_value=portfolio_value,
                           available_balance=user['virtual_balance'],
                           total_invested=total_invested,
                           current_holdings_value=current_holdings_value,
                           today_pnl=today_pnl,
                           overall_pnl=overall_pnl,
                           overall_pnl_pct=overall_pnl_pct,
                           recent_orders=recent_orders,
                           gainers=gainers,
                           losers=losers)

@app.route('/markets')
def markets():
    sector = request.args.get('sector', 'all')
    exchange = request.args.get('exchange', 'all')
    search = request.args.get('q', '')
    sort = request.args.get('sort', 'volume_desc')
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    per_page = 40
    result = MarketService.get_all_stocks(
        sector=sector,
        query=search,
        exchange=exchange,
        sort=sort,
        page=page,
        per_page=per_page
    )
    indices = MarketService.get_indices()
    
    sectors = ["All", "Banking & Finance", "Information Technology", "Energy & Telecom", "FMCG", "Automobile", "Infrastructure & Engineering", "Healthcare & Pharma", "Other Equities"]
    return render_template(
        'markets.html',
        stocks=result['stocks'],
        total_count=result['total_count'],
        page=result['page'],
        total_pages=result['total_pages'],
        indices=indices,
        current_sector=sector,
        current_exchange=exchange,
        current_sort=sort,
        sectors=sectors,
        search_query=search
    )

@app.route('/stock/<symbol>')
def stock_detail(symbol):
    stock = MarketService.get_stock(symbol)
    if not stock:
        flash(f"Stock symbol '{symbol}' was not found.", "danger")
        return redirect(url_for('markets'))

    # If user is logged in, fetch user's holdings for this stock
    user_holding = None
    user_balance = DEFAULT_VIRTUAL_BALANCE
    if 'user_id' in session:
        db = get_db()
        user_holding = db.execute("SELECT * FROM holdings WHERE user_id = ? AND stock_symbol = ?", (session['user_id'], symbol.upper())).fetchone()
        user = db.execute("SELECT virtual_balance FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        if user:
            user_balance = user['virtual_balance']
        db.close()

    # Generate initial 1D chart data
    initial_chart = MarketService.generate_chart_data(symbol, timeframe='1D')

    return render_template('stock.html', 
                           stock=stock, 
                           user_holding=user_holding, 
                           user_balance=user_balance,
                           initial_chart=initial_chart)

@app.route('/portfolio')
@login_required
def portfolio():
    user_id = session['user_id']
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    holdings_rows = db.execute("""
        SELECT h.*, s.name, s.current_price, s.change_pct, s.change_amount, s.sector
        FROM holdings h
        JOIN stocks s ON h.stock_symbol = s.symbol
        WHERE h.user_id = ?
        ORDER BY (h.quantity * s.current_price) DESC
    """, (user_id,)).fetchall()
    
    holdings_list = []
    total_invested = 0.0
    current_value = 0.0
    
    allocation_labels = []
    allocation_values = []

    for h in holdings_rows:
        curr_val = h['quantity'] * h['current_price']
        pnl = curr_val - h['total_invested']
        pnl_pct = (pnl / h['total_invested'] * 100.0) if h['total_invested'] > 0 else 0.0
        
        total_invested += h['total_invested']
        current_value += curr_val
        
        allocation_labels.append(h['stock_symbol'])
        allocation_values.append(round(curr_val, 2))
        
        holdings_list.append({
            'symbol': h['stock_symbol'],
            'name': h['name'],
            'sector': h['sector'],
            'quantity': h['quantity'],
            'avg_buy_price': h['avg_buy_price'],
            'current_price': h['current_price'],
            'invested': h['total_invested'],
            'current_value': curr_val,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })
        
    overall_pnl = current_value - total_invested
    overall_pnl_pct = (overall_pnl / total_invested * 100.0) if total_invested > 0 else 0.0
    portfolio_total = user['virtual_balance'] + current_value

    db.close()
    return render_template('portfolio.html',
                           user=user,
                           portfolio_total=portfolio_total,
                           available_balance=user['virtual_balance'],
                           total_invested=total_invested,
                           current_value=current_value,
                           overall_pnl=overall_pnl,
                           overall_pnl_pct=overall_pnl_pct,
                           holdings=holdings_list,
                           allocation_labels=allocation_labels,
                           allocation_values=allocation_values)

@app.route('/orders')
@login_required
def orders():
    user_id = session['user_id']
    status_filter = request.args.get('status', 'all').upper()
    
    db = get_db()
    if status_filter in ['OPEN', 'COMPLETED', 'CANCELLED']:
        orders_rows = db.execute("""
            SELECT o.*, s.name as company_name 
            FROM orders o
            LEFT JOIN stocks s ON o.stock_symbol = s.symbol
            WHERE o.user_id = ? AND o.status = ?
            ORDER BY o.created_at DESC
        """, (user_id, status_filter)).fetchall()
    else:
        status_filter = 'ALL'
        orders_rows = db.execute("""
            SELECT o.*, s.name as company_name 
            FROM orders o
            LEFT JOIN stocks s ON o.stock_symbol = s.symbol
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC
        """, (user_id,)).fetchall()
        
    db.close()
    return render_template('orders.html', orders=orders_rows, current_tab=status_filter)

@app.route('/watchlist')
@login_required
def watchlist():
    user_id = session['user_id']
    db = get_db()
    items = db.execute("""
        SELECT w.*, s.name, s.sector, s.current_price, s.change_amount, s.change_pct, s.day_high, s.day_low, s.high_52w, s.low_52w, s.volume
        FROM watchlist w
        JOIN stocks s ON w.stock_symbol = s.symbol
        WHERE w.user_id = ?
        ORDER BY w.created_at DESC
    """, (user_id,)).fetchall()
    
    all_stocks = db.execute("SELECT symbol, name, current_price FROM stocks ORDER BY volume DESC, symbol ASC LIMIT 500").fetchall()
    db.close()
    return render_template('watchlist.html', watchlist_items=items, all_stocks=all_stocks)

@app.route('/learn')
def learn():
    return render_template('learn.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            name = request.form.get('name', '').strip()
            mobile = request.form.get('mobile', '').strip()
            if name:
                db.execute("UPDATE users SET name = ?, mobile = ? WHERE id = ?", (name, mobile, user_id))
                db.commit()
                session['user_name'] = name
                flash("Profile updated successfully!", "success")
            else:
                flash("Name cannot be empty.", "danger")
        elif action == 'change_password':
            old_pass = request.form.get('old_password', '')
            new_pass = request.form.get('new_password', '')
            confirm_pass = request.form.get('confirm_password', '')
            
            if not check_password_hash(user['password_hash'], old_pass):
                flash("Current password incorrect.", "danger")
            elif len(new_pass) < 6:
                flash("New password must be at least 6 characters long.", "danger")
            elif new_pass != confirm_pass:
                flash("New passwords do not match.", "danger")
            else:
                db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_pass), user_id))
                db.commit()
                flash("Password changed successfully!", "success")
        return redirect(url_for('profile'))

    # Trading metrics
    trades_count = db.execute("SELECT COUNT(*) as count FROM orders WHERE user_id = ? AND status = 'COMPLETED'", (user_id,)).fetchone()['count']
    total_orders = db.execute("SELECT COUNT(*) as count FROM orders WHERE user_id = ?", (user_id,)).fetchone()['count']
    holdings_count = db.execute("SELECT COUNT(*) as count FROM holdings WHERE user_id = ?", (user_id,)).fetchone()['count']
    
    # Calculate total P&L
    holdings_rows = db.execute("""
        SELECT h.*, s.current_price FROM holdings h 
        JOIN stocks s ON h.stock_symbol = s.symbol 
        WHERE h.user_id = ?
    """, (user_id,)).fetchall()
    curr_h_val = sum(h['quantity'] * h['current_price'] for h in holdings_rows)
    tot_inv = sum(h['total_invested'] for h in holdings_rows)
    overall_pnl = curr_h_val - tot_inv

    db.close()
    return render_template('profile.html', 
                           user=user, 
                           trades_count=trades_count,
                           total_orders=total_orders,
                           holdings_count=holdings_count,
                           overall_pnl=overall_pnl)

@app.route('/admin')
@admin_required
def admin():
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
    total_trades = db.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'COMPLETED'").fetchone()['count']
    buy_trades = db.execute("SELECT COUNT(*) as count FROM orders WHERE action = 'BUY' AND status = 'COMPLETED'").fetchone()['count']
    sell_trades = db.execute("SELECT COUNT(*) as count FROM orders WHERE action = 'SELL' AND status = 'COMPLETED'").fetchone()['count']
    
    total_virtual_volume = db.execute("SELECT SUM(total_amount) as total FROM orders WHERE status = 'COMPLETED'").fetchone()['total'] or 0.0
    total_user_balance = db.execute("SELECT SUM(virtual_balance) as total FROM users").fetchone()['total'] or 0.0

    # Most traded stocks
    most_traded = db.execute("""
        SELECT stock_symbol, COUNT(*) as trades, SUM(quantity) as total_qty, SUM(total_amount) as volume
        FROM orders
        WHERE status = 'COMPLETED'
        GROUP BY stock_symbol
        ORDER BY trades DESC
        LIMIT 5
    """,).fetchall()

    users_list = db.execute("SELECT id, name, email, mobile, virtual_balance, is_admin, created_at FROM users ORDER BY created_at DESC").fetchall()
    all_orders = db.execute("""
        SELECT o.*, u.name as user_name 
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC LIMIT 20
    """).fetchall()

    stocks_list = db.execute("SELECT * FROM stocks ORDER BY symbol ASC").fetchall()
    db.close()

    return render_template('admin.html',
                           total_users=total_users,
                           active_users=total_users,
                           total_trades=total_trades,
                           buy_trades=buy_trades,
                           sell_trades=sell_trades,
                           total_virtual_volume=total_virtual_volume,
                           total_user_balance=total_user_balance,
                           most_traded=most_traded,
                           users_list=users_list,
                           all_orders=all_orders,
                           stocks_list=stocks_list)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ? OR name = ?", (login_id, login_id)).fetchone()
        db.close()

        if user and check_password_hash(user['password_hash'], password):
            session.permanent = remember
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['is_admin'] = bool(user['is_admin'])
            flash(f"Welcome back, {user['name']}!", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash("Invalid email/username or password.", "danger")

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash("Please fill in all required fields.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            db = get_db()
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                db.close()
                flash("An account with this email already exists. Please login.", "warning")
                return redirect(url_for('login'))

            hashed = generate_password_hash(password)
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO users (name, email, mobile, password_hash, virtual_balance, is_admin)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (name, email, mobile, hashed, DEFAULT_VIRTUAL_BALANCE))
            new_id = cursor.lastrowid

            # Initial notifications
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (?, ?, ?, ?)
            """, (new_id, "Welcome to TrendCore!", "₹10,00,000 in virtual paper funds credited. Practice real-time trading risk-free!", "success"))

            # Seed default watchlist
            for sym in ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC", "SBIN"]:
                cursor.execute("INSERT OR IGNORE INTO watchlist (user_id, stock_symbol) VALUES (?, ?)", (new_id, sym))

            db.commit()
            db.close()

            session['user_id'] = new_id
            session['user_name'] = name
            session['is_admin'] = False
            flash("Account created successfully! ₹10,00,000 virtual balance credited.", "success")
            return redirect(url_for('dashboard'))

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('login'))

# --- API Endpoints ---

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    results = MarketService.search_stocks(q)
    return jsonify({'success': True, 'results': results})

@app.route('/api/stock/<symbol>/chart')
def api_stock_chart(symbol):
    timeframe = request.args.get('timeframe', '1D').upper()
    chart_data = MarketService.generate_chart_data(symbol, timeframe)
    return jsonify({'success': True, 'data': chart_data})

@app.route('/api/trade/place', methods=['POST'])
@login_required
def api_place_trade():
    data = request.get_json() or {}
    symbol = data.get('symbol', '').strip().upper()
    action = data.get('action', '').strip().upper()  # BUY or SELL
    order_type = data.get('order_type', 'MARKET').strip().upper()  # MARKET or LIMIT
    
    try:
        quantity = int(data.get('quantity', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid quantity. Must be a positive integer.'}), 400

    if quantity <= 0:
        return jsonify({'success': False, 'message': 'Quantity must be at least 1 share.'}), 400

    stock = MarketService.get_stock(symbol)
    if not stock:
        return jsonify({'success': False, 'message': f'Stock {symbol} not found.'}), 404

    curr_price = stock['current_price']
    
    if order_type == 'LIMIT':
        try:
            target_price = float(data.get('target_price', 0))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid limit price.'}), 400
        if target_price <= 0:
            return jsonify({'success': False, 'message': 'Limit price must be greater than zero.'}), 400
        execution_price = target_price
    else:
        target_price = None
        execution_price = curr_price

    total_amount = round(quantity * execution_price, 2)
    user_id = session['user_id']
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    # Generate clean order code
    order_code = f"TC-{random.randint(100000, 999999)}"

    if action == 'BUY':
        if user['virtual_balance'] < total_amount:
            db.close()
            return jsonify({
                'success': False,
                'message': f"Insufficient virtual balance! Required: ₹{total_amount:,.2f}, Available: ₹{user['virtual_balance']:,.2f}"
            }), 400

        # Deduct balance
        new_balance = round(user['virtual_balance'] - total_amount, 2)
        db.execute("UPDATE users SET virtual_balance = ? WHERE id = ?", (new_balance, user_id))

        if order_type == 'MARKET':
            # Update or create holding
            existing_holding = db.execute("SELECT * FROM holdings WHERE user_id = ? AND stock_symbol = ?", (user_id, symbol)).fetchone()
            if existing_holding:
                new_qty = existing_holding['quantity'] + quantity
                new_invested = round(existing_holding['total_invested'] + total_amount, 2)
                new_avg = round(new_invested / new_qty, 2)
                db.execute("""
                    UPDATE holdings 
                    SET quantity = ?, avg_buy_price = ?, total_invested = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_qty, new_avg, new_invested, existing_holding['id']))
            else:
                db.execute("""
                    INSERT INTO holdings (user_id, stock_symbol, quantity, avg_buy_price, total_invested)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, symbol, quantity, execution_price, total_amount))

            # Record order
            db.execute("""
                INSERT INTO orders (order_code, user_id, stock_symbol, order_type, action, quantity, price, target_price, total_amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED')
            """, (order_code, user_id, symbol, order_type, action, quantity, execution_price, target_price, total_amount))

            # Ledger
            db.execute("INSERT INTO transactions (user_id, order_code, type, amount, balance_after, note) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, order_code, 'BUY_EXECUTE', total_amount, new_balance, f"Bought {quantity} {symbol} at ₹{execution_price:,.2f}"))

            # Notification
            db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                       (user_id, f"Order Executed: BUY {symbol}", f"{quantity} shares of {symbol} bought at ₹{execution_price:,.2f}", "success"))
            
            db.commit()
            db.close()
            return jsonify({
                'success': True,
                'message': f"Order placed successfully! {quantity} shares of {symbol} bought at ₹{execution_price:,.2f}",
                'order_code': order_code,
                'new_balance': new_balance
            })

        else: # LIMIT BUY
            # Held in OPEN status with virtual balance escrowed
            db.execute("""
                INSERT INTO orders (order_code, user_id, stock_symbol, order_type, action, quantity, price, target_price, total_amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (order_code, user_id, symbol, order_type, action, quantity, execution_price, target_price, total_amount))

            db.execute("INSERT INTO transactions (user_id, order_code, type, amount, balance_after, note) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, order_code, 'BUY_ESCROW', total_amount, new_balance, f"Limit Buy order placed for {quantity} {symbol} @ ₹{target_price:,.2f}"))

            db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                       (user_id, f"Limit Order Placed: BUY {symbol}", f"Limit Buy for {quantity} {symbol} placed at target ₹{target_price:,.2f}", "info"))

            db.commit()
            db.close()
            return jsonify({
                'success': True,
                'message': f"Limit BUY order placed! Will execute when {symbol} reaches ₹{target_price:,.2f}",
                'order_code': order_code,
                'new_balance': new_balance
            })

    elif action == 'SELL':
        holding = db.execute("SELECT * FROM holdings WHERE user_id = ? AND stock_symbol = ?", (user_id, symbol)).fetchone()
        if not holding or holding['quantity'] < quantity:
            avail = holding['quantity'] if holding else 0
            db.close()
            return jsonify({
                'success': False,
                'message': f"Cannot sell more shares than you hold! Owned: {avail}, Attempted: {quantity}"
            }), 400

        if order_type == 'MARKET':
            sell_proceeds = total_amount
            new_balance = round(user['virtual_balance'] + sell_proceeds, 2)
            db.execute("UPDATE users SET virtual_balance = ? WHERE id = ?", (new_balance, user_id))

            # Update holdings
            new_qty = holding['quantity'] - quantity
            if new_qty <= 0:
                db.execute("DELETE FROM holdings WHERE id = ?", (holding['id'],))
            else:
                new_invested = round(holding['total_invested'] - (holding['avg_buy_price'] * quantity), 2)
                db.execute("""
                    UPDATE holdings 
                    SET quantity = ?, total_invested = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_qty, new_invested, holding['id']))

            # Record order
            db.execute("""
                INSERT INTO orders (order_code, user_id, stock_symbol, order_type, action, quantity, price, target_price, total_amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED')
            """, (order_code, user_id, symbol, order_type, action, quantity, execution_price, target_price, total_amount))

            # Ledger
            db.execute("INSERT INTO transactions (user_id, order_code, type, amount, balance_after, note) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, order_code, 'SELL_PROCEEDS', sell_proceeds, new_balance, f"Sold {quantity} {symbol} at ₹{execution_price:,.2f}"))

            # Notification
            db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                       (user_id, f"Order Executed: SELL {symbol}", f"{quantity} shares of {symbol} sold at ₹{execution_price:,.2f}", "success"))

            db.commit()
            db.close()
            return jsonify({
                'success': True,
                'message': f"Order placed successfully! {quantity} shares of {symbol} sold at ₹{execution_price:,.2f}",
                'order_code': order_code,
                'new_balance': new_balance
            })

        else: # LIMIT SELL
            db.execute("""
                INSERT INTO orders (order_code, user_id, stock_symbol, order_type, action, quantity, price, target_price, total_amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (order_code, user_id, symbol, order_type, action, quantity, execution_price, target_price, total_amount))

            db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                       (user_id, f"Limit Order Placed: SELL {symbol}", f"Limit Sell for {quantity} {symbol} placed at target ₹{target_price:,.2f}", "info"))

            db.commit()
            db.close()
            return jsonify({
                'success': True,
                'message': f"Limit SELL order placed! Will execute when {symbol} reaches ₹{target_price:,.2f}",
                'order_code': order_code,
                'new_balance': user['virtual_balance']
            })

    db.close()
    return jsonify({'success': False, 'message': 'Unknown action'}), 400

@app.route('/api/order/cancel/<int:order_id>', methods=['POST'])
@login_required
def api_cancel_order(order_id):
    user_id = session['user_id']
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id)).fetchone()
    
    if not order:
        db.close()
        return jsonify({'success': False, 'message': 'Order not found.'}), 404
        
    if order['status'] != 'OPEN':
        db.close()
        return jsonify({'success': False, 'message': 'Only pending OPEN orders can be cancelled.'}), 400

    # If it was a BUY order, refund the escrowed cash
    if order['action'] == 'BUY':
        refund = order['total_amount']
        db.execute("UPDATE users SET virtual_balance = virtual_balance + ? WHERE id = ?", (refund, user_id))
        user = db.execute("SELECT virtual_balance FROM users WHERE id = ?", (user_id,)).fetchone()
        db.execute("INSERT INTO transactions (user_id, order_code, type, amount, balance_after, note) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, order['order_code'], 'REFUND_CANCEL', refund, user['virtual_balance'], f"Refund for cancelled order {order['order_code']}"))

    db.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
    db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
               (user_id, "Order Cancelled", f"Order {order['order_code']} ({order['stock_symbol']}) was cancelled.", "info"))

    db.commit()
    db.close()
    return jsonify({'success': True, 'message': f"Order {order['order_code']} cancelled successfully."})

@app.route('/api/watchlist/toggle', methods=['POST'])
@login_required
def api_toggle_watchlist():
    data = request.get_json() or {}
    symbol = data.get('symbol', '').strip().upper()
    user_id = session['user_id']
    
    if not symbol:
        return jsonify({'success': False, 'message': 'Symbol required'}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM watchlist WHERE user_id = ? AND stock_symbol = ?", (user_id, symbol)).fetchone()
    
    if existing:
        db.execute("DELETE FROM watchlist WHERE id = ?", (existing['id'],))
        is_in = False
        msg = f"{symbol} removed from watchlist."
    else:
        db.execute("INSERT INTO watchlist (user_id, stock_symbol) VALUES (?, ?)", (user_id, symbol))
        is_in = True
        msg = f"{symbol} added to watchlist."
        db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                   (user_id, "Watchlist Updated", msg, "info"))

    db.commit()
    db.close()
    return jsonify({'success': True, 'is_in_watchlist': is_in, 'message': msg})

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def api_mark_notifications_read():
    user_id = session['user_id']
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/profile/reset-balance', methods=['POST'])
@login_required
def api_reset_balance():
    user_id = session['user_id']
    db = get_db()
    # Reset balance to ₹10,00,000 and clear holdings
    db.execute("UPDATE users SET virtual_balance = ? WHERE id = ?", (DEFAULT_VIRTUAL_BALANCE, user_id))
    db.execute("DELETE FROM holdings WHERE user_id = ?", (user_id,))
    db.execute("UPDATE orders SET status = 'CANCELLED' WHERE user_id = ? AND status = 'OPEN'", (user_id,))
    
    db.execute("INSERT INTO transactions (user_id, order_code, type, amount, balance_after, note) VALUES (?, ?, ?, ?, ?, ?)",
               (user_id, "TC-RESET", 'PORTFOLIO_RESET', DEFAULT_VIRTUAL_BALANCE, DEFAULT_VIRTUAL_BALANCE, "Simulation portfolio reset to ₹10 Lakh"))
    
    db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
               (user_id, "Portfolio Reset", "Virtual trading balance restored to ₹10,00,000. All holdings cleared.", "warning"))
    
    db.commit()
    db.close()
    flash("Portfolio reset successfully! Your paper-trading balance is now ₹10,00,000.", "success")
    return jsonify({'success': True, 'message': 'Balance reset to ₹10,00,000.'})

@app.route('/admin/stock/update', methods=['POST'])
@admin_required
def admin_update_stock():
    symbol = request.form.get('symbol', '').upper()
    try:
        new_price = float(request.form.get('price', 0))
    except (ValueError, TypeError):
        flash("Invalid price value.", "danger")
        return redirect(url_for('admin'))
        
    db = get_db()
    stock = db.execute("SELECT current_price FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
    if stock:
        old_price = stock['current_price']
        diff = new_price - old_price
        diff_pct = (diff / old_price) * 100.0 if old_price > 0 else 0
        db.execute("""
            UPDATE stocks 
            SET current_price = ?, change_amount = ?, change_pct = ?
            WHERE symbol = ?
        """, (new_price, round(diff, 2), round(diff_pct, 2), symbol))
        db.commit()
        flash(f"Updated {symbol} price to ₹{new_price:,.2f}.", "success")
    db.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    port = DEFAULT_PORT
    try:
        print(f"[TrendCore] Starting server on http://{APP_DOMAIN}:{port} (or http://{APP_DOMAIN})...")
        app.run(host='0.0.0.0', port=port, debug=False)
    except (PermissionError, OSError) as e:
        print(f"[TrendCore] Port {port} not bindable ({e}). Falling back to port {FALLBACK_PORT}...")
        app.run(host='0.0.0.0', port=FALLBACK_PORT, debug=False)
