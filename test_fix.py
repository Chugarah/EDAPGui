from EDGraphicsSettings import EDGraphicsSettings
import logging

# Mock logger to avoid errors if EDlogger is not configured
logging.basicConfig()

try:
    print("Attempting to initialize EDGraphicsSettings...")
    gs = EDGraphicsSettings()
    print("Success: EDGraphicsSettings initialized.")
    print(f"Fullscreen mode: {gs.fullscreen_str}")
except Exception as e:
    print(f"Failed: {e}")
