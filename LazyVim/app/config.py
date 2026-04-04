import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY") or os.getenv("NEWS_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
VIDEO_OUTPUT_DIR = os.getenv("VIDEO_OUTPUT_DIR", "generated_videos")
SD_TURBO_URL = os.getenv("SD_TURBO_URL", "http://127.0.0.1:7860/generate")

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"
