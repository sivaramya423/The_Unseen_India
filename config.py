"""Central configuration for THE UNSEEN INDIA.

Secrets come from environment variables (a local .env file). They are never
hard-coded and never printed.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # harmless if the file does not exist

DATA_PATH = BASE_DIR / "data" / "opportunities.json"

# Used only when GROQ_MODEL is empty. This ID was listed as a production model
# on Groq's official models page on 2026-10-25, but whether YOUR key can use it
# is not guaranteed. Run `python scripts/check_groq.py` to see the models your
# key can actually call, then put one in .env.
DEFAULT_MODEL = "openai/gpt-oss-20b"

REQUEST_TIMEOUT_SECONDS = 30
MAX_COMPLETION_TOKENS = 900
RETRIEVAL_TOP_K = 5


def get_api_key() -> str:
    """Return the Groq API key from the environment ('' if missing)."""
    return os.getenv("GROQ_API_KEY", "").strip()


def get_model() -> str:
    """Return the configured model ID, or the documented default."""
    return os.getenv("GROQ_MODEL", "").strip() or DEFAULT_MODEL
