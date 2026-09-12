import os
import re

# 1. Fix tl_client.py return types
f_tl = "src/clients/tl_client.py"
with open(f_tl, "r") as f:
    tl_content = f.read()

tl_content = tl_content.replace(
    'return []',
    'return {"success": False, "filled_count": 0, "total_accounts": len(self.helpers) if hasattr(self, "helpers") and self.helpers else 0, "error": "ATOMIC_SETUP_LIMIT_REACHED"}'
)

with open(f_tl, "w") as f:
    f.write(tl_content)


# 2. Fix execution_firewall.py setup limit and exception
f_fw = "src/core/execution_firewall.py"
with open(f_fw, "r") as f:
    fw_content = f.read()

# Replace check_global_daily_setup_limit entirely
import ast
# We'll just regex out the whole function
pattern = r'    @staticmethod\s+def check_global_daily_setup_limit.*?return True, "OK"'
new_func = """    @staticmethod
    def check_global_daily_setup_limit() -> Tuple[bool, str]:
        \"\"\"
        INVARIANT 11: Global Daily Setup Limit (Max 1-2 Setups Per Day) via Atomic Lock.
        \"\"\"
        import json
        import os
        from datetime import datetime, timezone
        
        lock_file_path = "data/daily_setup_lock.json"
        try:
            if os.path.exists(lock_file_path):
                with open(lock_file_path, "r") as f:
                    data = json.load(f)
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if data.get("date") == today_str and data.get("setups_fired", 0) >= 2:
                    return False, f"Daily Setup Limit hit ({data.get('setups_fired')} setups locked in memory). Trading locked for 24h."
        except Exception as e:
            return False, f"Setup limit check failed: {e}"
        return True, "OK\"\"\""""

fw_content = re.sub(pattern, new_func, fw_content, flags=re.DOTALL)

with open(f_fw, "w") as f:
    f.write(fw_content)

print("Fixed tl_client.py and execution_firewall.py")
