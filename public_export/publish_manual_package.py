import os
import subprocess
import shutil
import getpass
import sys

# CONFIGURATION
PACKAGE_DIR = os.path.join(os.getcwd(), "public_export", "tradelocker-python")
DIST_DIR = os.path.join(PACKAGE_DIR, "dist")
GITHUB_ACTOR = "nicholasmacaskill" # Hardcoded for convenience, or input()
REPOSITORY_URL = "https://npm.pkg.github.com/"

def run_command(command, cwd=None, env=None):
    """Running shell commands with real-time output."""
    try:
        result = subprocess.run(
            command, 
            cwd=cwd, 
            shell=True, 
            check=True, 
            text=True,
            env=env
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing command: {command}")
        print(f"   Exit code: {e.returncode}")
        sys.exit(1)

def main():
    print("🚀 STARTED: Manual Package Publisher")
    print(f"   Target: {PACKAGE_DIR}")

    # 1. Verify Tools
    print("\n📦 Verifying build tools...")
    try:
        import build
        import twine
    except ImportError:
        print("   Installing 'build' and 'twine'...")
        run_command(f"{sys.executable} -m pip install build twine keyring keyrings.alt")

    # 2. Clean previous builds
    if os.path.exists(DIST_DIR):
        print("\n🧹 Cleaning old build artifacts...")
        shutil.rmtree(DIST_DIR)

    # 3. Build Source
    print("\n🔨 Building Package...")
    run_command(f"{sys.executable} -m build", cwd=PACKAGE_DIR)

    # 4. Authenticate & Upload
    print("\n🔑 AUTHENTICATION REQUIRED")
    print("   To publish to GitHub Packages, you need a Personal Access Token (PAT).")
    print("   Permissions required: 'write:packages', 'read:packages'")
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        token = getpass.getpass(prompt=f"   Enter GitHub Token for {GITHUB_ACTOR}: ")
    
    if not token:
        print("❌ No token provided. Aborting.")
        sys.exit(1)

    
    # 5. Create GitHub Release
    print("\n🚀 Creating GitHub Release v0.1.0...")
    
    # Check if release exists
    check_url = f"https://api.github.com/repos/{GITHUB_ACTOR}/sovereign-smc-public/releases/tags/v0.1.0"
    headers = {
        "Authorization": f"token {token}", 
        "Accept": "application/vnd.github.v3+json"
    }
    
    import requests
    response = requests.get(check_url, headers=headers)
    
    if response.status_code == 200:
        print("⚠️  Release v0.1.0 already exists. Skipping creation.")
        upload_url = response.json().get("upload_url").split("{")[0]
    else:
        # Create Release
        create_url = f"https://api.github.com/repos/{GITHUB_ACTOR}/sovereign-smc-public/releases"
        data = {
            "tag_name": "v0.1.0",
            "target_commitish": "main",
            "name": "v0.1.0 - TradeLocker Python SDK",
            "body": "Initial public release of the standalone TradeLocker Python client.",
            "draft": False,
            "prerelease": False
        }
        res = requests.post(create_url, json=data, headers=headers)
        if res.status_code == 201:
            print("✅ Release Created Successfully!")
            upload_url = res.json().get("upload_url").split("{")[0]
        else:
            print(f"❌ Failed to create release: {res.text}")
            sys.exit(1)

    # 6. Upload Assets
    print("\n⬆️  Uploading Build Assets...")
    import glob
    files = glob.glob(f"{DIST_DIR}/*")
    
    for file_path in files:
        filename = os.path.basename(file_path)
        print(f"   - Uploading {filename}...")
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
            
        upl_res = requests.post(
            f"{upload_url}?name={filename}", 
            headers={"Authorization": f"token {token}", "Content-Type": "application/octet-stream"},
            data=file_data
        )
        if upl_res.status_code == 201:
            print("     OK")
        else:
            print(f"     Failed: {upl_res.status_code}")

    print("\n✅ SUCCESS: Release published to Repository!")
    print(f"   View at: https://github.com/{GITHUB_ACTOR}/sovereign-smc-public/releases")

if __name__ == "__main__":
    main()
