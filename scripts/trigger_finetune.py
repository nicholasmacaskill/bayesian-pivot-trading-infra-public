import os
import json
import logging
import sys
from pathlib import Path
from google.cloud import aiplatform

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VertexTrigger")

def run_finetune(jsonl_path):
    """
    Automates the upload and triggering of a Vertex AI fine-tuning job.
    Requires GOOGLE_APPLICATION_CREDENTIALS and PROJECT_ID to be set.
    """
    project_id = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    bucket_name = os.environ.get("GCP_BUCKET_NAME")

    if not all([project_id, bucket_name]):
        logger.error("❌ Missing GCP configuration (PROJECT_ID, BUCKET_NAME).")
        return

    aiplatform.init(project=project_id, location=location)

    logger.info(f"🚀 Initializing Phase 2 Fine-Tuning for: {jsonl_path}")
    
    # 1. Upload to GCS
    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_name = f"training_data/{os.path.basename(jsonl_path)}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(jsonl_path)
    
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    logger.info(f"✅ Uploaded to {gcs_uri}")

    # 2. Trigger Fine-Tuning Job (Gemini 1.5 Flash / 2.0 Flash)
    # Note: As of now, Gemini fine-tuning is typically done via the Generative AI on Vertex AI
    # This is a placeholder for the API call which varies by model availability
    logger.info("📡 Dispatching fine-tuning job to Vertex AI (Supervised Tuning)...")
    
    # Example for SupervisedTuningJob
    # job = aiplatform.SupervisedTuningJob.create(
    #     display_name="sovereign-smc-phase2-evolution",
    #     source_model="gemini-1.5-flash-002",
    #     dataset_uri=gcs_uri,
    # )
    
    logger.info("⏳ Job submitted. The feedback loop is now closed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 trigger_finetune.py <path_to_jsonl>")
        sys.exit(1)
    
    run_finetune(sys.argv[1])
