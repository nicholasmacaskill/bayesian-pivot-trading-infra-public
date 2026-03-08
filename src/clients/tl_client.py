import requests
import os
import logging
from datetime import datetime, timezone, date, timedelta
from dotenv import load_dotenv

load_dotenv('.env.local')
load_dotenv()

logger = logging.getLogger(__name__)


class TradeLockerHelper:
    """Helper to manage a single TradeLocker account session using User-provided logic."""
    def __init__(self, email, password, server, base_url):
        self.email = email
        self.password = password
        self.server_id = server
        self.base_url = base_url.rstrip('/')
        self.access_token = None
        self.account_id = None
        self.acc_num = None # New Field for 'accNum' header
        # Rate limit protection (TTL Cache)
        self._history_cache = None
        self._history_last_fetch = 0
        
    def resolve_symbol(self, instrument_id):
        """Maps internal IDs to human-readable symbols."""
        mapping = {
            "206": "BTC/USD",
            "207": "ETH/USD",
            "214": "ETH/USD",
            "208": "SOL/USD",
            "221": "SOL/USD",
            "1": "EUR/USD",
            "2": "GBP/USD"
        }
        symbol = mapping.get(str(instrument_id))
        if not symbol:
            logger.warning(f"Unknown instrument ID: {instrument_id}")
            return str(instrument_id)
        return symbol

    def _get_headers(self, auth=False):
        """Standard stealth headers combined with user-required logic."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
        }
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        # Include accNum if available (Required by some servers e.g Upcomers)
        if self.acc_num:
            headers["accNum"] = str(self.acc_num)
            
        return headers

    def _make_request(self, method, url, auth=True, **kwargs):
        """Wrapper to handle automatic re-login on 401 Unauthorized."""
        headers = self._get_headers(auth=auth)
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        
        resp = requests.request(method, url, headers=headers, **kwargs)
        
        # Auto-retry once on 401 if we were trying to be authenticated
        if resp.status_code == 401 and auth:
            logger.warning(f"⚠️ JWT Expired for {self.email}. Attempting re-login...")
            if self.login():
                headers = self._get_headers(auth=True) # Refresh headers with new token
                resp = requests.request(method, url, headers=headers, **kwargs)
        
        return resp

    def login(self):
        """User-provided login logic with corrected /backend-api prefix."""
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/token"
            payload = {
                "email": self.email.strip(), # Fix for 400 errors
                "password": self.password,
                "server": self.server_id
            }
            
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=10)
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                self.access_token = data.get('accessToken')
                # CRITICAL: Fetch account details to avoid 404s
                return self.get_account_details()
            else:
                logger.error(f"Login Failed: {resp.status_code} - {resp.text[:50]}...")
                return False
        except requests.exceptions.Timeout:
            logger.warning("TL Login Timeout: Service might be down.")
            return False
        except Exception as e:
            logger.warning(f"TL Connection Error: {e}")
            return False

    def get_account_details(self):
        """User-provided account discovery logic via corrected /backend-api."""
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/all-accounts"
            resp = self._make_request("GET", url)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    accounts = data.get('accounts', [])
                except Exception:
                    # Silent failure during known downtime if it's HTML
                    if "<html" not in resp.text.lower():
                        logger.error(f"Invalid JSON from account details: {resp.text[:50]}...")
                    return False

                if accounts:
                    # Capture both ID and AccNum
                    self.account_id = accounts[0]['id']
                    self.acc_num = accounts[0].get('accNum')
                    return True
            logger.error(f"Failed to fetch account details: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Account details exception: {e}")
            return False

    def get_equity(self):
        """Fetch total equity from ALL accounts associated with this login."""
        if not self.access_token and not self.login(): return 0.0
        
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/all-accounts"
            resp = self._make_request("GET", url)
            if resp.status_code == 200:
                accounts = resp.json().get('accounts', [])
                total_equity = 0.0
                for acc in accounts:
                    equity = float(acc.get('projectedEquity') or acc.get('accountBalance', 0.0))
                    logger.info(f"   found account {acc['id']}: ${equity:,.2f}")
                    total_equity += equity
                return total_equity
            return 0.0
        except Exception:
            return 0.0

    def get_open_positions(self):
        """Fetches currently active positions."""
        if not self.access_token and not self.login(): return []
        
        try:
            url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/positions"
            resp = self._make_request("GET", url)
            
            if resp.status_code == 200:
                data = resp.json()
                trades = []
                positions = data.get('d', {}).get('positions', [])
                if not positions and isinstance(data, list): positions = data
                
                for p in positions:
                    # Parse Active Position
                    if isinstance(p, list) and len(p) >= 10:
                        try:
                            # Upcomers List Format
                            trades.append({
                                'id': str(p[0]),
                                'symbol': self.resolve_symbol(p[1]), 
                                'side': 'BUY' if str(p[3]).lower() == 'buy' else 'SELL',
                                'pnl': float(p[9] or 0.0),
                                'entry_time': str(p[8]),
                                'price': float(p[5] or 0.0),
                                'status': 'OPEN'
                            })
                        except Exception as e:
                            logger.error(f"❌ PARSE ERROR: {e} | DATA: {p}")
                    else:
                        trades.append({
                            'id': p.get('id'),
                            'symbol': self.resolve_symbol(p.get('instrumentId')),
                            'side': 'BUY' if p.get('side') == 'buy' else 'SELL',
                            'pnl': float(p.get('floatingProfit') or p.get('profit') or 0.0), 
                            'entry_time': p.get('openDate') or p.get('created'),
                            'price': float(p.get('avgOpenPrice') or p.get('openPrice') or 0.0),
                            'status': 'OPEN'
                        })
                return trades
            else:
                 return []
        except Exception as e:
            logger.error(f"Open Positions Fetch Error: {e}")
            return []

    def get_recent_history(self, hours=24):
        """
        Fetches filled orders from the ordersHistory endpoint.
        Pairs BUY/SELL orders by position_id to calculate per-trade PnL.
        """
        if not self.access_token and not self.login(): return []
        
        # 1. Check TTL Cache (Protect against 429)
        import time
        now = time.time()
        if self._history_cache is not None and (now - self._history_last_fetch) < 300: # 5 minute cache
            # Filter cached trades by hours requested
            from datetime import datetime, timezone, timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            return [t for t in self._history_cache if t['close_time'] > cutoff]

        try:
            # Correct endpoint for Upcomers/TradeLocker
            url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/ordersHistory"
            resp = self._make_request("GET", url, params={'limit': 500}, timeout=15)
            
            if resp.status_code != 200:
                # If we get a 429 or 503, serve from stale cache if available
                if resp.status_code in [429, 503] and self._history_cache is not None:
                    logger.warning(f"TradeLocker {resp.status_code}. Serving STALE cache.")
                    return self._history_cache
                logger.error(f"ordersHistory failed: {resp.status_code} - {resp.text[:200]}")
                return []

            try:
                data = resp.json()
            except Exception:
                logger.error(f"Failed to decode history JSON: {resp.text[:100]}")
                return []
                
            raw_orders = data.get('d', {}).get('ordersHistory', [])

            from datetime import datetime, timezone, timedelta
            cutoff_ms = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000

            # Parse filled orders into normalized dicts
            # List format: [order_id, instrument_id, acc_num, qty, side, type, status,
            #               fill_qty, fill_price, limit_price, ..., created_ms, filled_ms, ..., position_id, ...]
            filled = {}
            for o in raw_orders:
                if not isinstance(o, list) or len(o) < 17:
                    continue
                status = o[6]
                if status != 'Filled':
                    continue
                filled_ms = int(o[14]) if o[14] else 0
                if filled_ms < cutoff_ms:
                    continue

                position_id = str(o[16]) if o[16] else None
                if not position_id:
                    continue

                side = str(o[4]).upper()  # 'buy' or 'sell'
                fill_price = float(o[8]) if o[8] else 0.0
                qty = float(o[3]) if o[3] else 0.0
                symbol = self.resolve_symbol(o[1])
                created_ms = int(o[13]) if o[13] else filled_ms

                if position_id not in filled:
                    filled[position_id] = {
                        'id': position_id,
                        'symbol': symbol,
                        'orders': []
                    }
                filled[position_id]['orders'].append({
                    'side': side,
                    'price': fill_price,
                    'qty': qty,
                    'time_ms': filled_ms,
                })

            # Build normalized trade list from position groups
            trades = []
            for pos_id, pos in filled.items():
                orders = pos['orders']
                buys  = [o for o in orders if o['side'] == 'BUY']
                sells = [o for o in orders if o['side'] == 'SELL']

                if not buys or not sells:
                    # Position still open, skip
                    continue

                avg_buy  = sum(o['price'] * o['qty'] for o in buys)  / sum(o['qty'] for o in buys)
                avg_sell = sum(o['price'] * o['qty'] for o in sells) / sum(o['qty'] for o in sells)
                total_qty = min(sum(o['qty'] for o in buys), sum(o['qty'] for o in sells))

                pnl = (avg_sell - avg_buy) * total_qty
                side = 'BUY'  # Net side (opened as a BUY, closed as a SELL)
                close_time_ms = max(o['time_ms'] for o in orders)
                close_time = datetime.fromtimestamp(close_time_ms / 1000, timezone.utc).isoformat()

                trades.append({
                    'id': pos_id,
                    'symbol': pos['symbol'],
                    'side': side,
                    'pnl': round(pnl, 2),
                    'close_time': close_time,
                    'price': round(avg_sell, 2),
                    'entry_price': round(avg_buy, 2),
                    'qty': total_qty,
                    'status': 'CLOSED',
                })

            logger.info(f"ordersHistory: {len(raw_orders)} raw orders → {len(trades)} closed trades")
            self._history_cache = trades
            self._history_last_fetch = time.time()
            return trades

        except Exception as e:
            logger.error(f"History Fetch Error: {e}")
            return []


    def get_todays_trades_count(self):
        """Simplified trade count for verification."""
        if not self.access_token and not self.login(): return 0
        return 0 # Placeholder for brevity in verification

class TradeLockerClient:
    """Wrapper that manages multiple TradeLocker accounts (A, B, etc.) and aggregates equity."""
    def __init__(self):
        self.helpers = []
        
        # Account A (Primary/Legacy)
        email_a = os.environ.get("TRADELOCKER_EMAIL_A") or os.environ.get("TRADELOCKER_EMAIL")
        pass_a = os.environ.get("TRADELOCKER_PASSWORD_A") or os.environ.get("TRADELOCKER_PASSWORD")
        server_a = os.environ.get("TRADELOCKER_SERVER_A") or os.environ.get("TRADELOCKER_SERVER")
        base_url_a = os.environ.get("TRADELOCKER_BASE_URL_A") or os.environ.get("TRADELOCKER_BASE_URL", "https://demo.tradelocker.com")
        
        if email_a and pass_a:
            self.helpers.append(TradeLockerHelper(email_a, pass_a, server_a, base_url_a))
            
        # Account B (Secondary)
        email_b = os.environ.get("TRADELOCKER_EMAIL_B")
        pass_b = os.environ.get("TRADELOCKER_PASSWORD_B")
        server_b = os.environ.get("TRADELOCKER_SERVER_B") or server_a # Fallback to Server A if not specified
        base_url_b = os.environ.get("TRADELOCKER_BASE_URL_B") or base_url_a # Fallback to Base URL A
        
        if email_b and pass_b:
            self.helpers.append(TradeLockerHelper(email_b, pass_b, server_b, base_url_b))

    def get_open_positions(self):
        """Aggregates open positions from all accounts."""
        all_trades = []
        for helper in self.helpers:
            trades = helper.get_open_positions()
            all_trades.extend(trades)
        return all_trades

    def get_total_equity(self):
        """Returns Total Equity across ALL UNIQUE accounts. Defaults to $100k if offline."""
        total_equity = 0.0
        seen_account_ids = set()
        
        for i, helper in enumerate(self.helpers):
            # We need to manually call login/fetch to get the account IDs
            if not helper.access_token:
                helper.login()
                
            try:
                url = f"{helper.base_url}/backend-api/auth/jwt/all-accounts"
                resp = helper._make_request("GET", url)
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        accounts = data.get('accounts', [])
                    except Exception:
                        if "<html" not in resp.text.lower():
                            logger.error(f"Invalid JSON from account check: {resp.text[:50]}...")
                        continue

                    for acc in accounts:
                        acc_id = acc['id']
                        equity = float(acc.get('projectedEquity') or acc.get('accountBalance', 0.0))
                        logger.info(f"   Account {acc_id}: ${equity:,.2f}")
                        total_equity += equity
                        seen_account_ids.add(acc_id)
                else:
                    if resp.status_code not in [500, 502, 503, 504]: # Don't spam during downtime
                        logger.error(f"Account {i+1} ({helper.email}) check failed: {resp.status_code}")
                    
            except Exception as e:
                # Silence expected connection errors
                err_str = str(e)
                if "Expecting value: line 1 column 1 (char 0)" in err_str:
                    pass # Handled by the try/except block above
                elif "503" not in err_str and "timed out" not in err_str.lower():
                    logger.error(f"Error checking account {i+1}: {e}")
        
        return total_equity

    def get_recent_history(self, hours=24):
        """Aggregates history from all accounts."""
        all_trades = []
        for helper in self.helpers:
            trades = helper.get_recent_history(hours)
            all_trades.extend(trades)
        return all_trades

    def get_daily_trades_count(self):
        """Sum of trades count from all accounts."""
        total_trades = 0
        for helper in self.helpers:
            total_trades += helper.get_todays_trades_count()
        return total_trades

    def get_trade_history(self, limit=5):
        return [] # Placeholder
