import requests
import os
import logging
from typing import Optional, List, Dict, Any

# Set up default logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tradelocker")

class TradeLockerSession:
    """
    Manages a single TradeLocker account session.
    Handles authentication, headers, and basic account data fetching.
    """
    def __init__(self, email: str, password: str, server: str, base_url: str = "https://demo.tradelocker.com"):
        self.email = email
        self.password = password
        self.server_id = server
        self.base_url = base_url.rstrip('/')
        self.access_token: Optional[str] = None
        self.account_id: Optional[str] = None
        self.account_details: Dict[str, Any] = {}
        
    def _get_headers(self, auth: bool = False) -> Dict[str, str]:
        """Generates stealth headers to mimic a browser session."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
            "Content-Type": "application/json"
        }
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def login(self) -> bool:
        """
        Authenticates with TradeLocker and retrieves the JWT access token.
        Automatically fetches account details upon successful login.
        """
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/token"
            payload = {
                "email": self.email.strip(),
                "password": self.password,
                "server": self.server_id
            }
            
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=15)
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                self.access_token = data.get('accessToken')
                logger.info(f"Successfully logged in as {self.email}")
                return self._fetch_account_id()
            else:
                logger.error(f"Login Failed [{resp.status_code}]: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Connection Error during login: {e}")
            return False

    def _fetch_account_id(self) -> bool:
        """Internal method to discover the first available account ID."""
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/all-accounts"
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
            
            if resp.status_code == 200:
                accounts = resp.json().get('accounts', [])
                if accounts:
                    # We default to the first account found
                    self.account_details = accounts[0]
                    self.account_id = self.account_details.get('id')
                    logger.info(f"Connected to Account ID: {self.account_id}")
                    return True
                else:
                    logger.warning("No trading accounts found associated with these credentials.")
            
            return False
        except Exception as e:
            logger.error(f"Failed to fetch account info: {e}")
            return False

    def get_equity(self) -> float:
        """Returns the current projected equity or balance."""
        if not self.access_token:
            if not self.login():
                return 0.0
                
        # If we have details stored, optimize by returning cached? 
        # Better to re-fetch for real-time accuracy.
        try:
            url = f"{self.base_url}/backend-api/auth/jwt/all-accounts"
            resp = requests.get(url, headers=self._get_headers(auth=True), timeout=10)
            if resp.status_code == 200:
                accounts = resp.json().get('accounts', [])
                for acc in accounts:
                    if acc.get('id') == self.account_id:
                        return float(acc.get('projectedEquity') or acc.get('accountBalance', 0.0))
            return 0.0
        except Exception:
            return 0.0
            
    def close_all_positions(self) -> bool:
        """
        Closes all open positions for this account.
        (Placeholder for future expansion - API endpoint requires specific position IDs)
        """
        logger.warning("close_all_positions not yet fully implemented in v0.1.0")
        return False


class TradeLockerAggregator:
    """
    Manages multiple TradeLockerSession instances to aggregate data across accounts.
    Useful for Prop Firm traders managing multiple evaluations or funded accounts.
    """
    def __init__(self):
        self.sessions: List[TradeLockerSession] = []
        
    def add_session(self, email: str, password: str, server: str, base_url: str = "https://demo.tradelocker.com"):
        session = TradeLockerSession(email, password, server, base_url)
        self.sessions.append(session)
        
    def get_total_equity(self) -> float:
        """Sum of equity across all added sessions."""
        total = 0.0
        for session in self.sessions:
            total += session.get_equity()
        return total
