
import modal
from config import Config

app = modal.App("smc-alpha-env-check")

@app.function(
    secrets=Config.get_modal_secrets()
)
def check_env_keys():
    import os
    keys = sorted(os.environ.keys())
    # Filter for TradeLocker and sync related keys to be helpful but safe
    tl_keys = [k for k in keys if "TRADELOCKER" in k or "SYNC" in k]
    return tl_keys

if __name__ == "__main__":
    with app.run():
        print(check_env_keys.remote())
