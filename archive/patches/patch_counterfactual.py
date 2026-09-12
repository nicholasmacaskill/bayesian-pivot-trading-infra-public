f_path = "src/engines/counterfactual_tracker.py"
with open(f_path, "r") as f:
    content = f.read()

old_insert = """conn.execute(
                \"\"\"
                INSERT INTO counterfactual_trades (
                    timestamp, account_key, symbol, direction, pattern, strategy_mode,
                    entry_price, stop_loss, take_profit_1, take_profit_2,
                    rejection_reasons, status, outcome, simulated_pnl, simulated_r
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 'PENDING', 0.0, 0.0)
                \"\"\",
                (
                    now_iso, account_key, symbol, direction, pattern, strategy_mode,
                    entry_price, stop_loss, tp1, tp2, reasons_json
                )
            )"""

new_insert = """regime_type = setup.get("regime", "UNKNOWN")
            entry_hurst = float(setup.get("hurst", setup.get("hurst_exponent", 0.5)))
            adx_at_entry = float(setup.get("adx", 20.0))
            vol_percentile = float(setup.get("vol_percentile", 50.0))

            conn.execute(
                \"\"\"
                INSERT INTO counterfactual_trades (
                    timestamp, account_key, symbol, direction, pattern, strategy_mode,
                    entry_price, stop_loss, take_profit_1, take_profit_2,
                    rejection_reasons, status, outcome, simulated_pnl, simulated_r,
                    regime_type, entry_hurst, adx_at_entry, vol_percentile
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 'PENDING', 0.0, 0.0, ?, ?, ?, ?)
                \"\"\",
                (
                    now_iso, account_key, symbol, direction, pattern, strategy_mode,
                    entry_price, stop_loss, tp1, tp2, reasons_json,
                    regime_type, entry_hurst, adx_at_entry, vol_percentile
                )
            )"""

content = content.replace(old_insert, new_insert)
with open(f_path, "w") as f:
    f.write(content)
