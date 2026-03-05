import wave
import struct
import math
import os
import subprocess
import time
import logging
from threading import Thread

logger = logging.getLogger("NeuroModulator")

class NeuroModulator:
    """
    Sovereign Neuro-Modulation Engine.
    Generates binaural beats based on trader state to regulate psychology.
    
    Frequencies (Standard ICT Neuro-Layer):
    - Alpha (10Hz): Flow / Baseline.
    - Theta (6Hz): Stress Recovery / Tilt Mitigation.
    - Beta (20Hz): Alertness / Boredom combat.
    - Gamma (40Hz): Intensity / High-Confluence execution.
    """
    
    FREQUENCIES = {
        "ALPHA": (200, 210),  # 10Hz diff
        "THETA": (200, 206),  # 6Hz diff
        "BETA":  (200, 220),  # 20Hz diff
        "GAMMA": (200, 240)   # 40Hz diff
    }

    def __init__(self):
        self.current_state = "ALPHA"
        self.volume = 0.3
        self.is_playing = False
        self._playback_process = None
        self.tmp_path = "/tmp/sovereign_binaural.wav"

    def generate_binaural_wav(self, left_freq, right_freq, duration=300):
        """Generates a stereo WAV file with binaural frequencies."""
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        
        with wave.open(self.tmp_path, 'w') as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)   # 2 bytes per sample
            wav_file.setframerate(sample_rate)
            
            for i in range(n_samples):
                t = float(i) / sample_rate
                
                # Left channel
                left_val = math.sin(2 * math.pi * left_freq * t)
                # Right channel
                right_val = math.sin(2 * math.pi * right_freq * t)
                
                # Apply volume and convert to 16-bit signed int
                left_int = int(left_val * 32767 * self.volume)
                right_int = int(right_val * 32767 * self.volume)
                
                data = struct.pack('<hh', left_int, right_int)
                wav_file.writeframesraw(data)
        
        return self.tmp_path

    def set_state(self, state: str):
        """Changes the audio state based on psychology metrics."""
        state = state.upper()
        if state not in self.FREQUENCIES:
            logger.warning(f"Unknown modulation state: {state}")
            return

        if state == self.current_state and self.is_playing:
            return

        logger.info(f"🧠 NEURO-MODULATION: Switching to {state} state.")
        self.current_state = state
        self._refresh_audio()

    def _refresh_audio(self):
        """Regenerates and restarts playback."""
        self.stop()
        
        left, right = self.FREQUENCIES[self.current_state]
        self.generate_binaural_wav(left, right)
        
        # Start afplay in background
        self._playback_process = subprocess.Popen(
            ["afplay", self.tmp_path, "--loop"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.is_playing = True

    def stop(self):
        """Stops audio playback."""
        if self._playback_process:
            self._playback_process.terminate()
            self._playback_process = None
        self.is_playing = False

    def modulate_by_metrics(self, bpm, win_rate, bias_strength, setups_found):
        """
        Decision Logic for Neuro-States.
        """
        # 1. Stress Gate
        if bpm > 100 or win_rate < 0.3:
            self.set_state("THETA")
            return

        # 2. Intensity Gate
        if setups_found > 0 or bias_strength > 1.5:
            self.set_state("GAMMA")
            return

        # 3. Alertness Gate
        if bias_strength < 0.5:
            self.set_state("BETA")
            return

        # 4. Baseline
        self.set_state("ALPHA")

if __name__ == "__main__":
    # Local Test
    modulator = NeuroModulator()
    print("Testing ALPHA state...")
    modulator.set_state("ALPHA")
    time.sleep(5)
    print("Testing GAMMA state...")
    modulator.set_state("GAMMA")
    time.sleep(5)
    modulator.stop()
    print("Stopped.")
