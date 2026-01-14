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
    
    # Redact Numeric Parameters (e.g., STOP_LOSS_ATR_MULTIPLIER = 2.5 -> = <HIDDEN>)
    # But Python needs valid syntax. So replace with standard defaults or 0.0
    content = re.sub(r'(STOP_LOSS_ATR_MULTIPLIER)\s*=\s*[\d\.]+', r'\1 = 2.0  # Proprietary Parameter (Default)', content)
    content = re.sub(r'(TP1_R_MULTIPLE)\s*=\s*[\d\.]+', r'\1 = 1.0  # Proprietary Parameter (Default)', content)
    
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
            new_lines.append('        # Tracks: 4H Trend, Daily Structure, Momentum, Intermarket Flows\n')
            new_lines.append('        return "NEUTRAL"  # Placeholder for public repo\n')
            in_redacted_block = True
            continue
            
        if in_redacted_block:
            # Check if we exited the function (dedent)
            # Simple check: if line starts with '    def' or class def, we are out.
            # But indented logic continues.
            if line.strip().startswith("def "):
                in_redacted_block = False
                new_lines.append(line) # Add the new function def
            continue # Skip lines inside redacted function
            
        new_lines.append(line)
        
    with open(filepath, 'w') as f: f.writelines(new_lines)

if __name__ == "__main__":
    setup_export_dir()
    
    # Redact Config
    redact_config(os.path.join(EXPORT_DIR, "src", "core", "config.py"))
    
    # Redact Scanner Logic
    redact_scanner(os.path.join(EXPORT_DIR, "src", "engines", "smc_scanner.py"))
            
    print("✅ Public Export Ready in /public_export")
    print("👉 To push: cd public_export && git init && git remote add origin ... && git push --force")
