import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
import re
from google import genai
import requests
from src.core.config import Config
from src.core.database import get_db_connection

logger = logging.getLogger(__name__)

class PropGuardian:
    def __init__(self):
        # Establish sensible defaults (User requested 4% daily)
        self.max_daily_drawdown = Config.get('DAILY_DRAWDOWN_LIMIT', 0.04)
        self.max_total_drawdown = Config.get('MAX_DRAWDOWN_LIMIT', 0.06)
        self.target_rr = Config.get('TARGET_RR', 3.0)
        
        # Initialize Gemini for URL reading
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            
        # Try to pull dynamic rules once on init
        self._sync_dynamic_rules()

    def _sync_dynamic_rules(self):
        """Attempts to scrape the active prop firm URL and extract Drawdown logic."""
        active_firm = Config.get('ACTIVE_FIRM', 'UPCOMERS')
        firm_data = Config.PROP_FIRMS.get(active_firm)
        
        if not firm_data or not firm_data.get('url') or not self.client:
            return
            
        url = firm_data['url']
        try:
            print(f"🛡️ PropGuardian: Fetching dynamic rules from {url}...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            
            html = res.text
            clean = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)
            clean = re.sub(r'<style.*?>.*?</style>', '', clean, flags=re.DOTALL)
            
            # Simple text extraction
            text_content = []
            for tag in ['p', 'h1', 'h2', 'h3', 'li']:
                matches = re.findall(f'<{tag}[^>]*>(.*?)</{tag}>', clean, flags=re.DOTALL)
                for m in matches:
                    text_content.append(re.sub(r'<[^>]+>', ' ', m))
            
            clean_text = re.sub(r'\s+', ' ', " ".join(text_content)).strip()
            
            prompt = f"""
            Analyze the following text scraped from a prop firm website. 
            Extract the exact 'Daily Drawdown' limit and 'Total Drawdown' limit as percentages.
            
            If the text says "4% Daily Drawdown", return 0.04 for daily_drawdown.
            If multiple phases exist, return the strictest (lowest) drawdown.
            
            TEXT:
            {clean_text[:15000]}
            
            Return EXACTLY a JSON format like this, nothing else:
            {{"daily_drawdown": 0.04, "total_drawdown": 0.06}}
            """
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            data = json.loads(response.text)
            
            # Update Internal Limits
            if 'daily_drawdown' in data and data['daily_drawdown'] > 0:
                self.max_daily_drawdown = float(data['daily_drawdown'])
            if 'total_drawdown' in data and data['total_drawdown'] > 0:
                self.max_total_drawdown = float(data['total_drawdown'])
                
            print(f"🛡️ PropGuardian: Dynamic Rules Loaded - Daily: {self.max_daily_drawdown:.1%}, Total: {self.max_total_drawdown:.1%}")
            
        except Exception as e:
            print(f"PropGuardian Rule Sync Failed (Using Defaults): {e}")

    def check_account_health(self, current_equity: float):
        """
        Analyzes account health based on drawdown and historical performance.
        Returns a structured report with a risk_multiplier.
        """
        report = {
            "status": "HEALTHY",
            "daily_drawdown": 0.0,
            "total_drawdown": 0.0,
            "win_rate": 0.0,
            "avg_rr": 0.0,
            "risk_multiplier": 1.0,
            "message": "Account within safe parameters."
        }

        try:
            conn = get_db_connection()
            c = conn.cursor()

            # 1. Total Drawdown Calculation
            # We use the maximum historical value from sync_state as high-water mark
            c.execute("SELECT value FROM sync_state WHERE key = 'high_water_mark'")
            hwm_row = c.fetchone()
            hwm = float(hwm_row['value']) if hwm_row else current_equity

            if current_equity > hwm:
                hwm = current_equity
                c.execute("INSERT OR REPLACE INTO sync_state (key, value, last_updated) VALUES (?, ?, ?)", 
                         ("high_water_mark", str(hwm), datetime.now().isoformat()))
                conn.commit()

            total_dd = (hwm - current_equity) / hwm if hwm > 0 else 0
            report['total_drawdown'] = total_dd

            # 2. Daily Drawdown Calculation
            # Fetch equity at the start of the day
            c.execute("SELECT value FROM sync_state WHERE key = 'daily_start_equity'")
            day_start_row = c.fetchone()
            
            if not day_start_row or float(day_start_row['value']) <= 0:
                # CRITICAL FIX: If no anchor exists or is invalid, anchor to current equity
                logger.warning("🛡️ PropGuardian: No valid daily anchor found. Anchoring to current equity.")
                self.update_daily_start(current_equity)
                day_start_equity = current_equity
            else:
                day_start_equity = float(day_start_row['value'])

            # Guard against division by zero or nonsensical drawdown calculation
            if day_start_equity > 0 and current_equity > 0:
                daily_dd = (day_start_equity - current_equity) / day_start_equity
            else:
                daily_dd = 0.0
            
            report['daily_drawdown'] = max(0, daily_dd) # Drawdown is always non-negative

            # 3. Performance Stats (Last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            c.execute("""
                SELECT pnl, side, strategy 
                FROM journal 
                WHERE status = 'CLOSED' AND timestamp > ?
            """, (thirty_days_ago,))
            trades = c.fetchall()

            if trades:
                wins = len([t for t in trades if t['pnl'] > 0])
                losses = len([t for t in trades if t['pnl'] < 0])
                report['win_rate'] = wins / len(trades)
                
                # Simple R:R estimation (Average Win / Average Loss)
                avg_win = sum(t['pnl'] for t in trades if t['pnl'] > 0) / wins if wins > 0 else 0
                avg_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0) / losses) if losses > 0 else 0
                report['avg_rr'] = avg_win / avg_loss if avg_loss > 0 else 0

            # --- HARD GUARD LOGIC ---
            if daily_dd >= self.max_daily_drawdown:
                report['status'] = "CRITICAL_DAILY_DD"
                report['risk_multiplier'] = 0.0
                report['message'] = f"Daily Drawdown Limit Hit: {daily_dd:.2%}"
            elif total_dd >= self.max_total_drawdown:
                report['status'] = "CRITICAL_TOTAL_DD"
                report['risk_multiplier'] = 0.0
                report['message'] = f"Total Drawdown Limit Hit: {total_dd:.2%}"
            elif report['win_rate'] < 0.3 and len(trades) > 5:
                report['status'] = "WARNING_PERFORMANCE"
                report['risk_multiplier'] = 0.5
                report['message'] = f"Low Win Rate ({report['win_rate']:.1%}). Reducing risk."

            conn.close()
        except Exception as e:
            print(f"PropGuardian Health Check Error: {e}")

        return report

    def update_daily_start(self, equity: float):
        """Call this at the first run of the day to anchor drawdown."""
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO sync_state (key, value, last_updated) VALUES (?, ?, ?)", 
                     ("daily_start_equity", str(equity), datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating daily start equity: {e}")
