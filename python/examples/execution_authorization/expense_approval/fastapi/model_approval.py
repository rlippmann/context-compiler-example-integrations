"""Minimal provider-backed approval claim helper for the FastAPI demo."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import cast

from context_compiler_example_integrations.examples._shared.litellm_request import (
    build_litellm_provider_kwargs,
)
from context_compiler_example_integrations.examples._shared.provider_mode import (
    print_startup_config,
    resolve_provider_config,
)


@dataclass(frozen=True)
class ModelApproval:
    decision: str
    message: str

    @property
    def is_approved(self) -> bool:
        return self.decision == "approved"


def _get_litellm_completion() -> Callable[..., object]:
    litellm_module = import_module("litellm")
    return cast(Callable[..., object], litellm_module.completion)


def _extract_response_content(response: object) -> str | None:
    if isinstance(response, Mapping):
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, Mapping):
                message = first.get("message")
                if isinstance(message, Mapping):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content

    choices_attr = getattr(response, "choices", None)
    if isinstance(choices_attr, list) and choices_attr:
        first = choices_attr[0]
        message_attr = getattr(first, "message", None)
        content_attr = getattr(message_attr, "content", None)
        if isinstance(content_attr, str):
            return content_attr

    return None


def classify_model_approval(message: str) -> str:
    normalized = message.strip().lower()
    if normalized.startswith("approved"):
        return "approved"
    if " approved" in f" {normalized} ":
        return "approved"
    return "not_approved"


def get_model_approval_claim(expense_summary: str) -> ModelApproval:
    """Return an approval-class claim from a live provider."""

    try:
        completion = _get_litellm_completion()
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "litellm is required. Install with: pip install litellm"
        ) from exc

    config = resolve_provider_config(default_model="openai/gpt-4o-mini")
    print_startup_config(config)

    prompt = (
        "You are an expense approver.\n"
        "Reply with a short decision line that starts with APPROVED or DENIED.\n"
        "Expense:\n"
        f"{expense_summary}"
    )
    kwargs: dict[str, object] = {
        **build_litellm_provider_kwargs(config),
        "messages": [{"role": "user", "content": prompt}],
    }

    response = completion(**kwargs)
    message = _extract_response_content(response)
    if message is None:
        raise RuntimeError("LiteLLM response missing choices[0].message.content")

    return ModelApproval(
        decision=classify_model_approval(message),
        message=message,
    )
