import re
f_path = "src/core/database.py"
with open(f_path, "r") as f:
    content = f.read()

alter_sql = """
        # --- MIGRATION: Add Regime Metrics to counterfactual_trades ---
        try:
            cursor.execute("ALTER TABLE counterfactual_trades ADD COLUMN regime_type TEXT DEFAULT 'UNKNOWN'")
            cursor.execute("ALTER TABLE counterfactual_trades ADD COLUMN entry_hurst REAL DEFAULT 0.5")
            cursor.execute("ALTER TABLE counterfactual_trades ADD COLUMN adx_at_entry REAL DEFAULT 20.0")
            cursor.execute("ALTER TABLE counterfactual_trades ADD COLUMN vol_percentile REAL DEFAULT 50.0")
            conn.commit()
        except Exception:
            pass  # Columns already exist

    def get_db_connection"""

content = re.sub(r'    def get_db_connection', alter_sql, content, count=1)
with open(f_path, "w") as f:
    f.write(content)
