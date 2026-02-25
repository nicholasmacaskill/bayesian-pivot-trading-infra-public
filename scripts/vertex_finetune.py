"""
Vertex AI Fine-Tuning Launcher
================================
Submits a supervised fine-tuning job to Vertex AI using the exported
sovereign_trades.jsonl training data.

Prerequisites:
  1. Google Cloud project with Vertex AI API enabled
  2. `pip install google-cloud-aiplatform google-cloud-storage`
  3. Set in .env.local:
       GOOGLE_CLOUD_PROJECT=your-project-id
       VERTEX_AI_LOCATION=us-central1  (or nearest region)
  4. Authenticate: `gcloud auth application-default login`

Run: python3 scripts/vertex_finetune.py
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('.env.local')
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VertexFinetune")

TRAINING_FILE = "data/training/sovereign_trades.jsonl"
GCS_BUCKET = os.environ.get("GCS_BUCKET", "sovereign-training-data")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
BASE_MODEL = "gemini-2.0-flash-001"  # Tunable Gemini model

def check_prerequisites():
    """Validates environment before attempting to submit job."""
    errors = []
    
    if not PROJECT_ID:
        errors.append("GOOGLE_CLOUD_PROJECT not set in .env.local")
    
    if not Path(TRAINING_FILE).exists():
        errors.append(f"Training file not found: {TRAINING_FILE}. Run export_training_data.py first.")
    else:
        with open(TRAINING_FILE) as f:
            lines = f.readlines()
        if len(lines) < 16:
            errors.append(f"Training file has only {len(lines)} examples. Vertex AI requires ≥16.")
        else:
            logger.info(f"✅ Training file: {len(lines)} examples")
    
    try:
        import google.cloud.aiplatform
        import google.cloud.storage
        logger.info("✅ google-cloud-aiplatform installed")
    except ImportError:
        errors.append("Missing: pip install google-cloud-aiplatform google-cloud-storage")
    
    if errors:
        for e in errors:
            logger.error(f"❌ {e}")
        return False
    return True

def upload_to_gcs(local_file: str, bucket_name: str, dest_blob: str) -> str:
    """Uploads training JSONL to Google Cloud Storage."""
    from google.cloud import storage
    client = storage.Client(project=PROJECT_ID)
    
    # Create bucket if not exists
    try:
        bucket = client.get_bucket(bucket_name)
    except Exception:
        logger.info(f"Creating GCS bucket: {bucket_name}")
        bucket = client.create_bucket(bucket_name, location=LOCATION)
    
    blob = bucket.blob(dest_blob)
    blob.upload_from_filename(local_file)
    gcs_uri = f"gs://{bucket_name}/{dest_blob}"
    logger.info(f"✅ Uploaded to {gcs_uri}")
    return gcs_uri

def submit_finetune_job(training_gcs_uri: str) -> str:
    """Submits the fine-tuning job to Vertex AI."""
    import google.cloud.aiplatform as aiplatform
    
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    
    job_name = f"sovereign-gatekeeper-{datetime.utcnow().strftime('%Y%m%d-%H%M')}"
    logger.info(f"🚀 Submitting fine-tuning job: {job_name}")

    # Vertex AI supervised tuning for Gemini
    from google.cloud.aiplatform.preview import tuning
    
    tuning_job = tuning.SupervisedTuningJob.create(
        base_model=f"publishers/google/models/{BASE_MODEL}",
        training_dataset_uri=training_gcs_uri,
        tuned_model_display_name=job_name,
        # Hyperparameters (sensible defaults for small datasets)
        epochs=3,
        learning_rate_multiplier=1.0,
    )

    logger.info(f"✅ Job submitted: {tuning_job.resource_name}")
    logger.info(f"   Monitor at: https://console.cloud.google.com/vertex-ai/generative-language/tuning")
    
    # Save endpoint reference for later use
    job_info = {
        "job_name": job_name,
        "resource_name": tuning_job.resource_name,
        "submitted_at": datetime.utcnow().isoformat(),
        "training_file": TRAINING_FILE,
        "base_model": BASE_MODEL,
        "status": "RUNNING"
    }
    os.makedirs("data/training", exist_ok=True)
    with open("data/training/finetune_job.json", "w") as f:
        json.dump(job_info, f, indent=2)
    
    return tuning_job.resource_name

def check_job_status():
    """Checks the status of the most recent fine-tuning job."""
    job_file = "data/training/finetune_job.json"
    if not os.path.exists(job_file):
        logger.error("No job found. Run vertex_finetune.py first.")
        return
    
    with open(job_file) as f:
        job_info = json.load(f)
    
    import google.cloud.aiplatform as aiplatform
    from google.cloud.aiplatform.preview import tuning
    
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    job = tuning.SupervisedTuningJob(job_info['resource_name'])
    
    logger.info(f"Job: {job_info['job_name']}")
    logger.info(f"State: {job.state}")
    
    if job.state.name == "JOB_STATE_SUCCEEDED":
        endpoint = job.tuned_model_endpoint_name
        logger.info(f"✅ COMPLETE! Tuned model endpoint: {endpoint}")
        logger.info(f"   Update GEMINI_API_KEY in your code to use this endpoint.")
        job_info['status'] = 'COMPLETE'
        job_info['endpoint'] = endpoint
        with open(job_file, 'w') as f:
            json.dump(job_info, f, indent=2)

def main():
    logger.info("🧠 Vertex AI Fine-Tuning Launcher")
    logger.info(f"   Project: {PROJECT_ID}")
    logger.info(f"   Location: {LOCATION}")
    logger.info(f"   Base model: {BASE_MODEL}")
    
    if "--status" in sys.argv:
        check_job_status()
        return
    
    if not check_prerequisites():
        sys.exit(1)
    
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    dest_blob = f"training/{timestamp}/sovereign_trades.jsonl"
    
    logger.info("⬆️  Uploading training data to GCS...")
    gcs_uri = upload_to_gcs(TRAINING_FILE, GCS_BUCKET, dest_blob)
    
    logger.info("🔬 Submitting fine-tuning job...")
    resource_name = submit_finetune_job(gcs_uri)
    
    logger.info("\n" + "="*60)
    logger.info("✅ Fine-tuning job submitted successfully!")
    logger.info(f"   This typically takes 1-3 hours.")
    logger.info(f"   Check status: python3 scripts/vertex_finetune.py --status")
    logger.info("="*60)

if __name__ == "__main__":
    main()
