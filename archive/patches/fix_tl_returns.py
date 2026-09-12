import re

f_path = "src/clients/tl_client.py"
with open(f_path, "r") as f:
    content = f.read()

# We only want to replace return [] where it's part of the atomic lock logic.
content = content.replace(
    'logger.critical("🛡️ [ATOMIC LOCK] Daily Setup Limit (2) reached. Rejecting fleet dispatch.")\n                    return []',
    'logger.critical("🛡️ [ATOMIC LOCK] Daily Setup Limit (2) reached. Rejecting fleet dispatch.")\n                    return {"success": False, "filled_count": 0, "total_accounts": len(self.helpers) if hasattr(self, "helpers") and self.helpers else 0, "error": "ATOMIC_SETUP_LIMIT_REACHED"}'
)

content = content.replace(
    'logger.error(f"Failed to acquire atomic setup lock: {e}")\n            return []',
    'logger.error(f"Failed to acquire atomic setup lock: {e}")\n            return {"success": False, "filled_count": 0, "total_accounts": len(self.helpers) if hasattr(self, "helpers") and self.helpers else 0, "error": "ATOMIC_SETUP_LIMIT_REACHED"}'
)

with open(f_path, "w") as f:
    f.write(content)
print("Safely replaced tl_client.py atomic lock returns")
