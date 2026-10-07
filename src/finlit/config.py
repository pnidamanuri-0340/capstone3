"""Application settings loaded from environment variables / a `.env` file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when a required setting is missing; message is safe to show users."""


PROVIDERS = {
    "openai": {"label": "OpenAI", "key": "OPENAI_API_KEY", "url": "https://platform.openai.com/api-keys"},
    "google": {"label": "Google Gemini", "key": "GOOGLE_API_KEY", "url": "https://aistudio.google.com/apikey"},
    "anthropic": {"label": "Anthropic Claude", "key": "ANTHROPIC_API_KEY",
                  "url": "https://console.anthropic.com/"},
}
AUTO_ORDER = ("openai", "google", "anthropic")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # auto = first provider with a key, in AUTO_ORDER (OpenAI, then Gemini, then Claude).
    provider_setting: Literal["auto", "openai", "google", "anthropic"] = Field(
        default="auto", alias="FINLIT_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    alpha_vantage_api_key: str = Field(default="", alias="ALPHA_VANTAGE_API_KEY")
    alpha_vantage_mock: bool = Field(default=False, alias="ALPHA_VANTAGE_MOCK")

    # OpenAI models (provider=openai)
    openai_agent_model: str = Field(default="gpt-4o", alias="FINLIT_OPENAI_AGENT_MODEL")
    openai_router_model: str = Field(default="gpt-4o-mini", alias="FINLIT_OPENAI_ROUTER_MODEL")
    # Claude models (provider=anthropic)
    agent_model: str = Field(default="claude-sonnet-5-5", alias="FINLIT_AGENT_MODEL")
    router_model: str = Field(default="claude-haiku-4-5-20251001", alias="FINLIT_ROUTER_MODEL")
    # Gemini models (provider=google)
    gemini_agent_model: str = Field(default="gemini-3.5-flash", alias="FINLIT_GEMINI_AGENT_MODEL")
    gemini_router_model: str = Field(default="gemini-3.5-flash-lite", alias="FINLIT_GEMINI_ROUTER_MODEL")
    # Empty = model default. Ignored automatically for models that don't support it.
    temperature: float | None = Field(default=None, alias="FINLIT_TEMPERATURE")

    data_dir: Path = Field(default=Path("./data"), alias="FINLIT_DATA_DIR")
    embeddings: Literal["onnx", "hash"] = Field(default="onnx", alias="FINLIT_EMBEDDINGS")
    rag_top_k: int = Field(default=4, alias="FINLIT_RAG_TOP_K")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("temperature", mode="before")
    @classmethod
    def _blank_temperature(cls, v):
        return None if v in ("", None) else v

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "finlit.sqlite"

    @property
    def checkpoint_path(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    @property
    def use_mock_market_data(self) -> bool:
        return self.alpha_vantage_mock or not self.alpha_vantage_api_key

    def _key(self, provider: str) -> str:
        return getattr(self, f"{provider}_api_key").strip()

    @property
    def provider(self) -> str:
        if self.provider_setting != "auto":
            return self.provider_setting
        return next((p for p in AUTO_ORDER if self._key(p)), "anthropic")

    @property
    def llm_key_name(self) -> str:
        return PROVIDERS[self.provider]["key"]

    @property
    def provider_label(self) -> str:
        return PROVIDERS[self.provider]["label"]

    def model_for(self, role: str) -> str:
        prefix = {"openai": "openai_", "google": "gemini_", "anthropic": ""}[self.provider]
        return getattr(self, f"{prefix}{'router' if role == 'router' else 'agent'}_model")

    @property
    def has_llm(self) -> bool:
        return bool(self._key(self.provider))

    def require_llm(self) -> None:
        if not self.has_llm:
            raise ConfigError(
                f"{self.llm_key_name} is not set. Add it to your .env file "
                f"(get one at {PROVIDERS[self.provider]['url']})."
            )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


def _env_file_stamp() -> float | None:
    try:
        return Path(".env").stat().st_mtime
    except OSError:
        return None


@lru_cache(maxsize=1)
def _load_settings(_stamp: float | None) -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Cached settings, reloaded automatically when the `.env` file changes on disk,
    so key edits take effect without restarting the app."""
    return _load_settings(_env_file_stamp())


def reset_settings_cache() -> None:
    _load_settings.cache_clear()
