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
                    self.account_id = accounts[0]['id']
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
                            logger.info(f"   Skipping duplicate account {acc_id} (already counted)")
                            continue
                            
                        equity = float(acc.get('projectedEquity') or acc.get('accountBalance', 0.0))
                        logger.info(f"   Account {acc_id}: ${equity:,.2f}")
                        total_equity += equity
                        seen_account_ids.add(acc_id)
                else:
                    logger.warning(f"Account {i+1} ({helper.email}) check failed: {resp.status_code}")
                    
            except Exception as e:
                logger.error(f"Error checking account {i+1}: {e}")
        
        if total_equity == 0:
            logger.warning("All TradeLocker accounts offline or no funds. Using Fallback $100k.")
            return 100000.0
            
        return total_equity

    def get_daily_trades_count(self):
        """Sum of trades count from all accounts."""
        total_trades = 0
        for helper in self.helpers:
            total_trades += helper.get_todays_trades_count()
        return total_trades

    def get_trade_history(self, limit=5):
        return [] # Placeholder
