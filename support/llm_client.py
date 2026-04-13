import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def _first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


LLM_API_KEY = _first_env("CHIMEGE_API_KEY", "OPENAI_API_KEY")
LLM_BASE_URL = _first_env("CHIMEGE_BASE_URL", "OPENAI_BASE_URL")

CHAT_MODEL = _first_env("CHIMEGE_CHAT_MODEL", "OPENAI_CHAT_MODEL", default="gpt-4o-mini")
INTENT_MODEL = _first_env("CHIMEGE_INTENT_MODEL", default=CHAT_MODEL)
EMBED_MODEL = _first_env("CHIMEGE_EMBED_MODEL", "OPENAI_EMBED_MODEL", default="text-embedding-3-small")


# Chimege can be used here if it exposes an OpenAI-compatible endpoint.
if LLM_BASE_URL:
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
else:
    client = OpenAI(api_key=LLM_API_KEY)
