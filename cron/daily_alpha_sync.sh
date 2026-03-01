#!/bin/bash
# 🧠 Daily Alpha Sync: Harvesting Human Alpha for Sovereign Memory
# This script should be run daily via crontab

# Navigate to project directory
cd "/Users/nicholasmacaskill/sovereignSMC/sovereignSMC"

# Load environment
source venv/bin/activate

echo "🕵️‍♂️ Starting Alpha Sync Cycle..."

# 1. Harvest manual trades from Supabase
python3 scripts/data/extract_manual_from_supabase.py

# 2. Vectorize new entries (Bridge to RAG memory)
python3 scripts/backfill_embeddings.py 50

# 3. Perform Delta Analysis to update reports
python3 scripts/data/perform_delta_analysis.py

echo "✅ Alpha Sync Complete."
