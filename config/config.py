from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Config(BaseModel):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY")

    # Память разговора (services/context.py)
    SUMMARY_CONTEXT_MAX_CHARS: int = int(os.getenv("SUMMARY_CONTEXT_MAX_CHARS") or "600")
    SUMMARY_CONTEXT_TTL_MINUTES: float = float(os.getenv("SUMMARY_CONTEXT_TTL_MINUTES") or "15")

config = Config()
