
import modal
from config import Config

# Re-use the image from modal_app.py
image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .pip_install("yfinance", "pytz")
    .add_local_python_source("config")
    .add_local_python_source("tradelocker_client")
)

app = modal.App("smc-alpha-count-accounts")

@app.function(
    image=image,
    secrets=Config.get_modal_secrets()
)
def count_accounts():
    from tradelocker_client import TradeLockerClient
    tl = TradeLockerClient()
    count = len(tl.helpers)
    emails = [h.email for h in tl.helpers]
    return {"count": count, "emails": emails}

if __name__ == "__main__":
    with app.run():
        print(count_accounts.remote())
