import os
import shutil
import re

SOURCE_DIR = os.getcwd()
EXPORT_DIR = os.path.join(SOURCE_DIR, "public_export")
IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".gemini", "public_export"}
SENSITIVE_FILES = ["config.py", "smc_scanner.py", "strategies/strategy_1_smc_alpha.md"]

def setup_export_dir():
    if os.path.exists(EXPORT_DIR):
        shutil.rmtree(EXPORT_DIR)
    
    print(f"📂 Copying files to {EXPORT_DIR}...")
    
    # Copy all files except hidden/ignored
    for root, dirs, files in os.walk(SOURCE_DIR):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        # Calculate relative path
        rel_path = os.path.relpath(root, SOURCE_DIR)
        
        # Skip if within export_dir (should be handled by IGNORE_DIRS but just in case)
        if "public_export" in rel_path: continue
        
        target_dir = os.path.join(EXPORT_DIR, rel_path)
        os.makedirs(target_dir, exist_ok=True)
        
        for file in files:
            if file == "release_public.py": continue
            if file.startswith("."): continue
            
            src_file = os.path.join(root, file)
            dst_file = os.path.join(target_dir, file)
            shutil.copy2(src_file, dst_file)

def redact_config(filepath):
    """Redacts sensitive API keys and parameters in config.py"""
    print("🔒 Redacting Config...")
    with open(filepath, 'r') as f: content = f.read()
    
    # Redact Specific Values
    content = re.sub(r'API_KEY = ".*?"', 'API_KEY = "REDACTED"', content)
    content = re.sub(r'TELEGRAM_.* = ".*?"', 'TELEGRAM_TOKEN = "REDACTED"', content)
    
    # Redact Numeric Parameters and ROI stats
    content = re.sub(r'(RISK_PER_TRADE)\s*=\s*[\d\.]+', r'\1 = 0.001  # Proprietary (Redacted)', content)
    content = re.sub(r'(MAX_DRAWDOWN_LIMIT)\s*=\s*[\d\.]+', r'\1 = 0.05', content)
    content = re.sub(r'(DAILY_TRADE_LIMIT)\s*=\s*[\d\.]+', r'\1 = 1', content)
    content = re.sub(r'(ROI)\s*=\s*~[\d%]+', r'ROI = ~REDACTED%', content)
    
    # Redact Prop Firm Profiles
    content = re.sub(r'PROP_FIRMS = \{.*?\}', 'PROP_FIRMS = {"PUBLIC": {"name": "Public Profile", "url": "https://example.com", "contract_size": 1.0, "commission_rate": 0.0}}', content, flags=re.DOTALL)
    
    # Redact AI Thresholds
    content = re.sub(r'(AI_THRESHOLD)\s*=\s*[\d\.]+', r'\1 = 9.0', content)
    content = re.sub(r'(AI_THRESHOLD_ASIAN_FADE)\s*=\s*[\d\.]+', r'\1 = 9.0', content)

    # Redact Killzone Windows
    content = re.sub(r'(KILLZONE_.*?)\s*=\s*\(.*?\)', r'\1 = (0, 0) # Redacted Timing', content)

    # Redact Multi-Asset Alignments
    content = re.sub(r'(MIN_SMT_STRENGTH)\s*=\s*[\d\.]+', r'\1 = 0.99', content)

    # Redact Quartiles
    content = re.sub(r'(_QUARTILE.*?)\s*=\s*[\d\.]+', r'\1 = 0.0', content)
    
    with open(filepath, 'w') as f: f.write(content)

