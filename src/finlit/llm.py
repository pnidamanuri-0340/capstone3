"""Chat model factory.

Everything that needs an LLM goes through `get_chat_model`, so tests can swap
in a fake model with `set_model_override`. The provider (OpenAI, Google Gemini
or Anthropic Claude) is chosen by `Settings.provider`.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from finlit.config import Settings, get_settings

Role = Literal["agent", "router", "judge"]

_override: dict[str, BaseChatModel] = {}


def set_model_override(role: str, model: BaseChatModel | None) -> None:
    """Inject a model for a role (used by tests). Pass None to clear."""
    if model is None:
        _override.pop(role, None)
    else:
        _override[role] = model


def clear_overrides() -> None:
    _override.clear()


def get_chat_model(role: Role = "agent") -> BaseChatModel:
    if role in _override:
        return _override[role]
    settings = get_settings()
    settings.require_llm()
    if settings.provider == "openai":
        return _openai(settings, role)
    if settings.provider == "google":
        return _gemini(settings, role)
    return _claude(settings, role)


def _temperature(settings: Settings, role: str) -> float | None:
    return 0.0 if role in ("router", "judge") else settings.temperature


def _openai(settings: Settings, role: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    kwargs = dict(model=settings.model_for(role), api_key=settings.openai_api_key,
                  max_tokens=1024 if role == "router" else 2048, timeout=60, max_retries=3)
    temperature = _temperature(settings, role)
    if temperature is not None:
        kwargs["temperature"] = temperature
    return ChatOpenAI(**kwargs)


def _gemini(settings: Settings, role: str) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    model_name = settings.model_for(role)
    kwargs = dict(model=model_name, api_key=settings.google_api_key,
                  max_tokens=1024 if role == "router" else 4096, timeout=60, retries=3)
    temperature = _temperature(settings, role)
    # Gemini 3.x models use fixed sampling defaults and ignore temperature (with a warning).
    if temperature is not None and not model_name.startswith("gemini-3"):
        kwargs["temperature"] = temperature
    return ChatGoogleGenerativeAI(**kwargs)


def _claude(settings: Settings, role: str) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    common = dict(model=settings.model_for(role), api_key=settings.anthropic_api_key,
                  max_tokens=1024 if role == "router" else 2048, timeout=60, max_retries=3)
    temperature = _temperature(settings, role)
    if temperature is None:
        return ChatAnthropic(**common)
    model = ChatAnthropic(**common, temperature=temperature)
    # Newer Claude models (e.g. Sonnet 5.5) reject non-default temperatures; drop it for them.
    check = getattr(model, "_assert_valid_model_configuration", None)
    if check is not None:
        try:
            check({})
        except ValueError:
            return ChatAnthropic(**common)
    return model
