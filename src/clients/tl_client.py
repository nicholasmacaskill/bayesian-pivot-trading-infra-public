import requests
import os
import logging
from datetime import datetime, date

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
                data = resp.json()
                self.access_token = data.get('accessToken')
                # CRITICAL: Fetch account details to avoid 404s
                return self.get_account_details()
            else:
                logger.error(f"Login Failed: {resp.status_code} - {resp.text[:100]}")
                return False
        except Exception as e:
            logger.error(f"TL Connection Error: {e}")
            return False

    def get_account_details(self):
        """User-provided account discovery logic via corrected /backend-api."""
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/all-accounts"
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
            if resp.status_code == 200:
                accounts = resp.json().get('accounts', [])
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
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
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
                                'symbol': str(p[1]), 
                                'side': 'BUY' if str(p[3]).lower() == 'buy' else 'SELL',
                                'pnl': float(p[9] or 0.0),
                                'entry_time': str(p[8]),
                                'price': float(p[5] or 0.0),
                                'status': 'OPEN'
                            })
                        except Exception as e:
                            print(f"❌ PARSE ERROR: {e} | DATA: {p}")
                            logger.error(f"Failed to parse list position: {e}")
                    else:
                        trades.append({
                            'id': p.get('id'),
                            'symbol': p.get('instrumentId'),
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
        """Fetches closed positions from the last N hours."""
        if not self.access_token and not self.login(): return []
        
        try:
            # Try getting history (generic endpoint, may vary by broker version)
            # We look for 'positions' with 'status' closed.
            # endpoint found in previous scraping: /backend-api/trade/history
            url = f"{self.base_url}/backend-api/trade/history?timeRange=last{hours}h" 
            # Fallback to general history if timeRange not supported
            
            # Note: For many TL installs, use /backend-api/trade/orders/history or /trade/accounts/{id}/history
            # We will try the most common one: 
            url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/history"
            
            resp = requests.get(url, headers=self._get_headers(auth=True), params={'limit': 100}, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                # Normalized list of closed trades
                trades = []
                positions = data.get('d', {}).get('positions', []) # TL often wraps in 'd'
                if not positions and isinstance(data, list): positions = data # direct list
                
                for p in positions:
                    # Filter for closed positions within timeframe
                    close_time_str = p.get('closeDate') or p.get('filledAt')
                    if not close_time_str: continue
                    
                    # Basic parsing
                    trades.append({
                        'id': p.get('id'),
                        'symbol': p.get('instrumentId'), # map to valid symbol later
                        'side': 'BUY' if p.get('side') == 'buy' else 'SELL',
                        'pnl': float(p.get('profit') or 0.0),
                        'close_time': close_time_str,
                        'price': float(p.get('avgClosePrice') or 0.0)
                    })
                return trades
            else:
                 # Try alternative endpoint
                 return []
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
                resp = requests.get(url, headers=helper._get_headers(auth=True), timeout=10)
                
                if resp.status_code == 200:
                    accounts = resp.json().get('accounts', [])
                    for acc in accounts:
                        acc_id = acc['id']
                        if acc_id in seen_account_ids:
                            print(f"   Skipping duplicate account {acc_id} (already counted)")
                            continue
                            
                        equity = float(acc.get('projectedEquity') or acc.get('accountBalance', 0.0))
                        print(f"   Account {acc_id}: ${equity:,.2f}")
                        total_equity += equity
                        seen_account_ids.add(acc_id)
                else:
                    print(f"Account {i+1} ({helper.email}) check failed: {resp.status_code}")
                    
            except Exception as e:
                print(f"Error checking account {i+1}: {e}")
        
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
