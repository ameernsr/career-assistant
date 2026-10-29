"""Settings from .env. The only place that reads secrets (NF-04)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    chat_model: str
    embed_model: str
    stt_model: str = ""
    tts_model: str = ""
    session_budget_usd: float = 0.5
    # USD per 1M tokens: {"model": [input, output]}. Unknown models are counted as 0 and flagged.
    prices: dict[str, list[float]] = field(default_factory=dict)


def load_settings() -> Settings:
    load_dotenv(ENV_FILE)  # explicit path: find_dotenv() breaks under stdin / some runners
    missing = [k for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "CHAT_MODEL", "EMBED_MODEL") if not os.getenv(k)]
    if missing:
        raise ConfigError(f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill it in.")
    try:
        prices = json.loads(os.getenv("MODEL_PRICES", "{}"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"MODEL_PRICES is not valid JSON: {exc}") from exc
    return Settings(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
        chat_model=os.environ["CHAT_MODEL"],
        embed_model=os.environ["EMBED_MODEL"],
        stt_model=os.getenv("STT_MODEL", ""),
        tts_model=os.getenv("TTS_MODEL", ""),
        session_budget_usd=float(os.getenv("SESSION_BUDGET_USD", "0.5")),
        prices=prices,
    )
