
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import modal
from src.core.config import Config


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .pip_install("yfinance", "pytz")
    .add_local_dir("src", remote_path="/root/src")
)

app = modal.App("smc-alpha-count-accounts")

@app.function(
    image=image,
    secrets=Config.get_modal_secrets()
)
def count_accounts():
    from src.clients.tl_client import TradeLockerClient
    tl = TradeLockerClient()
    count = len(tl.helpers)
    emails = [h.email for h in tl.helpers]
    equity = tl.get_total_equity()
    return {"count": count, "emails": emails, "total_equity": equity}


if __name__ == "__main__":
    with app.run():
        print(count_accounts.remote())
