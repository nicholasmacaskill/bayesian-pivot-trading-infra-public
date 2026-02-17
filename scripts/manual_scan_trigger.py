import modal
from src.engines.smc_scanner import SMCScanner
from config import Config

image = (
    modal.Image.debian_slim()
    .pip_install("pandas", "numpy", "yfinance", "ccxt", "ta-lib")
    .add_local_python_source("config")
    .add_local_python_source("database")
    .add_local_python_source("smc_scanner")
    .add_local_python_source("ai_validator")
    .add_local_python_source("intermarket_engine")
    .add_local_python_source("news_filter")
    .add_local_python_source("visualizer")
    .add_local_python_source("tl_client")
    .add_local_python_source("sentiment_engine")
    .add_local_python_source("telegram_notifier")
)

app = modal.App("smc-manual-trigger")
volume = modal.Volume.from_name("smc-alpha-storage")

@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=Config.get_modal_secrets()
)
def manual_scan():
    print("🚀 Starting Manual Diagnostic Scan...")
    scanner = SMCScanner()
    symbol = "BTC/USDT"
    
    # 1. Check Killzone
    is_kz = scanner.is_killzone()
    quartile = scanner.get_session_quartile()
    print(f"🕒 Time Check: Killzone={is_kz}, Quartile={quartile}")
    
    # 2. Check 4H Bias
    bias = scanner.get_4h_bias(symbol)
    print(f"📈 4H Bias: {bias}")
    
    # 3. Run Full Scan
    result = scanner.scan_pattern(symbol)
    if result:
        print(f"✅ FOUND PATTERN: {result[0]['pattern']}")
    else:
        print("❌ No Pattern Found (Logic is working, just no setup)")

if __name__ == "__main__":
    with app.run():
        manual_scan.call()
