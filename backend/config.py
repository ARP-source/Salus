import os
from dotenv import load_dotenv

load_dotenv()

BOSONAI_API_KEY = os.environ.get("BOSONAI_API_KEY", "")
EIGEN_API_KEY = os.environ.get("EIGEN_API_KEY", "")
PORT = int(os.environ.get("PORT", "8000"))

# Boson Constants
BOSON_BASE_URL = "https://hackathon.boson.ai/v1"
BOSON_MODEL_PRIMARY = "higgs-audio-understanding-v3.5-Hackathon"
BOSON_MODEL_FALLBACK = "higgs-audio-understanding-v3-Hackathon"

# Audio Constants for VAD
VAD_THRESHOLD = 0.55
VAD_MIN_SPEECH_MS = 125
VAD_MIN_SILENCE_MS = 200
VAD_SPEECH_PAD_MS = 300
