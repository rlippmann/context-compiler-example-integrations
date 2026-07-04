"""Tiny shared helper for LiteLLM live-validation request kwargs."""

from __future__ import annotations

from typing import Literal, TypedDict


class ProviderConfigLike(TypedDict):
    mode: Literal["openai", "ollama", "openai_compatible"]
    source: str
    base_url: str
    model: str
    api_key: str | None


class LiteLLMProviderKwargs(TypedDict, total=False):
    model: str
    api_base: str
    api_key: str
    temperature: float
    drop_params: bool


def build_litellm_provider_kwargs(
    config: ProviderConfigLike,
) -> LiteLLMProviderKwargs:
    """Return LiteLLM-safe provider/model kwargs for live validations."""

    model = _normalize_litellm_model_id(config)
    base_url = _config_value(config, "base_url")
    if base_url is None:
        raise RuntimeError("Provider config missing base_url.")

    kwargs: LiteLLMProviderKwargs = {
        "model": model,
        "api_base": base_url,
        "drop_params": True,
    }
    api_key = _config_value(config, "api_key")
    if api_key:
        kwargs["api_key"] = api_key
    kwargs["temperature"] = 0
    return kwargs


def _normalize_litellm_model_id(config: ProviderConfigLike) -> str:
    mode = _config_value(config, "mode")
    model = _config_value(config, "model")
    if model is None:
        raise RuntimeError("Provider config missing model.")
    if mode == "ollama" and "/" not in model:
        return f"ollama/{model}"
    return model


def _config_value(config: object, key: str) -> str | None:
    if isinstance(config, dict):
        value = config.get(key)
    else:
        value = getattr(config, key, None)
    return value if isinstance(value, str) or value is None else str(value)
