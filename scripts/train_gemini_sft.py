import os
import sys
import time
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
load_dotenv(".env.local")
load_dotenv(".env")

# Ensure project root is in path
sys.path.append(os.getcwd())

from google import genai
from src.core.config import Config
from src.engines.retraining_loop import RetrainingLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("GeminiSFT")

def run_gemini_fine_tuning():
    """
    Submits the SFT training dataset generated from live trade outcomes
    to Google AI Studio for free model fine-tuning.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("❌ GEMINI_API_KEY not found in .env.local! Get a free key at https://aistudio.google.com/app/apikey")
        return False

    # 1. Force a fresh dataset export from trade outcomes
    logger.info("📊 Step 1: Exporting fresh trade outcome dataset from signed_ledger & journal...")
    retrain = RetrainingLoop()
    summary = retrain.run(force=True)
    
    jsonl_path_str = summary.get("jsonl_export")
    if not jsonl_path_str or not os.path.exists(jsonl_path_str):
        logger.error("❌ Failed to generate JSONL training dataset.")
        return False
        
    logger.info(f"✅ Training Dataset Ready: {jsonl_path_str} ({summary.get('samples', 0)} trade samples)")

    # 2. Initialize Gemini Client
    client = genai.Client(api_key=api_key)
    
    # 3. Create Fine-Tuning Job on Google AI Studio
    logger.info("🚀 Step 2: Submitting Fine-Tuning job to Google AI Studio (Free Tier)...")
    try:
        # Base model for fine-tuning
        base_model = "models/gemini-1.5-flash-001"
        display_name = f"sovereign-smc-v1-{int(time.time())}"
        
        # Read dataset to verify contents
        with open(jsonl_path_str, "r") as f:
            training_data = [json.loads(line) for line in f if line.strip()]

        logger.info(f"Submitting {len(training_data)} instruction pairs to base model '{base_model}'...")
        
        # Create tuning job using Google GenAI SDK
        tuning_job = client.tunings.tune(
            base_model=base_model,
            training_dataset={
                "examples": [
                    {
                        "text_input": item["messages"][0]["content"],
                        "output": item["messages"][1]["content"]
                    }
                    for item in training_data if len(item.get("messages", [])) >= 2
                ]
            },
            config={
                "tuned_model_display_name": display_name,
                "epoch_count": 5,
                "batch_size": 4,
                "learning_rate": 0.001
            }
        )
        
        logger.info(f"🎉 Fine-Tuning Job Created Successfully!")
        logger.info(f"   Job Name: {tuning_job.name}")
        logger.info(f"   Display Name: {display_name}")
        logger.info("⏳ Waiting for model training to complete (~3-5 minutes)...")
        
        # Poll for completion
        while True:
            job_status = client.tunings.get(name=tuning_job.name)
            state = getattr(job_status, "state", "TRAINING")
            logger.info(f"   Status: {state}")
            
            if state in ["COMPLETED", "SUCCEEDED", "ACTIVE"]:
                tuned_model_id = getattr(job_status, "tuned_model", tuning_job.name)
                logger.info(f"🏆 SUCCESS! Custom Fine-Tuned Model Ready: {tuned_model_id}")
                
                # Save fine-tuned model ID to .env.local
                env_path = Path(".env.local")
                if env_path.exists():
                    content = env_path.read_text()
                    if "SOVEREIGN_FINE_TUNED_MODEL" in content:
                        import re
                        content = re.sub(r"SOVEREIGN_FINE_TUNED_MODEL=.*", f"SOVEREIGN_FINE_TUNED_MODEL={tuned_model_id}", content)
                    else:
                        content += f"\nSOVEREIGN_FINE_TUNED_MODEL={tuned_model_id}\n"
                    env_path.write_text(content)
                    logger.info(f"💾 Updated .env.local with SOVEREIGN_FINE_TUNED_MODEL={tuned_model_id}")
                return True
            elif state in ["FAILED", "CANCELLED"]:
                logger.error(f"❌ Fine-tuning failed with state: {state}")
                return False
                
            time.sleep(30)

            
    except Exception as e:
        logger.error(f"❌ Error submitting fine-tuning job: {e}")
        return False

if __name__ == "__main__":
    run_gemini_fine_tuning()
