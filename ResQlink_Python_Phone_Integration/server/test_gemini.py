import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)
print("key set:", bool(os.getenv("GEMINI_API_KEY")), "| model:", os.getenv("GEMINI_MODEL") or "MISSING")

from gemini_chat import ask_gemini

try:
    print(ask_gemini("hi"))
except Exception as e:
    print("FAILED:", type(e).__name__, str(e)[:400])