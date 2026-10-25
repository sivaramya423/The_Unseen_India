"""Safe Groq connectivity test.

Run from the project folder:   python scripts/check_groq.py

It reads GROQ_API_KEY and GROQ_MODEL from your .env file, asks Groq which models
your key can use, and tells you whether your configured model is among them.
It never prints your key and sends no chat message.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from services.groq_service import check_connection  # noqa: E402


def main() -> int:
    print("API key found in environment:", "yes" if config.get_api_key() else "NO")
    print("Configured model:", config.get_model())
    result = check_connection()
    print(result.message)
    if result.ok:
        print("\nModels your key can see:")
        for model_id in result.details["models"]:
            print("  -", model_id)
        print("\nSet GROQ_MODEL in .env to one of the chat models above (not whisper or guard models).")
        return 0
    print("\nProblem type:", result.error_kind)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
