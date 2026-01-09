from smc_scanner import SMCScanner
from config import Config
from datetime import datetime

print("🔍 Inspecting Config...")
print(f"London Killzone: {Config.KILLZONE_LONDON}")
print(f"NY Killzone: {Config.KILLZONE_NY_CONTINUOUS}")

scanner = SMCScanner()
print(f"\n✅ Scanner Initialized.")

# Mock test for is_killzone
print("\nTesting Killzone Logic (Mock Times)...")
from unittest.mock import MagicMock
import datetime
import unittest

# Mock 8 AM (London)
mock_time = datetime.time(8, 0, 0) # 8:00 UTC
with unittest.mock.patch('datetime.datetime') as mock_date:
    mock_date.utcnow.return_value.time.return_value = mock_time
    mock_date.utcnow.return_value.hour = 8
    print(f"Time 08:00 UTC (London): {scanner.is_killzone()}")

# Mock 13 PM (NY)
mock_time = datetime.time(13, 0, 0)
with unittest.mock.patch('datetime.datetime') as mock_date:
    mock_date.utcnow.return_value.time.return_value = mock_time
    mock_date.utcnow.return_value.hour = 13
    print(f"Time 13:00 UTC (NY): {scanner.is_killzone()}")

# Mock 6 AM (Dead Zone)
        # Re-implementing mock logic manually since imports are tricky in one-off scripts
class MockScanner(SMCScanner):
    def test_time(self, h):
        london = Config.KILLZONE_LONDON
        if london and (london[0] <= h < london[1]): return True
        ny = Config.KILLZONE_NY_CONTINUOUS
        if ny and (ny[0] <= h < ny[1]): return True
        return False

ms = MockScanner()
print(f"08:00 (London): {ms.test_time(8)}")
print(f"13:00 (NY): {ms.test_time(13)}")
print(f"06:00 (Dead): {ms.test_time(6)}")
