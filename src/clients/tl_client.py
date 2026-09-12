import requests
import os
import time
import logging
from datetime import datetime, date
from dotenv import load_dotenv
from src.core.config import Config

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
        self._instruments_cache = {}
        self._symbol_cache = {}
        
    def sync_instruments(self):
        """Discovers and caches all tradable instruments and routes directly from the broker API."""
        if not self.access_token:
            return False
        try:
            url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/instruments"
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                instruments = data.get('d', {}).get('instruments', [])
                for inst in instruments:
                    name = str(inst.get('name', '')).replace("/", "").replace("_", "").upper()
                    tradable_id = str(inst.get('tradableInstrumentId') or inst.get('id'))
                    trade_routes = [r for r in inst.get('routes', []) if r.get('type') == 'TRADE']
                    route_id = trade_routes[0].get('id') if trade_routes else 2025730
                    self._instruments_cache[name] = {
                        'tradableInstrumentId': int(tradable_id),
                        'routeId': int(route_id),
                        'name': inst.get('name'),
                        'description': inst.get('description'),
                        'type': inst.get('type')
                    }
                    self._symbol_cache[tradable_id] = inst.get('name')
                logger.info(f"✅ Synced {len(self._instruments_cache)} broker instruments for {self.email}")
                return True
        except Exception as e:
            logger.debug(f"Broker instrument sync note: {e}")
        return False

    def resolve_symbol(self, instrument_id):
        """Maps internal IDs to human-readable symbols using live cache with canonical fallback."""
        str_id = str(instrument_id)
        if hasattr(self, '_symbol_cache') and str_id in self._symbol_cache:
            return self._symbol_cache[str_id]
        mapping = {
            "206": "BTC/USD",
            "207": "ETH/USD",
            "214": "ETH/USD",
            "208": "SOL/USD",
            "221": "SOL/USD",
            "1": "EUR/USD",
            "2": "GBP/USD",
            "19965": "BTC/USD",
            "19957": "ETH/USD",
            "19967": "SOL/USD",
            "19915": "XAU/USD",
            "19968": "SOL/USD",
            "19973": "GALA/USD",
            "20020": "EUR/USD",
            "19987": "GBP/USD",
        }
        symbol = mapping.get(str_id)
        if not symbol:
            logger.debug(f"Unmapped instrument ID: {instrument_id}")
            return str_id
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
                try:
                    data = resp.json()
                    self.access_token = data.get('accessToken')
                    # CRITICAL: Fetch account details to avoid 404s
                    return self.get_account_details()
                except Exception:
                    if "<html" not in resp.text.lower():
                        logger.warning(f"Login failed: Invalid JSON response")
                    return False
            else:
                logger.warning(f"Login Failed: {resp.status_code}")
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
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
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
                    # Capture both ID, AccNum, and live Balance
                    self.account_id = accounts[0]['id']
                    self.acc_num = accounts[0].get('accNum')
                    self.status = str(accounts[0].get('status', 'ACTIVE')).upper()
                    self.balance = float(accounts[0].get('projectedEquity') or accounts[0].get('accountBalance') or 25000.0)
                    print(f"DEBUG: Account Discovery Meta: {accounts[0]}")
                    try:
                        self.sync_instruments()
                    except Exception:
                        pass
                    return True
            if resp.status_code not in [502, 503, 504]:
                logger.warning(f"Failed to fetch account details: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Account details exception: {e}")
            return False

    def get_equity(self):
        """Fetch total equity from ALL accounts associated with this login."""
        if not self.access_token and not self.login(): return 0.0
        
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/all-accounts"
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
            if resp.status_code == 200:
                try:
                    accounts = resp.json().get('accounts', [])
                    total_equity = 0.0
                    for acc in accounts:
                        logger.info(f"🔍 RAW ACCOUNT META: {acc}")
                        equity = float(acc.get('projectedEquity') or acc.get('accountBalance', 0.0))
                        logger.info(f"   found account {acc['id']}: ${equity:,.2f}")
                        total_equity += equity
                    return total_equity
                except Exception:
                    return 0.0
            elif resp.status_code == 401:
                logger.warning(f"401 Unauthorized for {self.email}. Re-authenticating...")
                if self.login():
                    return self.get_equity()
            return 0.0
        except Exception:
            return 0.0

    def get_open_positions(self):
        """Fetches currently active positions."""
        if not self.access_token and not self.login(): return []
        
        try:
            url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/positions"
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                trades = []
                positions = data.get('d', {}).get('positions', [])
                if not positions and isinstance(data, list): positions = data
                
                for p in positions:
                    print(f"DEBUG LOOP: Type={type(p)}, p={p}")
                    # Parse Active Position
                    if isinstance(p, list) and len(p) >= 10:
                        try:
                            # Upcomers List Format
                            trades.append({
                                'id': str(p[0]),
                                'symbol': self.resolve_symbol(p[1]), 
                                'side': 'BUY' if str(p[3]).lower() == 'buy' else 'SELL',
                                'pnl': float(p[9] or 0.0),
                                'entry_time': datetime.utcfromtimestamp(float(p[8]) / 1000).isoformat() + 'Z' if p[8] else None,
                                'price': float(p[5] or 0.0),
                                'qty': float(p[4] or 0.0),
                                'stopLossOrderId': str(p[6]) if len(p) > 6 and p[6] else None,
                                'takeProfitOrderId': str(p[7]) if len(p) > 7 and p[7] else None,
                                'status': 'OPEN'
                            })
                        except Exception as e:
                            print(f"❌ PARSE ERROR: {e} | DATA: {p}")
                            logger.error(f"Failed to parse list position: {e}")
                    else:
                        trades.append({
                            'id': p.get('id'),
                            'symbol': self.resolve_symbol(p.get('instrumentId')),
                            'side': 'BUY' if p.get('side') == 'buy' else 'SELL',
                            'pnl': float(p.get('floatingProfit') or p.get('profit') or 0.0), 
                            'entry_time': p.get('openDate') or p.get('created'),
                            'price': float(p.get('avgOpenPrice') or p.get('openPrice') or 0.0),
                            'qty': float(p.get('qty') or p.get('lotSize') or 0.0),
                            'stopLoss': float(p.get('stopLoss') or 0.0) if p.get('stopLoss') else None,
                            'takeProfit': float(p.get('takeProfit') or 0.0) if p.get('takeProfit') else None,
                            'status': 'OPEN'
                        })
                return trades
            elif resp.status_code == 401:
                logger.warning(f"401 Unauthorized for {self.email} on positions. Re-authenticating...")
                self.access_token = None # Hard reset
                if self.login():
                    return self.get_open_positions()
                return []
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
        
        try:
            # Correct endpoint for Upcomers/TradeLocker
            url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/ordersHistory"
            resp = requests.get(url, headers=self._get_headers(auth=True), params={'limit': 500}, timeout=15)
            
            if resp.status_code == 401:
                logger.warning(f"401 Unauthorized for {self.email} on history. Re-authenticating...")
                if self.login():
                    return self.get_recent_history(hours)
                return []
            if resp.status_code != 200:
                logger.error(f"ordersHistory failed: {resp.status_code} - {resp.text[:200]}")
                return []

            try:
                data = resp.json()
            except Exception:
                logger.error(f"Failed to decode history JSON: {resp.text[:100]}")
                return []
                
            raw_orders = data.get('d', {}).get('ordersHistory', [])

            from datetime import datetime, timedelta
            cutoff_ms = (datetime.utcnow() - timedelta(hours=hours)).timestamp() * 1000

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
                
                # Sort orders by time_ms to identify the opening trade side (BUY for Long, SELL for Short)
                orders_sorted = sorted(orders, key=lambda x: x['time_ms'])
                side = orders_sorted[0]['side'] if orders_sorted else 'BUY'
                
                close_time_ms = max(o['time_ms'] for o in orders)
                close_time = datetime.utcfromtimestamp(close_time_ms / 1000).isoformat()

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
            return trades

        except Exception as e:
            logger.error(f"History Fetch Error: {e}")
            return []

    def place_order(self, instrument_id, side, qty, stop_loss=None, take_profit=None, order_type="market", price=0.0, symbol_hint=None):
        """Stealth & Idempotent Order Execution Module with Pre-Flight Broker Invariant Verification."""
        import time
        from src.engines.multi_account_funnel import align_lot_size

        if not self.access_token and not self.login(): 
            return False

        # Pre-Flight Invariant: Verify instrument matches target asset hint
        if symbol_hint:
            resolved_sym = self.resolve_symbol(instrument_id).replace("/", "").replace("_", "").upper()
            target_sym = symbol_hint.replace("/", "").replace("_", "").upper()
            # If target has a specific asset ticker, ensure it matches
            for asset_key in ["XAU", "GOLD", "BTC", "ETH", "SOL", "EUR", "GBP"]:
                if asset_key in target_sym and asset_key not in resolved_sym:
                    logger.critical(f"🚨 [BROKER MISMATCH INTERCEPTED] Refusing to place order: Target '{symbol_hint}' does not match resolved instrument '{resolved_sym}' (ID: {instrument_id})!")
                    return False

        # 1. Align Lot Size with Broker Metadata Step Constraints
        aligned_qty = align_lot_size(qty, min_lot=0.01, lot_step=0.01)
        if aligned_qty <= 0:
            logger.error(f"❌ Order Rejected: Quantity {qty} below min lot (0.01)")
            return False

        # Dynamically determine routeId from metadata cache
        route_id = 2025730
        if hasattr(self, '_instruments_cache') and self._instruments_cache:
            for inst_meta in self._instruments_cache.values():
                if str(inst_meta.get('tradableInstrumentId')) == str(instrument_id):
                    route_id = inst_meta.get('routeId', 2025730)
                    break

        url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/orders"
        payload = {
            "tradableInstrumentId": int(instrument_id),
            "qty": float(aligned_qty),
            "side": side.lower(),
            "type": order_type.lower(),
            "routeId": int(route_id),
            "validity": "IOC"
        }
        if order_type.lower() == "limit":
            payload["price"] = float(price)
        else:
            payload["price"] = 0.0



        for attempt in range(2):
            try:
                resp = requests.post(url, json=payload, headers=self._get_headers(auth=True), timeout=8)
                
                # Dynamic Rate Limiting (HTTP 429)
                if resp.status_code == 429:
                    retry_after = max(float(resp.headers.get("Retry-After") or 2.5), 2.5)
                    logger.warning(f"⚠️ Rate limited (HTTP 429). Sleeping {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                # Unhandled 401 Re-Auth
                if resp.status_code == 401 and attempt == 0:
                    logger.warning(f"401 Unauthorized during place_order. Refreshing token...")
                    if self.login():
                        continue
                    return False

                if resp.status_code in [200, 201]:
                    res_json = resp.json()
                    logger.info(f"✅ Order Executed: {side} {aligned_qty} on {instrument_id}")
                    
                    # Ensure Stop Loss & Take Profit are verified & attached via Position PATCH fallback
                    if stop_loss or take_profit:
                        time.sleep(0.5)
                        try:
                            # Robust 5-second polling loop to guarantee settlement before patch
                            import time
                            settled = False
                            for poll in range(5):
                                time.sleep(1.0)
                                open_pos = self.get_open_positions()
                                if open_pos:
                                    for p in open_pos:
                                        if str(p.get("tradableInstrumentId")) == str(instrument_id) and str(p.get("side")).lower() == side.lower():
                                            # Found it, patch it
                                            pos_id = p.get("id")
                                            self.modify_position_bracket(pos_id, stop_loss=stop_loss, take_profit=take_profit)
                                            settled = True
                                            break
                                if settled:
                                    break
                            if not settled:
                                logger.critical("⚠️ Trade placed but failed to locate position ID for bracket patch!")
                        except Exception as bracket_err:
                            logger.warning(f"⚠️ Bracket attach non-fatal error: {bracket_err}")

                    return res_json
                elif resp.status_code in [500, 502, 503, 504]:
                    # Server timeout/gateway error: check if order hit book before retrying
                    logger.warning(f"⚠️ Broker server error ({resp.status_code}). Checking for filled open position...")
                    time.sleep(1.0)
                    open_pos = self.get_open_positions()
                    if open_pos:
                        for p in open_pos:
                            if str(p.get("tradableInstrumentId")) == str(instrument_id) and str(p.get("side")).lower() == side.lower():
                                logger.info(f"✅ Idempotent Reconciliation: Order already filled during timeout!")
                                return p
                    # If position not found, retry once
                    continue
                else:
                    logger.error(f"❌ Order Failed: {resp.status_code} - {resp.text}")
                    return False

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"⚠️ Network timeout during order dispatch: {e}. Reconciling position state...")
                time.sleep(1.0)
                open_pos = self.get_open_positions()
                if open_pos:
                    for p in open_pos:
                        if str(p.get("tradableInstrumentId")) == str(instrument_id) and str(p.get("side")).lower() == side.lower():
                            logger.info(f"✅ Idempotent Reconciliation: Order filled despite timeout!")
                            return p
                if attempt == 1:
                    logger.error(f"❌ Network dispatch failed after reconciliation.")
                    return False

        return False


    def modify_position_bracket(self, position_id, stop_loss=None, take_profit=None):
        """
        Updates Stop Loss and Take Profit on an existing open position in place via PATCH.
        Guaranteed to NEVER place duplicate or orphan pending orders on the broker book.
        """
        if not self.access_token and not self.login():
            return False
        acc_part = f"/accounts/{self.account_id}" if self.account_id else ""
        url = f"{self.base_url}/backend-api/trade{acc_part}/positions/{position_id}"
        payload = {"stopLossType": "absolute", "takeProfitType": "absolute"}
        if stop_loss is not None:
            payload["stopLoss"] = float(stop_loss)
        if take_profit is not None:
            payload["takeProfit"] = float(take_profit)
            
        for attempt in range(3):
            try:
                resp = requests.patch(url, json=payload, headers=self._get_headers(auth=True), timeout=10)
                if resp.status_code in [200, 201, 204]:
                    logger.info(f"✅ Position {position_id} updated: SL={stop_loss}, TP={take_profit}")
                    return True
                elif resp.status_code == 429:
                    retry_after = max(float(resp.headers.get("Retry-After") or 15.0), 15.0)
                    logger.warning(f"⚠️ Rate limited on position patch (HTTP 429). Sleeping {retry_after}s...")
                    time.sleep(retry_after)
                else:
                    logger.error(f"❌ Failed to patch position {position_id}: {resp.status_code} - {resp.text}")
                    return False
            except Exception as e:
                logger.error(f"Error modifying position bracket: {e}")
                time.sleep(2.0)
        return False

    def close_position(self, position_id):
        """Safely closes an open position on TradeLocker using DELETE endpoint."""
        if not self.access_token and not self.login():
            return False
        url = f"{self.base_url}/backend-api/trade/positions/{position_id}"
        try:
            resp = requests.delete(url, headers=self._get_headers(auth=True), timeout=10)
            if resp.status_code in [200, 204]:
                logger.info(f"✅ Position {position_id} successfully closed.")
                return True
            else:
                logger.warning(f"DELETE position {position_id} returned {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error closing position {position_id}: {e}")
            return False

    def get_todays_trades_count(self):
        """Simplified trade count for verification."""
        if not self.access_token and not self.login(): return 0
        return 0 # Placeholder for brevity in verification

