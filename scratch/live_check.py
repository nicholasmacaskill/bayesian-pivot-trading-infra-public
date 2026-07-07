import os
import sys
sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner

print("Scanning live BTC market...")
scanner = SMCScanner()
result = scanner.scan_pattern("BTC/USDT", "5m")

if result:
    print(f"SETUP FOUND: {result}")
else:
    print("NO SETUP DETECTED BY ALGORITHM.")
