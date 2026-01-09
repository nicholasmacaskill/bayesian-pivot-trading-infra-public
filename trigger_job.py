
from modal_app import app, run_scanner_job

@app.local_entrypoint()
def main():
    print("🚀 Manually triggering run_scanner_job on the cloud...")
    try:
        run_scanner_job.remote()
        print("✅ Job triggered successfully.")
    except Exception as e:
        print(f"❌ Failed to trigger job: {e}")