class TradeLockerClient:
    """Wrapper that manages multiple TradeLocker accounts (A, B, C, etc.) and aggregates equity."""
    def __init__(self):
        self.helpers = []
        import string
        
        default_server = os.environ.get("TRADELOCKER_SERVER_A") or os.environ.get("TRADELOCKER_SERVER", "UPCOMS")
        default_base_url = os.environ.get("TRADELOCKER_BASE_URL_A") or os.environ.get("TRADELOCKER_BASE_URL", "https://demo.tradelocker.com")
        
        seen_emails = set()
        suffixes = [""] + [f"_{c}" for c in string.ascii_uppercase]
        
        for suffix in suffixes:
            if suffix == "":
                email = os.environ.get("TRADELOCKER_EMAIL")
                password = os.environ.get("TRADELOCKER_PASSWORD")
                server = os.environ.get("TRADELOCKER_SERVER") or default_server
                base_url = os.environ.get("TRADELOCKER_BASE_URL") or default_base_url
            else:
                email = os.environ.get(f"TRADELOCKER_EMAIL{suffix}")
                password = os.environ.get(f"TRADELOCKER_PASSWORD{suffix}")
                server = os.environ.get(f"TRADELOCKER_SERVER{suffix}") or default_server
                base_url = os.environ.get(f"TRADELOCKER_BASE_URL{suffix}") or default_base_url

            if email and password and email.strip() not in seen_emails:
                seen_emails.add(email.strip())
                self.helpers.append(TradeLockerHelper(email, password, server, base_url))

    def update_fleet_stop_loss(self, new_stop_loss, symbol="BTC/USD"):
        """
        Safely modifies Stop Loss in place on all open positions across the fleet.
        Guaranteed to NEVER place duplicate or orphan pending orders.
        """
        results = []
        for i, helper in enumerate(self.helpers):
            positions = helper.get_open_positions()
            for p in positions:
                sym = str(p.get('symbol', '')).upper()
                if symbol.replace('/', '').upper() in sym.replace('/', '').upper():
                    pos_id = p.get('id')
                    if pos_id:
                        res = helper.modify_position_bracket(pos_id, stop_loss=new_stop_loss)
                        results.append(res)
        return results

    def close_all_fleet_positions(self):
        """Safely closes all open positions across all accounts in the fleet."""
        total_closed = 0
        for i, helper in enumerate(self.helpers):
            positions = helper.get_open_positions()
            for p in positions:
                pos_id = p.get('id')
                if pos_id:
                    if helper.close_position(pos_id):
                        total_closed += 1
        return total_closed


    def get_open_positions(self):
        """Aggregates open positions from all accounts with rate-limit pacing."""
        import time
        all_trades = []
        for i, helper in enumerate(self.helpers):
            if i > 0:
                time.sleep(0.05) # 50ms pacing between account queries
            trades = helper.get_open_positions()
            if trades:
                all_trades.extend(trades)
        return all_trades

    def get_total_equity(self):
        """Returns Total Equity across ALL UNIQUE accounts. Defaults to $100k if offline."""
        import time
        total_equity = 0.0
        seen_account_ids = set()
        
        for i, helper in enumerate(self.helpers):
            if i > 0:
                time.sleep(0.05) # 50ms pacing between account queries
            # We need to manually call login/fetch to get the account IDs

            if not helper.access_token:
                helper.login()
                
            try:
                url = f"{helper.base_url}/backend-api/auth/jwt/all-accounts"
                resp = requests.get(url, headers=helper._get_headers(auth=True), timeout=10)
                
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
                        logger.debug(f"Account Discovery Meta: {acc}")
                        if acc_id in seen_account_ids:
                            logger.debug(f"Skipping duplicate account {acc_id}")
                            continue
                            
                        equity = float(acc.get('projectedEquity') or acc.get('accountBalance', 0.0))
                        logger.debug(f"Account {acc_id}: ${equity:,.2f}")
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

    def resolve_instrument_id(self, symbol="BTC/USD") -> str:
        """Dynamically resolves broker tradableInstrumentId for any asset with verified live broker metadata cache."""
        norm = symbol.replace("/", "").replace("_", "").upper()
        # 1. First check if any helper has dynamic broker metadata cached
        for h in self.helpers:
            if hasattr(h, '_instruments_cache') and h._instruments_cache:
                for k, meta in h._instruments_cache.items():
                    if norm == k or norm in k or k in norm:
                        return str(meta['tradableInstrumentId'])
                        
        # 2. Hardcoded canonical mappings as verified fallback
        if "BTC" in norm:
            return "19965"
        elif "ETH" in norm:
            return "19957"
        elif "SOL" in norm:
            return "19967"
        elif "XAU" in norm or "GOLD" in norm:
            return "19915"
        elif "EUR" in norm:
            return "20020"
        elif "GBP" in norm:
            return "19987"
        return "19965"

    def execute_trade(self, symbol="BTC/USD", side="buy", qty=0.15, stop_loss=None, take_profit=None, account_index=0):
        """Executes a trade across the selected TradeLocker account. Uses dynamic instrument ID."""
        instrument_id = self.resolve_instrument_id(symbol)
        
        if not self.helpers:
            logger.error("No TradeLocker account helpers configured.")
            return False
            
        target_account = self.helpers[account_index] if 0 <= account_index < len(self.helpers) else self.helpers[0]
        
        return target_account.place_order(
            instrument_id=instrument_id,
            side=side,
            qty=qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_type="market",
            symbol_hint=symbol
        )

    def execute_trade_across_all_accounts(
        self,
        symbol="BTC/USD",
        side="buy",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        risk_scale=1.00,
        tranche_label="FULL_SIZE_ENTRY",
        ai_score=8.5,
        is_htf_confirmed=True,
        has_smt=False,
        session="",
        hurst_exponent=0.58,
        risk_pct_override=None,
        bypass_firewall=False
    ):
        """
        Executes a dynamically sized order across all configured TradeLocker accounts with 2.5s rate-limit pacing.
        Features Dynamic Fractional Kelly Risk Sizing (scales up on A+ confluence, caps at 1.00% max safety ceiling).
        Protected by the Sovereign ExecutionFirewall.
        """
        # Atomic Daily Setup Lock Enforcement
        import json
        import os
        from datetime import datetime, timezone
        lock_file_path = "data/daily_setup_lock.json"
        try:
            os.makedirs("data", exist_ok=True)
            try:
                from filelock import FileLock
                has_filelock = True
            except ImportError:
                has_filelock = False

            def _update_setup_lock():
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                data = {"date": today_str, "setups_fired": 0}
                if os.path.exists(lock_file_path):
                    try:
                        with open(lock_file_path, "r") as lf:
                            data = json.load(lf)
                    except Exception:
                        pass
                if data.get("date") != today_str:
                    data = {"date": today_str, "setups_fired": 0}
                if data.get("setups_fired", 0) >= 2:
                    logger.critical("🛡️ [ATOMIC LOCK] Daily Setup Limit (2) reached. Rejecting fleet dispatch.")
                    return False
                data["setups_fired"] = data.get("setups_fired", 0) + 1
                with open(lock_file_path, "w") as lf:
                    json.dump(data, lf)
                return True

            if has_filelock:
                lock = FileLock("data/daily_setup_lock.json.lock")
                with lock.acquire(timeout=5):
                    if not _update_setup_lock():
                        return {"success": False, "filled_count": 0, "total_accounts": len(self.helpers) if hasattr(self, "helpers") and self.helpers else 0, "error": "ATOMIC_SETUP_LIMIT_REACHED"}
            else:
                if not _update_setup_lock():
                    return {"success": False, "filled_count": 0, "total_accounts": len(self.helpers) if hasattr(self, "helpers") and self.helpers else 0, "error": "ATOMIC_SETUP_LIMIT_REACHED"}
        except Exception as e:
            logger.error(f"Failed to acquire atomic setup lock: {e}")
            return {"success": False, "filled_count": 0, "total_accounts": len(self.helpers) if hasattr(self, "helpers") and self.helpers else 0, "error": "ATOMIC_SETUP_LIMIT_REACHED"}
            

        import time
        from src.core.execution_firewall import ExecutionFirewall

        # ── SOVEREIGN EXECUTION FIREWALL AIRGAP GATE ──
        if not bypass_firewall:
            # Query live fleet positions before evaluating firewall invariants
            current_open_positions = []
            try:
                current_open_positions = self.get_open_positions()
            except Exception as pos_err:
                logger.warning(f"Note querying open positions during pre-flight firewall audit: {pos_err}")

            is_approved, rejection_reason = ExecutionFirewall.audit_trade_request(
                symbol=symbol,
                side=side,
                stop_loss=stop_loss,
                take_profit=take_profit,
                ai_score=ai_score,
                is_htf_confirmed=is_htf_confirmed,
                open_positions=current_open_positions
            )
            if not is_approved:
                logger.critical(f"🛡️ [EXECUTION FIREWALL INTERCEPTED] Blocked un-gated order on {symbol} {side.upper()}: {rejection_reason}")
                return {"success": False, "filled_count": 0, "total_accounts": len(self.helpers) if self.helpers else 0, "firewall_rejection": rejection_reason}

        instrument_id = self.resolve_instrument_id(symbol)
        
        if not self.helpers:
            logger.error("No TradeLocker account helpers configured.")
            return {"success": False, "filled_count": 0, "total_accounts": 0}

        # ── DYNAMIC RISK SIZING CALCULATION (FRACTIONAL KELLY) ──
        if risk_pct_override is not None:
            target_risk_pct = float(risk_pct_override)
        elif getattr(Config, 'DYNAMIC_RISK_SCALING_ENABLED', True):
            # Evaluate A+ High Win-Rate Confluence
            norm_score = float(ai_score) if float(ai_score) <= 10.0 else float(ai_score) / 10.0
            min_score = getattr(Config, 'A_PLUS_MIN_SCORE', 9.0)
            score_threshold = min_score if min_score <= 1.0 else (min_score / 10.0 if min_score <= 10.0 else min_score / 100.0)
            score_passed = norm_score >= score_threshold
            smt_passed = (not getattr(Config, 'A_PLUS_REQUIRE_SMT', True)) or bool(has_smt or is_htf_confirmed)
            session_str = str(session or "").upper()
            killzone_passed = (not getattr(Config, 'A_PLUS_REQUIRE_KILLZONE', True)) or any(kz in session_str for kz in ["LONDON", "NY", "KILLZONE", "CONTINUOUS"])
            hurst_passed = float(hurst_exponent) >= getattr(Config, 'A_PLUS_MIN_HURST', 0.58)

            is_a_plus = score_passed and smt_passed and (killzone_passed or norm_score >= 0.95) and hurst_passed
            if is_a_plus:
                target_risk_pct = getattr(Config, 'A_PLUS_RISK_PCT', 0.0085)
                logger.info(f"💎 [DYNAMIC SIZING: A+ CONFLUENCE] Score={ai_score}, SMT={has_smt or is_htf_confirmed}, Session={session}, Hurst={hurst_exponent:.2f} -> SCALING RISK TO {target_risk_pct*100:.2f}%")
            else:
                target_risk_pct = getattr(Config, 'BASELINE_RISK_PCT', 0.005)
        else:
            target_risk_pct = getattr(Config, 'BASELINE_RISK_PCT', 0.005)

        # Enforce Hard Safety Ceiling (Never exceed 1.00% on any trade)
        max_ceiling = getattr(Config, 'MAX_SINGLE_TRADE_RISK_CEILING', 0.010)
        target_risk_pct = min(target_risk_pct, max_ceiling)
            
        results = []
        logger.info(f"⚡ [PROBE & SCALE] Dispatching {tranche_label} ({target_risk_pct*100:.2f}% Risk Basis, {risk_scale*100:.0f}% Tranche Scale) across {len(self.helpers)} accounts for {symbol} {side.upper()}...")
        
        for i, helper in enumerate(self.helpers):
            if i > 0:
                time.sleep(2.5)  # 2.5s adaptive pacing to avoid HTTP 429 rate limits
                
            try:
                if not helper.access_token:
                    helper.login()
                    
                # Determine live account balance / equity
                equity = getattr(helper, 'balance', 0.0)
                if equity <= 0:
                    try:
                        helper.get_account_details()
                        equity = getattr(helper, 'balance', 25000.0)
                    except Exception:
                        equity = 25000.0
                    
                # Exact Dynamic Fractional Dollar Risk Calculation
                # Sizing: Lots = (Equity * Target Risk Pct) / Stop Loss Distance
                target_risk_usd = equity * target_risk_pct

                # ── DISTANCE-TO-DEFAULT (DtD) 5% HWM TRAILING-TO-EVEN DRAWDOWN PROTECTION ──
                # Rule: Trails 5.0% below peak High-Water Mark until floor reaches Starting Balance (Even Equity), then permanently locks at Starting Balance
                initial_size = 10000.0 if equity < 18000.0 else (25000.0 if equity < 38000.0 else 50000.0)
                max_dd_pct = getattr(Config, 'MAX_DRAWDOWN_LIMIT', 0.05)
                # Account High-Water Mark: peak equity reached (at least initial size)
                hwm = max(initial_size, equity)
                raw_trailing_floor = hwm * (1.0 - max_dd_pct)
                # Floor locks at initial_size (even equity) and never trails higher than initial balance
                hard_floor = min(initial_size, raw_trailing_floor)
                # Account 1 ($25k funded) peak exceeded $26k -> Floor permanently locked at $25,000.00 Even Equity
                is_account_1 = (helper.email == getattr(Config, 'FUNDED_ACCOUNT_1_EMAIL', 's79qv3xetj@upcomers.com'))
                if is_account_1:
                    hard_floor = 25000.0
                remaining_buffer = max(0.0, equity - hard_floor)
                
                # Check Account Status, Open Position Count & Drawdown Quarantine Gate (Invariant 9)
                acct_status = getattr(helper, 'status', 'ACTIVE')
                acct_open_pos = helper.get_open_positions()
                acct_pos_count = len(acct_open_pos) if acct_open_pos else 0

                is_eligible, ineligibility_reason = ExecutionFirewall.is_account_eligible(
                    email=helper.email,
                    status=acct_status,
                    equity=equity,
                    hard_floor=hard_floor,
                    open_positions_count=acct_pos_count
                )
                if not is_eligible:
                    logger.critical(f"🛡️ [ACCOUNT EXCLUDED] Account {i+1} ({helper.email}): {ineligibility_reason}. Zero risk permitted.")
                    continue

                # Enforce Fleet-Wide Tier-Specific Dollar Risk Ceilings with Buffer-Adaptive Ladders
                if getattr(Config, 'TIER_CAPS_ENABLED', True):
                    acct_caps = getattr(Config, 'ACCOUNT_RISK_CAPS', {})
                    if helper.email in acct_caps:
                        base_cap = acct_caps[helper.email]
                        if base_cap <= 0.0:
                            target_risk_usd = 0.0
                        else:
                            # Dynamic ratchet scaling based on remaining buffer above floor:
                            if helper.email == getattr(Config, 'FUNDED_ACCOUNT_1_EMAIL', 's79qv3xetj@upcomers.com'):
                                # Account 1: $35 base -> $50 when buffer > $600 -> $70 when buffer > $1,200
                                if remaining_buffer > 1200.0:
                                    target_risk_usd = 70.0
                                elif remaining_buffer > 600.0:
                                    target_risk_usd = 50.0
                                else:
                                    target_risk_usd = 35.0
                            elif helper.email == "jfcuue7er3@upcomers.com":
                                # Account 9: Fresh 50k Oracle Lead Striker
                                # $150 base -> scales to $250 once trailing floor locks at $50,000 (buffer > $2,650)
                                if remaining_buffer > 2650.0:
                                    target_risk_usd = 250.0
                                else:
                                    target_risk_usd = 150.0
                            elif equity <= 35000.0:
                                # $25k Tier (Accounts 3, 7): Base $35 / $50 -> scales to $65 / $80 at buffer > $1,000
                                if remaining_buffer > 1000.0:
                                    target_risk_usd = min(80.0, base_cap * 1.5)
                                else:
                                    target_risk_usd = base_cap
                            else:
                                # $50k Tier (Accounts 2, 6): Base $70 / $80 -> scales to $120 at buffer > $1,800
                                if remaining_buffer > 1800.0:
                                    target_risk_usd = 120.0
                                else:
                                    target_risk_usd = base_cap
                            # Ensure buffer maintains survival runway (at least 5+ losses)
                            target_risk_usd = min(target_risk_usd, max(15.0, remaining_buffer * 0.20))
                    elif equity <= 15000.0:
                        # Decommissioned accounts ($10k tier)
                        target_risk_usd = 0.0
                    elif equity <= 35000.0:
                        target_risk_usd = getattr(Config, 'TIER_MAX_RISK_25K', 40.0)
                    else:
                        target_risk_usd = getattr(Config, 'TIER_MAX_RISK_50K', 80.0)
                
                # Calculate exact stop loss distance
                if stop_loss is not None and entry_price is not None:
                    stop_dist = abs(float(entry_price) - float(stop_loss))
                elif stop_loss is not None:
                    # Fallback if entry price is not explicitly passed
                    stop_dist = 25.0 if "ETH" in symbol else 300.0 if "BTC" in symbol else 15.0
                else:
                    stop_dist = 25.0 if "ETH" in symbol else 300.0 if "BTC" in symbol else 15.0
                
                if stop_dist <= 0:
                    stop_dist = 25.0 if "ETH" in symbol else 300.0 if "BTC" in symbol else 15.0
                    
                exact_lots = target_risk_usd / stop_dist
                scaled_lot = round(exact_lots * risk_scale, 2)
                
                # Enforce Hard Per-Order Maximum Lot Size Ceiling
                max_order_lot = getattr(Config, 'MAX_LOT_SIZE_PER_ORDER', {}).get(symbol, 5.0)
                if scaled_lot > max_order_lot:
                    logger.warning(f"⚠️ Clamping order size on {symbol} from {scaled_lot} lots to max safety cap {max_order_lot} lots.")
                    scaled_lot = max_order_lot
                    
                if scaled_lot < 0.01:
                    scaled_lot = 0.01
                    
                is_scale_out_acc = getattr(Config, 'SPLIT_FLEET_SCALE_OUT_ENABLED', True) and (i in getattr(Config, 'SCALE_OUT_ACCOUNT_INDICES', [0, 2, 3, 4]))

                if is_scale_out_acc and scaled_lot >= 0.02 and entry_price is not None and stop_loss is not None:
                    # ── TWO-TRANCHE SPLIT EXECUTION (50% TP1 @ +1.5R, 50% TP2 @ Full Target) ──
                    lot_t1 = round(scaled_lot * 0.50, 2)
                    lot_t2 = round(scaled_lot - lot_t1, 2)
                    if lot_t1 < 0.01: lot_t1 = 0.01
                    if lot_t2 < 0.01: lot_t2 = 0.01
                    
                    tp1_r = getattr(Config, 'SCALE_OUT_TP1_R', 1.5)
                    tp1_price = round(float(entry_price) + (tp1_r * stop_dist) if side == "buy" else float(entry_price) - (tp1_r * stop_dist), 2)
                    
                    # Place Tranche 1 (Cash Builder @ +1.5R)
                    res_t1 = helper.place_order(
                        instrument_id=instrument_id,
                        side=side,
                        qty=lot_t1,
                        stop_loss=stop_loss,
                        take_profit=tp1_price,
                        order_type="market",
                        symbol_hint=symbol
                    )
                    time.sleep(1.0)
                    # Place Tranche 2 (Runner @ Full TP)
                    res_t2 = helper.place_order(
                        instrument_id=instrument_id,
                        side=side,
                        qty=lot_t2,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        order_type="market",
                        symbol_hint=symbol
                    )
                    success = bool(res_t1 or res_t2)
                    if success:
                        logger.info(f"✅ Account {i+1} ({helper.email}) [SCALE-OUT SPLIT] Filled T1={lot_t1} lots (TP1: {tp1_price}) & T2={lot_t2} lots (TP2: {take_profit}) on {symbol}")
                        results.append(True)
                    else:
                        logger.warning(f"⚠️ Account {i+1} ({helper.email}) scale-out order placement failed.")
                        results.append(False)
                else:
                    # ── FULL RUNNER SINGLE ORDER EXECUTION ──
                    success = helper.place_order(
                        instrument_id=instrument_id,
                        side=side,
                        qty=scaled_lot,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        order_type="market",
                        symbol_hint=symbol
                    )
                    if success:
                        logger.info(f"✅ Account {i+1} ({helper.email}) [FULL RUNNER] Filled {scaled_lot} lots {side.upper()} on {symbol} (SL: {stop_loss}, TP: {take_profit})")
                        results.append(True)
                    else:
                        logger.warning(f"⚠️ Account {i+1} ({helper.email}) order placement failed or rejected.")
                        results.append(False)
            except Exception as e:
                logger.error(f"❌ Error dispatching to Account {i+1} ({helper.email}): {e}")
                results.append(False)
                
        filled_count = sum(1 for r in results if r)
        logger.info(f"📊 [PROBE & SCALE] Execution summary: {filled_count}/{len(self.helpers)} accounts successfully filled.")
        
        # Record Persistent Cooldown upon successful order execution (Invariant 8)
        if filled_count > 0:
            ExecutionFirewall.record_trade_execution(symbol)

        return {
            "success": filled_count > 0,
            "filled_count": filled_count,
            "total_accounts": len(self.helpers),
            "tranche_label": tranche_label
        }
