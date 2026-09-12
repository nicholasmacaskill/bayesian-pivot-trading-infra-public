import re

f_path = "src/core/database.py"
with open(f_path, "r") as f:
    content = f.read()

# Add ALTER TABLE block in init_db()
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
"""

# Find where init_db does conn.commit() for the counterfactual table
content = content.replace("conn.commit()\n\n    def get_db_connection", "conn.commit()\n" + alter_sql + "\n    def get_db_connection")

with open(f_path, "w") as f:
    f.write(content)
print("database.py patched")
