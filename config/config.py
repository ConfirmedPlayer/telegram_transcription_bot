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

    # Провайдеры сводки (services/llm.py): оба OpenAI-совместимые
    LLM_PRIMARY_BASE_URL: str = os.getenv("LLM_PRIMARY_BASE_URL") or "https://api.cerebras.ai/v1"
    LLM_PRIMARY_API_KEY: str = os.getenv("LLM_PRIMARY_API_KEY") or ""
    LLM_PRIMARY_MODEL: str = os.getenv("LLM_PRIMARY_MODEL") or "qwen-3.8-27b"
    LLM_PRIMARY_EXTRA: str = os.getenv("LLM_PRIMARY_EXTRA") or '{"reasoning_effort": "none"}'
    LLM_FALLBACK_BASE_URL: str = os.getenv("LLM_FALLBACK_BASE_URL") or "https://api.groq.com/openai/v1"
    LLM_FALLBACK_API_KEY: str = os.getenv("LLM_FALLBACK_API_KEY") or ""
    LLM_FALLBACK_MODEL: str = os.getenv("LLM_FALLBACK_MODEL") or "qwen/qwen3.8-27b"
    LLM_FALLBACK_EXTRA: str = os.getenv("LLM_FALLBACK_EXTRA") or '{"reasoning_effort": "none"}'

    # Сводка: пороги и бюджеты (services/summary.py)
    SUMMARY_MIN_WORDS: int = int(os.getenv("SUMMARY_MIN_WORDS") or "100")
    CONTEXT_MIN_WORDS: int = int(os.getenv("CONTEXT_MIN_WORDS") or "1")
    SUMMARY_TOTAL_TIMEOUT: float = float(os.getenv("SUMMARY_TOTAL_TIMEOUT") or "15")
    SUMMARY_MAX_OUTPUT_TOKENS: int = int(os.getenv("SUMMARY_MAX_OUTPUT_TOKENS") or "350")
    SUMMARY_MAX_INPUT_CHARS: int = int(os.getenv("SUMMARY_MAX_INPUT_CHARS") or "12000")

config = Config()
