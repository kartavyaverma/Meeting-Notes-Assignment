"""Configuration from environment variables, optionally loaded from a .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple

DEFAULT_MODEL = "gemini-3.8-flash"
REPO_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    """Missing or invalid setup. The message says how to fix it."""


def load_dotenv(start: Optional[Path] = None) -> Optional[Path]:
    """Load KEY=VALUE pairs from `.env` in `start` (default: the current directory) or the repo root.

    Variables already set in the environment always win, so a shell or scheduler can override the file.
    Returns the file that was loaded, if any.
    """
    for directory in ((start or Path.cwd()).resolve(), REPO_ROOT):
        candidate = directory / ".env"
        if candidate.is_file():
            for key, value in _parse_dotenv(candidate.read_text(encoding="utf-8-sig")):
                os.environ.setdefault(key, value)
            return candidate
    return None


def _parse_dotenv(text: str) -> Iterator[Tuple[str, str]]:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, value = line.split("=", 1)
        yield key.strip(), value.strip().strip("\"'")


def _get(name: str) -> str:
    """An environment value, treating unfilled `.env.example` placeholders as unset."""
    value = os.environ.get(name, "").strip()
    return "" if value.lower().startswith("your-") else value


def _price(name: str) -> Optional[float]:
    value = _get(name)
    if not value:
        return None
    try:
        price = float(value)
    except ValueError:
        raise ConfigError(f"{name} must be a number (USD per 1M tokens), got {value!r}") from None
    if price < 0:
        raise ConfigError(f"{name} can't be negative")
    return price


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = ""
    gemini_model: str = DEFAULT_MODEL
    notion_token: str = ""
    notion_database_id: str = ""
    input_usd_per_m: Optional[float] = None
    output_usd_per_m: Optional[float] = None

    @classmethod
    def from_env(cls, *, need_gemini: bool = True, need_notion: bool = True) -> "Settings":
        """Build settings from the environment, failing with one clear message listing what's missing."""
        settings = cls(
            gemini_api_key=_get("GEMINI_API_KEY"),
            gemini_model=_get("GEMINI_MODEL") or DEFAULT_MODEL,
            notion_token=_get("NOTION_TOKEN"),
            notion_database_id=_get("NOTION_DATABASE_ID").replace("-", ""),
            input_usd_per_m=_price("GEMINI_INPUT_USD_PER_M"),
            output_usd_per_m=_price("GEMINI_OUTPUT_USD_PER_M"),
        )
        required = {}
        if need_gemini:
            required["GEMINI_API_KEY"] = settings.gemini_api_key
        if need_notion:
            required["NOTION_TOKEN"] = settings.notion_token
            required["NOTION_DATABASE_ID"] = settings.notion_database_id
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigError(f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill them in.")
        return settings
