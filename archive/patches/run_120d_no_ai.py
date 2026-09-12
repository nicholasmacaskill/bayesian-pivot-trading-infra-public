import sys
import os
sys.path.append(os.getcwd())

from src.core.config import Config
Config.BYPASS_AI_GATE = True
from scripts.analysis.comprehensive_120d_backtest import run_120d_backtest

print("Running Comprehensive 120d Backtest WITHOUT AI...")
run_120d_backtest()
