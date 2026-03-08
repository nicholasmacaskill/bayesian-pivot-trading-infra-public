import os
import subprocess
import logging
from datetime import datetime

logger = logging.getLogger("VoiceEngine")

class VoiceEngine:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or os.path.join(os.getcwd(), "results", "audio")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Available voices on macOS (typical): 'Daniel', 'Samantha', 'Alex'
        # 'Daniel' is a firm British voice, good for "Gatekeeper"
        self.default_voice = "Daniel"

    def generate_voice_note(self, text, filename=None, tone="Firm"):
        """
        Generates an audio file (.aiff) using the Mac 'say' command.
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gatekeeper_{timestamp}.aiff"
            
        output_path = os.path.join(self.output_dir, filename)
        
        # Tone mapping to voices (Mac native)
        voice = self.default_voice
        if tone == "Urgent":
            voice = "Alex" # Alex is very clear/standard
        elif tone == "Calm":
            voice = "Samantha" # Samantha is soft
            
        try:
            # cmd: say -v <voice> -o <path> <text>
            cmd = ["say", "-v", voice, "-o", output_path, text]
            subprocess.run(cmd, check=True)
            logger.info(f"Voice note generated: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate voice note: {e}")
            return None

    def prepare_verdict_audio(self, verdict_dict, tone="Firm"):
        """
        Formats a trading verdict into a spoken script.
        """
        verdict = verdict_dict.get('verdict', 'Unknown')
        reasoning = verdict_dict.get('reasoning', 'No reasoning provided.')
        
        script = f"Attention. Trader Audit complete. Verdict is: {verdict}. {reasoning}"
        
        return self.generate_voice_note(script, tone=tone)

if __name__ == "__main__":
    # Test
    ve = VoiceEngine()
    path = ve.generate_voice_note("Sovereign Gatekeeper online. I am monitoring your tilt levels.")
    print(f"Test audio saved to: {path}")
