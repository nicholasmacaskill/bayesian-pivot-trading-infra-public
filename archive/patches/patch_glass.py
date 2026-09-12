import re

f_path = "src/ui/glass_server.py"
with open(f_path, "r") as f:
    content = f.read()

# Find the block where shadow_pf is calculated and strategies.append happens
old_append = """        # Calculate empirical profit factor
        gross_win = max(1.0, float(sh_wins) * 250.0)
        gross_loss = max(1.0, float(sh_losses) * 100.0)
        shadow_pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else 2.50

        strategies.append({"""

new_append = """        # Calculate empirical profit factor
        gross_win = max(1.0, float(sh_wins) * 250.0)
        gross_loss = max(1.0, float(sh_losses) * 100.0)
        shadow_pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else 2.50

        # Regime breakdown query
        try:
            cursor.execute(f\"\"\"
                SELECT 
                    coalesce(regime_type, 'UNKNOWN'),
                    count(*),
                    count(CASE WHEN outcome = 'HIT_TP' THEN 1 END),
                    count(CASE WHEN outcome = 'HIT_SL' THEN 1 END),
                    avg(simulated_r)
                FROM counterfactual_trades 
                WHERE {where_clauses}
                GROUP BY coalesce(regime_type, 'UNKNOWN')
            \"\"\")
            regime_rows = cursor.fetchall()
            regime_breakdown = []
            for r_row in regime_rows:
                r_type = r_row[0]
                r_samples = r_row[1]
                r_wins = r_row[2]
                r_losses = r_row[3]
                r_avg_r = round(float(r_row[4] or 0.0), 2)
                r_wr = round((r_wins / max(1, r_wins + r_losses)) * 100.0, 1) if (r_wins + r_losses) > 0 else 0.0
                regime_breakdown.append({
                    "regime": r_type,
                    "samples": r_samples,
                    "win_rate": r_wr,
                    "expected_r": r_avg_r
                })
        except Exception:
            regime_breakdown = []

        strategies.append({
            "regime_breakdown": regime_breakdown,"""

content = content.replace(old_append, new_append)

with open(f_path, "w") as f:
    f.write(content)
print("Glass server patched.")
