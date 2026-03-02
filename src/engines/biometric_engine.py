import os
import time
import logging
from typing import Optional, Dict
from threading import Thread
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BiometricEngine")

class BiometricEngine:
    """
    Bayesian Biometric Bridge
    Receives real-time Heart Rate and HRV data from Apple Health (via Webhook).
    """
    def __init__(self, port: int = 8080):
        self.port = port
        self.app = FastAPI(title="Bayesian Biometric Bridge")
        self.current_bpm: float = 70.0  # Baseline
        self.current_hrv: float = 50.0  # Baseline (SDNN)
        self.last_update: float = 0
        
        self.setup_routes()

    def setup_routes(self):
        @self.app.post("/webhook")
        async def handle_health_data(request: Request, background_tasks: BackgroundTasks):
            """
            Endpoint for Health Auto Export or similar apps.
            Expects JSON payload with metrics.
            """
            try:
                data = await request.json()
                
                # Format 1: Siri Shortcut / Custom (Direct Bridge)
                # Example: {"bpm": 95, "hrv": 45}
                if "bpm" in data or "hrv" in data:
                    if "bpm" in data:
                        self.current_bpm = float(data["bpm"])
                        logger.info(f"❤️ Heart Rate Updated (Direct): {self.current_bpm} BPM")
                    if "hrv" in data:
                        self.current_hrv = float(data["hrv"])
                        logger.info(f"📉 HRV Updated (Direct): {self.current_hrv} ms")
                    self.last_update = time.time()
                    return {"status": "success"}

                # Format 2: Health Auto Export (Original)
                # Health Auto Export structure: {"data": {"metrics": [...]}}
                metrics = data.get("data", {}).get("metrics", [])
                
                for metric in metrics:
                    name = metric.get("name")
                    qty = metric.get("qty")
                    
                    if name == "heart_rate":
                        self.current_bpm = float(qty)
                        logger.info(f"❤️ Heart Rate Updated: {self.current_bpm} BPM")
                    elif name == "heart_rate_variability":
                        self.current_hrv = float(qty)
                        logger.info(f"📉 HRV Updated: {self.current_hrv} ms")
                
                self.last_update = time.time()
                return {"status": "success"}
            except Exception as e:
                logger.error(f"Error parsing health data: {e}")
                return {"status": "error", "message": str(e)}

        @self.app.get("/status")
        async def get_status():
            return {
                "bpm": self.current_bpm,
                "hrv": self.current_hrv,
                "last_update_age": time.time() - self.last_update if self.last_update > 0 else -1,
                "physio_tilt": self.calculate_physio_tilt()
            }

    def calculate_physio_tilt(self) -> float:
        """
        Calculates a 1-10 tilt score purely from physiology.
        Uses Sovereign Logic if available; otherwise uses a basic threshold.
        """
        try:
            from src.sovereign_core.logic.biometric_math import calculate_sovereign_physio_tilt
            return calculate_sovereign_physio_tilt(self.current_bpm, self.current_hrv)
        except ImportError:
            # Public Lite Fallback
            if self.current_bpm > 100 or self.current_hrv < 25:
                return 7.0
            return 1.0

    def start_server(self):
        """Runs the FastAPI server in a background thread."""
        def run():
            uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="error")
            
        server_thread = Thread(target=run, daemon=True)
        server_thread.start()
        logger.info(f"🚀 Biometric Bridge active on port {self.port}")

if __name__ == "__main__":
    # Test execution
    engine = BiometricEngine()
    engine.start_server()
    
    print("Biometric Server running. Try sending a mock pulse:")
    print("curl -X POST http://localhost:8080/webhook -H 'Content-Type: application/json' -d '{\"data\": {\"metrics\": [{\"name\": \"heart_rate\", \"qty\": 110}, {\"name\": \"heart_rate_variability\", \"qty\": 20}]}}'")
    
    while True:
        time.sleep(5)
        print(f"Current Physio Tilt: {engine.calculate_physio_tilt()}")