def redact_scanner(filepath):
    """Redacts proprietary math in smc_scanner.py"""
    print("🔒 Redacting SMC Scanner...")
    with open(filepath, 'r') as f: lines = f.readlines()
    
    new_lines = []
    in_redacted_block = False
    
    for line in lines:
        # Example redaction: Logic inside specific methods
        if "def get_detailed_bias" in line:
            new_lines.append(line)
            new_lines.append('        """\n        Calculates Multi-Factor Bias using proprietary signal inputs.\n        Returns: Bias String (BULLISH/BEARISH/NEUTRAL)\n        """\n')
            new_lines.append('        # [REDACTED] Proprietary Geometric Logic\n')
            new_lines.append('        return "NEUTRAL"  # Placeholder for public repo\n')
            in_redacted_block = True
            continue

        if "def scan_pattern" in line:
            new_lines.append(line)
            new_lines.append('        """\n        Main Scanning Function.\n        [REDACTED] Core Logic Hidden for Public Release.\n        """\n')
            new_lines.append('        return None\n')
            in_redacted_block = True
            continue

        if "def scan_asian_fade" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Proprietary Asian Range Fade Alpha.\n        """\n')
            new_lines.append('        return None\n')
            in_redacted_block = True
            continue

        if "def get_price_quartiles" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Proprietary Price Quartile Calculation.\n        """\n')
            new_lines.append('        return {}\n')
            in_redacted_block = True
            continue

        if "def get_session_quartile" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Proprietary Session Cycle Logic.\n        """\n')
            new_lines.append('        return {}\n')
            in_redacted_block = True
            continue

        if "def validate_sweep_depth" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Institutional Order Book Absorption Validation.\n        """\n')
            new_lines.append('        return True\n')
            in_redacted_block = True
            continue

        if "def get_volatility_adjusted_target" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Dynamic Targeted Alpha Logic.\n        """\n')
            new_lines.append('        return 0.0\n')
            in_redacted_block = True
            continue

        if "def get_next_institutional_target" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Recursively Scans for Draw on Liquidity.\n        """\n')
            new_lines.append('        return None\n')
            in_redacted_block = True
            continue

        if "def is_tapping_fvg" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Fair Value Gap Neutralization Logic.\n        """\n')
            new_lines.append('        return False\n')
            in_redacted_block = True
            continue

        if "def scan_order_flow" in line:
            new_lines.append(line)
            new_lines.append('        """\n        [REDACTED] Institutional Order Flow Logic.\n        """\n')
            new_lines.append('        return None\n')
            in_redacted_block = True
            continue

        if "def detect_mss" in line:
            new_lines.append(line)
            new_lines.append('        # [REDACTED] Proprietary Market Structure Shift Detection\n')
            new_lines.append('        return None\n')
            in_redacted_block = True
            continue
            
        if "def find_order_block" in line:
            new_lines.append(line)
            new_lines.append('        # [REDACTED] Proprietary Order Block Identification\n')
            new_lines.append('        return None\n')
            in_redacted_block = True
            continue 

        if "def get_hurst_exponent" in line:
            new_lines.append(line)
            new_lines.append('        # [REDACTED] Proprietary Geometric Persistence Math\n')
            new_lines.append('        return 0.5\n')
            in_redacted_block = True
            continue

        if "def check_stationarity" in line:
            new_lines.append(line)
            new_lines.append('        # [REDACTED] Proprietary Unit Root Logic\n')
            new_lines.append('        return True\n')
            in_redacted_block = True
            continue

        if "def get_smt_divergence" in line:
            new_lines.append(line)
            new_lines.append('        # [REDACTED] Proprietary Multi-Asset Correlation Math\n')
            new_lines.append('        return 0.0\n')
            in_redacted_block = True
            continue
            
        if in_redacted_block:
            # Check if we exited the function (dedent)
            if line.startswith("    def ") or line.startswith("def "):
                in_redacted_block = False
                # Do NOT continue here - we need to process this line as a regular line
            else:
                continue # Skip lines inside redacted function
            
        new_lines.append(line)
        
    with open(filepath, 'w') as f: f.writelines(new_lines)

if __name__ == "__main__":
    setup_export_dir()
    
    # Redact Config
    redact_config(os.path.join(EXPORT_DIR, "src", "core", "config.py"))
    
    # Redact Scanner Logic
    redact_scanner(os.path.join(EXPORT_DIR, "src", "engines", "smc_scanner.py"))
    
    # Remove All Sensitive Strategy Docs
    strategies_dir = os.path.join(EXPORT_DIR, "strategies")
    if os.path.exists(strategies_dir):
        shutil.rmtree(strategies_dir)
        print(f"🔒 Removed Sensitive Strategies Folder: {strategies_dir}")
            
    print("✅ Public Export Ready in /public_export")
    print("👉 To push: cd public_export && git init && git remote add origin ... && git push --force")
