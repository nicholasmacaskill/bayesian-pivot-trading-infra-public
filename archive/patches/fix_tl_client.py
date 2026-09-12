import os
import re

filepath = "src/clients/tl_client.py"
with open(filepath, "r") as f:
    content = f.read()

# Remove stopLoss from payload completely
payload_sl_code = """        if stop_loss:
            payload["stopLoss"] = float(stop_loss)
            payload["stopLossType"] = "absolute"
        if take_profit:
            payload["takeProfit"] = float(take_profit)
            payload["takeProfitType"] = "absolute\"\"\"
"""
content = re.sub(r'        if stop_loss:\s*payload\["stopLoss"\].*?takeProfitType"\] = "absolute"', '', content, flags=re.DOTALL)

# Add robust bracket loop using modify_position_bracket
old_bracket_code = r'try:\s*open_pos = self\.get_open_positions\(\).*?except Exception as bracket_err:\s*logger\.warning\(f"⚠️ Bracket attach non-fatal error: \{bracket_err\}"\)'

new_bracket_code = """try:
                            # Robust 5-second polling loop to guarantee settlement before patch
                            import time
                            settled = False
                            for poll in range(5):
                                time.sleep(1.0)
                                open_pos = self.get_open_positions()
                                if open_pos:
                                    for p in open_pos:
                                        if str(p.get("tradableInstrumentId")) == str(instrument_id) and str(p.get("side")).lower() == side.lower():
                                            # Found it, patch it
                                            pos_id = p.get("id")
                                            self.modify_position_bracket(pos_id, stop_loss=stop_loss, take_profit=take_profit)
                                            settled = True
                                            break
                                if settled:
                                    break
                            if not settled:
                                logger.critical("⚠️ Trade placed but failed to locate position ID for bracket patch!")
                        except Exception as bracket_err:
                            logger.warning(f"⚠️ Bracket attach non-fatal error: {bracket_err}")"""

content = re.sub(old_bracket_code, new_bracket_code, content, flags=re.DOTALL)

with open(filepath, "w") as f:
    f.write(content)
