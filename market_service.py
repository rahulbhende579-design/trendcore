import math
import random
import datetime
from models import get_db
from config import MARKET_INDICES

class MarketService:
    @staticmethod
    def get_indices():
        """Returns the major Indian benchmark indices with realistic values."""
        indices = []
        for idx in MARKET_INDICES:
            # Small realistic jitter
            jitter = round(random.uniform(-0.15, 0.15), 2)
            pct = round(idx["change_pct"] + jitter, 2)
            chg = round(idx["base_price"] * (pct / 100.0), 2)
            curr = round(idx["base_price"] + chg, 2)
            indices.append({
                "symbol": idx["symbol"],
                "name": idx["name"],
                "price": f"{curr:,.2f}",
                "raw_price": curr,
                "change": f"{'+' if chg >= 0 else ''}{chg:,.2f}",
                "change_pct": f"{'+' if pct >= 0 else ''}{pct:.2f}%",
                "is_positive": pct >= 0
            })
        return indices

    @staticmethod
    def get_ticker_items():
        """Returns items for the horizontally scrolling market ticker."""
        items = MarketService.get_indices()
        # Also append top 4 blue-chip stocks to ticker
        db = get_db()
        top_stocks = db.execute("SELECT symbol, name, current_price, change_pct FROM stocks LIMIT 6").fetchall()
        db.close()
        for s in top_stocks:
            is_pos = s['change_pct'] >= 0
            items.append({
                "symbol": s['symbol'],
                "name": s['symbol'],
                "price": f"₹{s['current_price']:,.2f}",
                "change": f"{'+' if is_pos else ''}{s['change_pct']:.2f}%",
                "is_positive": is_pos
            })
        return items

    @staticmethod
    def get_all_stocks(sector=None, query=None, exchange=None, sort='volume_desc', page=1, per_page=50, limit=None):
        """
        Fetches stocks with sector, exchange filters, search query, sorting, and pagination.
        Supports the full 5,700+ NSE & BSE instrument directory.
        """
        db = get_db()
        sql = "SELECT * FROM stocks WHERE 1=1"
        params = []

        if sector and sector.lower() != 'all':
            sql += " AND sector LIKE ?"
            params.append(f"%{sector}%")

        if exchange and exchange.lower() != 'all':
            if exchange.upper() == 'NSE':
                sql += " AND (exchange = 'NSE' OR exchange = 'NSE/BSE')"
            elif exchange.upper() == 'BSE':
                sql += " AND (exchange = 'BSE' OR exchange = 'NSE/BSE')"

        if query and query.strip():
            q_clean = query.strip()
            sql += " AND (symbol LIKE ? OR name LIKE ?)"
            params.append(f"%{q_clean}%")
            params.append(f"%{q_clean}%")

        # Sorting logic
        if sort == 'price_asc':
            order_clause = " ORDER BY current_price ASC"
        elif sort == 'price_desc':
            order_clause = " ORDER BY current_price DESC"
        elif sort == 'change_asc':
            order_clause = " ORDER BY change_pct ASC"
        elif sort == 'change_desc':
            order_clause = " ORDER BY change_pct DESC"
        elif sort == 'symbol_asc':
            order_clause = " ORDER BY symbol ASC"
        elif sort == 'symbol_desc':
            order_clause = " ORDER BY symbol DESC"
        else: # volume_desc or default
            order_clause = " ORDER BY volume DESC, ABS(change_pct) DESC"

        # Count total matching rows
        count_sql = "SELECT COUNT(*) FROM stocks WHERE 1=1"
        count_params = []
        if sector and sector.lower() != 'all':
            count_sql += " AND sector LIKE ?"
            count_params.append(f"%{sector}%")
        if exchange and exchange.lower() != 'all':
            if exchange.upper() == 'NSE':
                count_sql += " AND (exchange = 'NSE' OR exchange = 'NSE/BSE')"
            elif exchange.upper() == 'BSE':
                count_sql += " AND (exchange = 'BSE' OR exchange = 'NSE/BSE')"
        if query and query.strip():
            q_clean = query.strip()
            count_sql += " AND (symbol LIKE ? OR name LIKE ?)"
            count_params.append(f"%{q_clean}%")
            count_params.append(f"%{q_clean}%")

        total_count = db.execute(count_sql, count_params).fetchone()[0]

        if limit:
            sql += order_clause + f" LIMIT {int(limit)}"
        else:
            page = max(1, int(page or 1))
            per_page = max(10, min(100, int(per_page or 50)))
            offset = (page - 1) * per_page
            sql += order_clause + f" LIMIT {per_page} OFFSET {offset}"

        rows = db.execute(sql, params).fetchall()
        db.close()

        results = [dict(r) for r in rows]
        total_pages = max(1, math.ceil(total_count / (per_page if not limit else limit)))

        return {
            'stocks': results,
            'total_count': total_count,
            'page': page,
            'per_page': per_page if not limit else len(results),
            'total_pages': total_pages
        }

    @staticmethod
    def get_stock(symbol):
        """Fetches a single stock by symbol from the complete universe."""
        if not symbol:
            return None
        db = get_db()
        row = db.execute("SELECT * FROM stocks WHERE symbol = ?", (symbol.upper().strip(),)).fetchone()
        db.close()
        if row:
            return dict(row)
        return None

    @staticmethod
    def search_stocks(query, limit=12):
        """Global search across the entire 5,700+ stock universe by symbol or name."""
        if not query or len(query.strip()) == 0:
            return []
        db = get_db()
        q = f"%{query.strip()}%"
        exact_prefix = f"{query.strip()}%"
        rows = db.execute("""
            SELECT symbol, name, sector, exchange, current_price, change_amount, change_pct
            FROM stocks
            WHERE symbol LIKE ? OR name LIKE ?
            ORDER BY 
                CASE WHEN symbol = ? THEN 1
                     WHEN symbol LIKE ? THEN 2
                     WHEN name LIKE ? THEN 3
                     ELSE 4 END,
                volume DESC
            LIMIT ?
        """, (q, q, query.strip().upper(), exact_prefix, exact_prefix, limit)).fetchall()
        db.close()
        return [dict(r) for r in rows]

    @staticmethod
    def generate_chart_data(symbol, timeframe='1D'):
        """
        Generates realistic chart data series for a given stock and timeframe.
        Timeframes supported: 1D, 1W, 1M, 3M, 6M, 1Y, 5Y.
        """
        stock = MarketService.get_stock(symbol)
        base_price = stock['current_price'] if stock else 1000.0
        
        now = datetime.datetime.now()
        labels = []
        data = []
        volumes = []

        # Seed pseudo-random with symbol hash so the chart shape is consistent but realistic
        seed_val = sum(ord(c) for c in symbol) + (hash(timeframe) % 1000)
        rng = random.Random(seed_val)

        if timeframe == '1D':
            # Trading hours: 09:15 AM to 03:30 PM (every 5 minutes)
            start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
            points = 75
            current_val = base_price - (stock['change_amount'] if stock else 0)
            for i in range(points):
                t = start_time + datetime.timedelta(minutes=i * 5)
                labels.append(t.strftime("%I:%M %p"))
                # Random walk toward current_price
                step_noise = rng.uniform(-0.003, 0.003) * current_val
                drift = (base_price - current_val) / max(points - i, 1)
                current_val += step_noise + drift
                data.append(round(current_val, 2))
                volumes.append(int(rng.uniform(10000, 150000)))
            data[-1] = base_price  # Anchor last point to current price

        elif timeframe == '1W':
            # 5 days, 7 points per day
            points = 35
            start_day = now - datetime.timedelta(days=7)
            current_val = base_price * rng.uniform(0.96, 1.04)
            for i in range(points):
                dt = start_day + datetime.timedelta(hours=i * 4)
                labels.append(dt.strftime("%d %b %I%p"))
                current_val += rng.uniform(-0.008, 0.008) * current_val
                data.append(round(current_val, 2))
                volumes.append(int(rng.uniform(30000, 300000)))
            data[-1] = base_price

        elif timeframe == '1M':
            # 30 days, daily
            points = 30
            start_day = now - datetime.timedelta(days=30)
            current_val = base_price * rng.uniform(0.92, 1.08)
            for i in range(points):
                dt = start_day + datetime.timedelta(days=i)
                labels.append(dt.strftime("%d %b"))
                current_val += rng.uniform(-0.015, 0.015) * current_val
                data.append(round(current_val, 2))
                volumes.append(int(rng.uniform(50000, 500000)))
            data[-1] = base_price

        elif timeframe == '3M':
            points = 45
            start_day = now - datetime.timedelta(days=90)
            current_val = base_price * rng.uniform(0.88, 1.12)
            for i in range(points):
                dt = start_day + datetime.timedelta(days=i * 2)
                labels.append(dt.strftime("%d %b"))
                current_val += rng.uniform(-0.02, 0.02) * current_val
                data.append(round(current_val, 2))
                volumes.append(int(rng.uniform(100000, 800000)))
            data[-1] = base_price

        elif timeframe == '6M':
            points = 60
            start_day = now - datetime.timedelta(days=180)
            current_val = base_price * rng.uniform(0.82, 1.18)
            for i in range(points):
                dt = start_day + datetime.timedelta(days=i * 3)
                labels.append(dt.strftime("%d %b %Y"))
                current_val += rng.uniform(-0.025, 0.025) * current_val
                data.append(round(current_val, 2))
                volumes.append(int(rng.uniform(120000, 900000)))
            data[-1] = base_price

        elif timeframe == '1Y':
            points = 52  # Weekly
            start_day = now - datetime.timedelta(days=365)
            current_val = base_price * rng.uniform(0.75, 1.25)
            for i in range(points):
                dt = start_day + datetime.timedelta(weeks=i)
                labels.append(dt.strftime("%b %Y"))
                current_val += rng.uniform(-0.03, 0.03) * current_val
                data.append(round(current_val, 2))
                volumes.append(int(rng.uniform(200000, 1500000)))
            data[-1] = base_price

        elif timeframe == '5Y':
            points = 60  # Monthly for 5 years
            start_day = now - datetime.timedelta(days=1825)
            current_val = base_price * rng.uniform(0.40, 0.70)  # General upward Indian stock market trend over 5y
            for i in range(points):
                dt = start_day + datetime.timedelta(days=i * 30)
                labels.append(dt.strftime("%b %Y"))
                current_val += rng.uniform(-0.035, 0.045) * current_val
                data.append(round(current_val, 2))
                volumes.append(int(rng.uniform(500000, 3000000)))
            data[-1] = base_price

        else:
            labels = ["9:15", "11:00", "13:00", "15:30"]
            data = [base_price * 0.99, base_price * 1.01, base_price * 0.995, base_price]
            volumes = [50000, 80000, 60000, 120000]

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "labels": labels,
            "prices": data,
            "volumes": volumes,
            "high": max(data),
            "low": min(data),
            "open": data[0],
            "close": data[-1],
            "change": round(data[-1] - data[0], 2),
            "change_pct": round(((data[-1] - data[0]) / data[0]) * 100.0, 2)
        }

    @staticmethod
    def check_and_execute_limit_orders():
        """
        Simulates filling open limit orders when stock prices match criteria.
        Called periodically or upon market view.
        """
        db = get_db()
        open_orders = db.execute("SELECT * FROM orders WHERE status = 'OPEN'").fetchall()
        for ord_row in open_orders:
            stock = db.execute("SELECT current_price FROM stocks WHERE symbol = ?", (ord_row['stock_symbol'],)).fetchone()
            if not stock:
                continue
            curr_price = stock['current_price']
            action = ord_row['action']
            target = ord_row['target_price']
            filled = False

            if action == 'BUY' and curr_price <= target:
                filled = True
            elif action == 'SELL' and curr_price >= target:
                filled = True

            if filled:
                # Execute order
                user_id = ord_row['user_id']
                sym = ord_row['stock_symbol']
                qty = ord_row['quantity']
                tot = qty * curr_price

                if action == 'BUY':
                    # Add to holdings
                    hold = db.execute("SELECT * FROM holdings WHERE user_id = ? AND stock_symbol = ?", (user_id, sym)).fetchone()
                    if hold:
                        new_qty = hold['quantity'] + qty
                        new_invested = hold['total_invested'] + tot
                        new_avg = round(new_invested / new_qty, 2)
                        db.execute("UPDATE holdings SET quantity = ?, avg_buy_price = ?, total_invested = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                   (new_qty, new_avg, new_invested, hold['id']))
                    else:
                        db.execute("INSERT INTO holdings (user_id, stock_symbol, quantity, avg_buy_price, total_invested) VALUES (?, ?, ?, ?, ?)",
                                   (user_id, sym, qty, curr_price, tot))
                elif action == 'SELL':
                    # Credit virtual balance
                    db.execute("UPDATE users SET virtual_balance = virtual_balance + ? WHERE id = ?", (tot, user_id))
                    # Deduct holdings
                    hold = db.execute("SELECT * FROM holdings WHERE user_id = ? AND stock_symbol = ?", (user_id, sym)).fetchone()
                    if hold:
                        new_qty = hold['quantity'] - qty
                        if new_qty <= 0:
                            db.execute("DELETE FROM holdings WHERE id = ?", (hold['id'],))
                        else:
                            new_invested = hold['total_invested'] - (hold['avg_buy_price'] * qty)
                            db.execute("UPDATE holdings SET quantity = ?, total_invested = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                       (new_qty, new_invested, hold['id']))

                db.execute("UPDATE orders SET status = 'COMPLETED', price = ? WHERE id = ?", (curr_price, ord_row['id']))
                db.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                           (user_id, f"Limit Order Filled: {sym}", f"{qty} shares of {sym} {action.lower()} order executed at ₹{curr_price:,.2f}", "success"))
        db.commit()
        db.close()

    @staticmethod
    def sync_stocks():
        """
        Synchronizes stock instruments from official NSE & BSE lists.
        Downloads the latest instrument masters and updates the database.
        """
        import os, csv, json, urllib.request

        base_dir = os.path.dirname(os.path.abspath(__file__))
        nse_csv_path = os.path.join(base_dir, 'nse_equities_master.csv')
        bse_json_path = os.path.join(base_dir, 'bse_equities_master.json')

        # Download latest NSE list if possible
        try:
            req = urllib.request.Request('https://archives.nseindia.com/content/equities/EQUITY_L.csv', headers={'User-Agent': 'Mozilla/5.0'})
            res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
            with open(nse_csv_path, 'w', encoding='utf-8') as f:
                f.write(res)
        except Exception as e:
            print(f"[Sync] NSE download skipped ({e}), using cached master.")

        nse_dict = {}
        if os.path.exists(nse_csv_path):
            with open(nse_csv_path, encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    sym = row.get('SYMBOL', '').strip().upper()
                    if sym:
                        nse_dict[sym] = {
                            'name': row.get('NAME OF COMPANY', '').strip(),
                            'series': row.get(' SERIES', 'EQ').strip(),
                            'isin': row.get(' ISIN NUMBER', '').strip()
                        }

        bse_dict = {}
        if os.path.exists(bse_json_path):
            with open(bse_json_path, encoding='utf-8') as f:
                for item in json.load(f):
                    sym = str(item.get('symbol', '')).strip().upper()
                    if sym:
                        bse_dict[sym] = {
                            'name': item.get('name', sym).strip(),
                            'token': item.get('token', '').strip()
                        }

        def guess_sector(name, symbol):
            n = (name + ' ' + symbol).upper()
            if any(k in n for k in ['BANK', 'FINANCE', 'FINANCIAL', 'CAPITAL', 'INVEST', 'HOLDING', 'INSURANCE', 'SECURITIES', 'CREDIT', 'MUTUAL']):
                return 'Banking & Finance'
            if any(k in n for k in ['TECH', 'INFOSYS', 'SOFTWARE', 'SYSTEMS', 'DIGITAL', 'INFO', 'TELECOM', 'COMMUNICATION', 'DATA', 'NETWORKS']):
                return 'Information Technology'
            if any(k in n for k in ['PHARMA', 'HEALTH', 'DRUG', 'LAB', 'BIO', 'HOSPITAL', 'MEDIC', 'REMEDIES', 'CHEM']):
                return 'Healthcare & Pharma'
            if any(k in n for k in ['MOTORS', 'AUTO', 'AUTOMOBILE', 'TYRE', 'WHEEL', 'VEHICLE']):
                return 'Automobile'
            if any(k in n for k in ['FOOD', 'CONSUMER', 'BEVERAGE', 'FMCG', 'DAIRY', 'SUGAR', 'AGRO', 'TEA', 'BREWERIES', 'RETAIL', 'TOBACCO', 'ITC']):
                return 'FMCG'
            if any(k in n for k in ['STEEL', 'POWER', 'ENERGY', 'OIL', 'GAS', 'PETRO', 'MINERAL', 'METALS', 'COAL', 'CEMENT', 'INFRA', 'ENGINEERING', 'CONSTRUCTION', 'PROJECT']):
                return 'Infrastructure & Engineering'
            return 'Other Equities'

        all_symbols = sorted(set(list(nse_dict.keys()) + list(bse_dict.keys())))
        db = get_db()
        existing = {r['symbol']: dict(r) for r in db.execute("SELECT * FROM stocks").fetchall()}
        
        batch = []
        for sym in all_symbols:
            in_nse = sym in nse_dict
            in_bse = sym in bse_dict
            exch = 'NSE/BSE' if (in_nse and in_bse) else ('NSE' if in_nse else 'BSE')
            
            if sym in existing:
                continue
                
            rng = random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(sym)))
            name = nse_dict.get(sym, {}).get('name') or bse_dict.get(sym, {}).get('name') or sym
            if name == sym:
                name = sym.replace('-', ' ').title() + ' Ltd.'
            sector = guess_sector(name, sym)
            
            tier = rng.random()
            if tier < 0.45:
                price = round(rng.uniform(15.0, 180.0), 2)
            elif tier < 0.85:
                price = round(rng.uniform(180.0, 950.0), 2)
            else:
                price = round(rng.uniform(950.0, 3800.0), 2)
                
            change_pct = round(rng.uniform(-4.5, 4.5), 2)
            change_amount = round(price * (change_pct / 100.0), 2)
            day_low = round(price * rng.uniform(0.97, 0.995), 2)
            day_high = round(price * rng.uniform(1.005, 1.03), 2)
            low_52w = round(price * rng.uniform(0.60, 0.85), 2)
            high_52w = round(price * rng.uniform(1.15, 1.65), 2)
            volume = int(rng.uniform(25000, 2500000))
            pe_ratio = round(rng.uniform(12.0, 48.0), 1)
            
            mcap_val = round((price * volume * rng.uniform(15, 80)) / 10000000, 1)
            market_cap = f'₹{mcap_val/100000:.2f} Lakh Cr' if mcap_val >= 100000 else f'₹{mcap_val:,.1f} Cr'
            description = f'{name} is an Indian equity listed on {exch} in the {sector} sector.'
            isin = nse_dict.get(sym, {}).get('isin', '')
            series = nse_dict.get(sym, {}).get('series', 'EQ')
            
            batch.append((
                sym, name, sector, price, change_amount, change_pct,
                day_high, day_low, high_52w, low_52w, volume, pe_ratio,
                market_cap, description, exch, isin, series
            ))
            
        if batch:
            db.executemany("""
                INSERT OR IGNORE INTO stocks (
                    symbol, name, sector, current_price, change_amount, change_pct,
                    day_high, day_low, high_52w, low_52w, volume, pe_ratio,
                    market_cap, description, exchange, isin, series
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            db.commit()
            print(f"[Sync] Synchronized {len(batch)} new stocks into database.")
        db.close()
        return len(batch)
