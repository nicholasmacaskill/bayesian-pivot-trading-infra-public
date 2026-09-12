"""
Sovereign SMC Master Process Mutex Lock
=======================================
Guarantees strictly single-instance master execution across all runners:
- Prevents multiple concurrent processes from scanning or executing live trades.
- Uses OS-level advisory file locks (fcntl.flock) + PID verification.
- Safe against crashed / stale processes.
"""

import os
import sys
import fcntl
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("MasterProcessLock")

LOCK_FILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
MASTER_LOCK_PATH = os.path.join(LOCK_FILE_DIR, "sovereign_master_execution.lock")


class MasterProcessLock:
    """
    Cross-process exclusive mutex lock using fcntl file locking and PID tracking.
    """
    def __init__(self, runner_name: str = "master_runner", lock_path: Optional[str] = None):
        self.runner_name = runner_name
        self.lock_path = lock_path or MASTER_LOCK_PATH
        self._file_obj = None
        self.acquired = False

    def acquire(self) -> bool:
        """
        Attempts to acquire the exclusive master process lock.
        Returns True if acquired, False if another process already holds it.
        """
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        try:
            self._file_obj = open(self.lock_path, "a+")
            fcntl.flock(self._file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Truncate and write lock metadata
            self._file_obj.seek(0)
            self._file_obj.truncate()
            lock_info = {
                "runner_name": self.runner_name,
                "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "command": " ".join(sys.argv)
            }
            json.dump(lock_info, self._file_obj, indent=2)
            self._file_obj.flush()
            self.acquired = True
            logger.info(f"🔒 [MASTER LOCK ACQUIRED] Runner '{self.runner_name}' (PID: {os.getpid()}) holds exclusive execution lock.")
            return True
        except (IOError, BlockingIOError):
            # Read existing lock owner if possible
            existing_owner = "Unknown"
            try:
                with open(self.lock_path, "r") as f:
                    data = json.load(f)
                    existing_owner = f"{data.get('runner_name')} (PID: {data.get('pid')}) started at {data.get('started_at')}"
            except Exception:
                pass
            logger.critical(f"🚨 [LOCK CONFLICT] Another master process is actively running: {existing_owner}. Exiting '{self.runner_name}' (PID: {os.getpid()}) to prevent multi-process order duplication.")
            if self._file_obj:
                try:
                    self._file_obj.close()
                except Exception:
                    pass
                self._file_obj = None
            self.acquired = False
            return False

    def release(self):
        """Releases the lock gracefully."""
        if self.acquired and self._file_obj:
            try:
                fcntl.flock(self._file_obj.fileno(), fcntl.LOCK_UN)
                self._file_obj.close()
            except Exception as e:
                logger.warning(f"Error releasing master lock: {e}")
            self.acquired = False
            self._file_obj = None
            logger.info(f"🔓 [MASTER LOCK RELEASED] Runner '{self.runner_name}' (PID: {os.getpid()}) released lock.")

    def __enter__(self):
        if not self.acquire():
            sys.exit(0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
