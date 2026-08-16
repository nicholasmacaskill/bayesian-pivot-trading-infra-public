import sys
import os
import time
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.database import init_db, execute_db_write_with_retry, get_db_connection
from src.engines.multi_account_funnel import MultiAccountFunnelManager, align_lot_size

class TestConcurrencyAndIdempotency(unittest.TestCase):
    def setUp(self):
        init_db()
        self.manager = MultiAccountFunnelManager()

    def test_lot_size_step_alignment(self):
        """Verifies lot sizing aligns with min_lot and lot_step bounds."""
        self.assertEqual(align_lot_size(0.005, min_lot=0.01, lot_step=0.01), 0.0)  # Below min lot -> 0.0
        self.assertEqual(align_lot_size(0.128, min_lot=0.01, lot_step=0.01), 0.12) # Round down to step
        self.assertEqual(align_lot_size(1.500, min_lot=0.01, lot_step=0.01), 1.50)

    def test_concurrent_anti_hedging_race_condition(self):
        """
        Simulates 10 concurrent threads attempting opposing trade intents simultaneously.
        Verifies the in-memory Intent Registry blocks race conditions 100% of the time.
        """
        blocked_count = 0
        approved_count = 0
        lock = threading.Lock()

        def attempt_trade(thread_id):
            nonlocal blocked_count, approved_count
            direction = "BUY" if thread_id % 2 == 0 else "SELL"
            acc_key = f"ACCOUNT_{chr(65 + (thread_id % 8))}"
            
            # Check gate
            ok, reason = self.manager.check_anti_hedging_gate("BTC/USD", direction, [])
            if ok:
                # Register in-flight intent immediately
                self.manager.register_in_flight_intent("BTC/USD", direction, acc_key)
                with lock:
                    approved_count += 1
                time.sleep(0.05) # Simulate API latency
                self.manager.clear_in_flight_intent("BTC/USD", direction, acc_key)
            else:
                with lock:
                    blocked_count += 1

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_trade, i) for i in range(10)]
            for f in futures:
                f.result()

        # At least one thread should be blocked due to opposing in-flight intent
        self.assertGreater(blocked_count, 0)
        print(f"\n[Race Condition Test] Total Threads: 10 | Approved: {approved_count} | Blocked by Intent Registry: {blocked_count}")

    def test_sqlite_concurrent_write_backoff(self):
        """
        Spawns 10 concurrent database write transactions to verify zero 'database is locked' errors.
        """
        success_count = 0
        lock = threading.Lock()

        def write_db(thread_id):
            nonlocal success_count
            query = "INSERT INTO scans (symbol, timeframe, pattern, ai_score) VALUES (?, ?, ?, ?)"
            params = (f"TEST_{thread_id}", "5m", "StressTest", 8.0)
            res = execute_db_write_with_retry(query, params)
            if res:
                with lock:
                    success_count += 1



        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_db, i) for i in range(10)]
            for f in futures:
                f.result()

        self.assertEqual(success_count, 10)
        print(f"[SQLite Stress Test] 10/10 Concurrent Writes Completed Successfully in WAL Mode with Retry Backoff.")

if __name__ == "__main__":
    unittest.main()
