#!/usr/bin/env bash
# scripts/push_public.sh
# ─────────────────────────────────────────────────────────────────────────────
# Selective push to the public GitHub mirror.
# Only safe files (dashboard, stubs, harness, docs) are included.
# Core engine logic, config thresholds, and runner orchestration are excluded.
#
# Usage: bash scripts/push_public.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

REMOTE="public"
BRANCH="main"
TMP_BRANCH="public-staging-$(date +%s)"

echo "📦 Creating staging branch..."
git checkout -b "$TMP_BRANCH"

# ── Files to REMOVE from the public push ──────────────────────────────────────
REMOVE_FILES=(
  # Core IP — scanner logic
  "src/engines/smc_scanner.py"         # Replaced by stub in public mirror
  "src/engines/sovereign_engine/patterns.py"
  "src/engines/sovereign_engine/scanners.py"
  "src/engines/sovereign_engine/analyzer.py"
  "src/engines/sovereign_engine/forensics.py"
  "src/engines/sovereign_engine/injection_defense.py"
  "src/engines/sovereign_engine/persistence.py"
  "src/engines/sovereign_engine/tripwire.py"
  "src/engines/sovereign_engine/triggers.py"

  # AI scoring & audit logic
  "src/engines/ai_audit_engine.py"
  "src/engines/retraining_loop.py"

  # Signal pipeline
  "src/engines/correlation_gate.py"
  "src/engines/regime_filter.py"
  "src/engines/intermarket_engine.py"
  "src/engines/execution_audit.py"
  "src/engines/trade_ledger.py"

  # Runner orchestration
  "src/runners/local_scanner.py"
  "src/runners/forensic_audit.py"
  "src/runners/sovereign_ctl.py"

  # Strategy blueprints (replaced by philosophy doc)
  "strategies/strategy_2_mean_reversion.md"
  "strategies/strategy_3_order_flow.md"
  "strategies/future_ideas.md"

  # Internal docs
  "docs/SOVEREIGN_SYSTEM_MANIFESTO.md"

  # Data & charts (large binary blobs)
  "data/"
  "backtesting/monte_carlo_results.json"
)

for f in "${REMOVE_FILES[@]}"; do
  git rm -rf --cached "$f" 2>/dev/null || true
done

# ── Create a .gitignore for the public branch ─────────────────────────────────
cat > .gitignore.public << 'EOF'
# Private implementation files — not published in public mirror
src/engines/smc_scanner_impl.py
src/engines/sovereign_engine/
src/engines/ai_audit_engine.py
src/engines/ai_validator_impl.py
src/engines/correlation_gate.py
src/engines/regime_filter.py
src/engines/intermarket_engine.py
src/engines/execution_audit.py
src/engines/trade_ledger.py
src/runners/local_scanner.py
src/runners/forensic_audit.py
src/runners/sovereign_ctl.py
strategies/future_ideas.md
strategies/strategy_2_*.md
strategies/strategy_3_*.md
docs/SOVEREIGN_SYSTEM_MANIFESTO.md
data/
*.db
*.key
.env*
__pycache__/
EOF

echo "🚀 Pushing to $REMOTE/$BRANCH..."
git push "$REMOTE" "$TMP_BRANCH:$BRANCH" --force

echo "🧹 Cleaning up staging branch..."
git checkout main
git branch -D "$TMP_BRANCH"

echo "✅ Public mirror updated successfully."
