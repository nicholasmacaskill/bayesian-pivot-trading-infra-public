
import modal
from config import Config

image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .pip_install("yfinance", "pytz")
    .add_local_python_source("config")
    .add_local_python_source("tradelocker_client")
)

app = modal.App("smc-alpha-final-verify")

@app.function(
    image=image,
    secrets=Config.get_modal_secrets()
)
def final_verify():
    from tradelocker_client import TradeLockerClient
    tl = TradeLockerClient()
    equity = tl.get_total_equity()
    trades = tl.get_daily_trades_count()
    accounts = [{"email": h.email, "id": h.account_id} for h in tl.helpers]
    return {"total_equity": equity, "trades_today": trades, "accounts": accounts}

if __name__ == "__main__":
    with app.run():
        print(final_verify.remote())
