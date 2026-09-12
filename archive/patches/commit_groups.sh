#!/bin/bash

# Group 1: AI, RAG, and Token Budget fixes
git add src/engines/multi_account_funnel.py src/engines/ai_permission_map.py src/core/memory.py src/engines/visual_vector_engine.py src/core/token_tracker.py
git commit -m "fix(ai): patch SMT defaults, stale RAG gates, and vector zero-padding"

# Group 2: Execution Firewall and Risk
git add src/core/execution_firewall.py src/core/config.py
git commit -m "fix(firewall): wire up Hurst regime gates, Atomic FileLocks, and News invariants"

# Group 3: TradeLocker Execution & Settlements
git add src/clients/tl_client.py
git commit -m "fix(execution): patch TL bracket settlement loop and payload types"

# Group 4: Regime-Aware Shadow Analytics
git add src/engines/counterfactual_tracker.py src/ui/glass_server.py src/core/database.py
git commit -m "feat(shadow): add regime-aware tracking and matrix expectancy to counterfactuals"

# Group 5: Core framework and additional updates
git add -u
git commit -m "refactor(core): Sovereign SMC architecture final graduation updates"

