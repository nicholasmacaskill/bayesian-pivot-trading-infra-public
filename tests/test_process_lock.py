"""
Tests for MasterProcessLock Mutex
=================================
Verifies:
1. Single instance acquires lock cleanly.
2. Concurrent instance fails to acquire held lock.
3. Lock is released cleanly upon context exit or manual release.
"""

import os
import unittest
import tempfile
from src.core.process_lock import MasterProcessLock


class TestProcessLock(unittest.TestCase):

    def test_master_process_lock_acquisition_and_release(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_path = os.path.join(tmp_dir, "test_master.lock")
            
            lock1 = MasterProcessLock(runner_name="runner_1", lock_path=lock_path)
            self.assertTrue(lock1.acquire())
            self.assertTrue(lock1.acquired)
            self.assertTrue(os.path.exists(lock_path))

            # Second runner should fail
            lock2 = MasterProcessLock(runner_name="runner_2", lock_path=lock_path)
            self.assertFalse(lock2.acquire())
            self.assertFalse(lock2.acquired)

            # Release first lock
            lock1.release()
            self.assertFalse(lock1.acquired)

            # Second runner should now succeed
            self.assertTrue(lock2.acquire())
            self.assertTrue(lock2.acquired)
            lock2.release()

    def test_master_process_lock_context_manager(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_path = os.path.join(tmp_dir, "test_context.lock")
            
            with MasterProcessLock(runner_name="context_runner_1", lock_path=lock_path) as l1:
                self.assertTrue(l1.acquired)
                # Concurrent runner fails
                l2 = MasterProcessLock(runner_name="context_runner_2", lock_path=lock_path)
                self.assertFalse(l2.acquire())

            # After exiting context, lock is released
            l2 = MasterProcessLock(runner_name="context_runner_2", lock_path=lock_path)
            self.assertTrue(l2.acquire())
            l2.release()


if __name__ == "__main__":
    unittest.main()
