import os
import dotenv

def check_env_keys(file_path):
    if not os.path.exists(file_path):
        print(f"Skipping {file_path} (not found)")
        return
    
    print(f"Checking keys in {file_path}...")
    config = dotenv.dotenv_values(file_path)
    for key in config.keys():
        if "NEXT_PUBLIC" in key:
            print(f"⚠️  WARNING: Found public key: {key}")
        elif "KEY" in key or "SECRET" in key or "TOKEN" in key:
            print(f"🔒 Found secret key candidate: {key}")
        else:
            print(f"   Found key: {key}")

if __name__ == "__main__":
    check_env_keys(".env")
    check_env_keys(".env.local")
    check_env_keys("dashboard/.env.local")
