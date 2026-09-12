import re

f_path = "src/clients/tl_client.py"
with open(f_path, "r") as f:
    content = f.read()

lock_code = """
        # Atomic Daily Setup Lock Enforcement
        import json
        import os
        from datetime import datetime, timezone
        from filelock import FileLock
        
        lock_file_path = "data/daily_setup_lock.json"
        try:
            os.makedirs("data", exist_ok=True)
            lock = FileLock("data/daily_setup_lock.json.lock")
            with lock.acquire(timeout=5):
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if os.path.exists(lock_file_path):
                    with open(lock_file_path, "r") as lf:
                        data = json.load(lf)
                else:
                    data = {"date": today_str, "setups_fired": 0}
                    
                if data.get("date") != today_str:
                    data = {"date": today_str, "setups_fired": 0}
                    
                if data.get("setups_fired", 0) >= 2:
                    logger.critical("🛡️ [ATOMIC LOCK] Daily Setup Limit (2) reached. Rejecting fleet dispatch.")
                    return []
                    
                data["setups_fired"] = data.get("setups_fired", 0) + 1
                with open(lock_file_path, "w") as lf:
                    json.dump(data, lf)
        except Exception as e:
            logger.error(f"Failed to acquire atomic setup lock: {e}")
            return []
            
"""
# Insert right after the docstring
old_doc = "Protected by the Sovereign ExecutionFirewall.\n        \"\"\""
new_doc = old_doc + lock_code
content = content.replace(old_doc, new_doc)

with open(f_path, "w") as f:
    f.write(content)
