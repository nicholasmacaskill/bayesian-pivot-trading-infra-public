import os
import re

# 1. multi_account_funnel.py: smt_strength default
f1 = "src/engines/multi_account_funnel.py"
with open(f1, "r") as f: content = f.read()
content = content.replace("smt_strength: float = 0.20", "smt_strength: float = 0.0")
with open(f1, "w") as f: f.write(content)

# 2. ai_permission_map.py: Check is_stale
f2 = "src/engines/ai_permission_map.py"
with open(f2, "r") as f: content = f.read()
stale_check = """        # 1. Archetype Authorization"""
stale_fix = """        if perm.get("is_stale"):
            return False, 0.0, "AI Permission is STALE (older than 4 hours). Execution blocked."

        # 1. Archetype Authorization"""
content = content.replace(stale_check, stale_fix)
with open(f2, "w") as f: f.write(content)

# 3. memory.py: Fix ai_score/ai_reasoning
f3 = "src/core/memory.py"
with open(f3, "r") as f: content = f.read()
content = content.replace("trade.get('ai_grade')", "(trade.get('ai_grade') or trade.get('ai_score'))")
content = content.replace("trade.get('notes')", "(trade.get('notes') or trade.get('ai_reasoning'))")
with open(f3, "w") as f: f.write(content)

# 4. visual_vector_engine.py: VECTOR_DIM = 48
f4 = "src/engines/visual_vector_engine.py"
with open(f4, "r") as f: content = f.read()
content = content.replace("VECTOR_DIM = 64", "VECTOR_DIM = 48")
with open(f4, "w") as f: f.write(content)

# 5. token_tracker.py: Raise exception on budget
f5 = "src/core/token_tracker.py"
with open(f5, "r") as f: content = f.read()
budget_block = """            notifier._send_message(msg)
            _warning_sent = True
            logger.warning(f"Daily token budget ceiling exceeded: ${current_cost:.4f}")"""
budget_fix = """            notifier._send_message(msg)
            _warning_sent = True
            logger.warning(f"Daily token budget ceiling exceeded: ${current_cost:.4f}")
            raise RuntimeError(f"TOKEN BUDGET EXHAUSTED: ${current_cost:.4f} / ${DAILY_BUDGET_USD:.2f}")"""
content = content.replace(budget_block, budget_fix)
with open(f5, "w") as f: f.write(content)

print("Patched 1-5 successfully")
