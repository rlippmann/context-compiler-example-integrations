from types import MappingProxyType
from typing import Any

import pytest
from context_compiler import create_engine
from context_compiler.grammar import CanonicalDirective, DirectiveKind
from context_compiler_directive_drafter import (
    DirectiveDrafter,
    DraftResult,
    NoDirective,
    UnknownDirective,
)

from context_compiler_example_integrations.examples.prompt_construction.litellm import (
    with_directive_drafter as module,
)


def setup_function() -> None:
    return None


def test_directive_shaped_or_natural_language_input_is_drafted_before_engine_step(
    monkeypatch,
) -> None:
    compile_inputs: list[str] = []
    real_step = create_engine().step

    engine = create_engine()

    def step_with_capture(user_input: str):
        compile_inputs.append(user_input)
        return real_step(user_input)

    monkeypatch.setattr(engine, "step", step_with_capture)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: "use docker"),
    )

    result = module.handle_turn(
        "please use docker", engine, approval_handler=lambda _directive: True
    )

    assert result == "State updated."
    assert compile_inputs == ["use docker"]


def test_rejected_canonical_directive_does_not_call_engine_step_or_mutate_state(
    monkeypatch,
) -> None:
    engine = create_engine()
    compile_inputs: list[str] = []
    real_step = engine.step

    def step_with_capture(user_input: str):
        compile_inputs.append(user_input)
        return real_step(user_input)

    monkeypatch.setattr(engine, "step", step_with_capture)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: "use docker"),
    )
    llm_calls: list[list[dict[str, str]]] = []

    def should_not_call(messages: list[dict[str, str]]) -> str:
        llm_calls.append(messages)
        return "should not be called"

    monkeypatch.setattr(module, "_call_litellm", should_not_call)

    result = module.handle_turn(
        "please use docker", engine, approval_handler=lambda _directive: False
    )

    assert compile_inputs == []
    assert result == "Directive rejected. No state change applied."
    assert llm_calls == []
    assert engine.policies == {}
    assert engine.premise is None


def test_no_directive_keeps_normal_flow(monkeypatch) -> None:
    engine = create_engine()
    compile_inputs: list[str] = []
    llm_calls: list[list[dict[str, str]]] = []
    real_step = engine.step

    def step_with_capture(user_input: str):
        compile_inputs.append(user_input)
        return real_step(user_input)

    monkeypatch.setattr(engine, "step", step_with_capture)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: None),
    )

    def downstream(messages: list[dict[str, str]]) -> str:
        llm_calls.append(messages)
        return "stubbed reply"

    monkeypatch.setattr(module, "_call_litellm", downstream)

    result = module.handle_turn("hello there", engine)

    assert compile_inputs == []
    assert result == "stubbed reply"
    assert len(llm_calls) == 1


def test_unknown_directive_keeps_normal_flow(monkeypatch) -> None:
    engine = create_engine()
    compile_inputs: list[str] = []
    llm_calls: list[list[dict[str, str]]] = []
    real_step = engine.step

    def step_with_capture(user_input: str):
        compile_inputs.append(user_input)
        return real_step(user_input)

    monkeypatch.setattr(engine, "step", step_with_capture)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: "use docker and prohibit peanuts"),
    )

    def downstream(messages: list[dict[str, str]]) -> str:
        llm_calls.append(messages)
        return "stubbed reply"

    monkeypatch.setattr(module, "_call_litellm", downstream)

    result = module.handle_turn("please use docker", engine)

    assert compile_inputs == []
    assert result == "stubbed reply"
    assert len(llm_calls) == 1


def test_extract_drafted_text_observes_draft_result_behavior() -> None:
    drafter = DirectiveDrafter(fallback=lambda _message: "use docker")
    drafted_result = drafter.draft_directive("please use docker")

    assert module._extract_drafted_text(drafted_result) == "use docker"

    no_directive_result = DraftResult(
        source="test", result=NoDirective("not a directive")
    )

    assert module._extract_drafted_text(no_directive_result) is None

    unknown_directive_result = DraftResult(
        source="test", result=UnknownDirective("unresolved")
    )

    assert module._extract_drafted_text(unknown_directive_result) is None


def test_extract_drafted_text_only_applies_canonical_directive() -> None:
    drafted_result = DraftResult(
        source="test",
        result=CanonicalDirective(
            text="use docker",
            kind=DirectiveKind.USE_ITEM,
            operands=MappingProxyType({"item": "docker"}),
        ),
    )

    assert module._extract_drafted_text(drafted_result) == "use docker"


def test_local_update_responses_skip_downstream_litellm_call(
    monkeypatch,
) -> None:
    llm_calls: list[object] = []

    def should_not_call(messages: list[dict[str, str]]) -> str:
        llm_calls.append(messages)
        return "should not be called"

    monkeypatch.setattr(module, "_call_litellm", should_not_call)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: "use docker"),
    )

    update_engine = create_engine()
    update = module.handle_turn(
        "please use docker", update_engine, approval_handler=lambda _directive: True
    )

    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: None),
    )

    assert update == "State updated."
    assert llm_calls == []


def test_malformed_directive_like_input_falls_through_to_downstream_litellm(
    monkeypatch,
) -> None:
    llm_calls: list[object] = []

    def downstream(messages: list[dict[str, str]]) -> str:
        llm_calls.append(messages)
        return "downstream reply"

    monkeypatch.setattr(module, "_call_litellm", downstream)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: None),
    )

    clarify_engine = create_engine()
    clarify = module.handle_turn("set premise to concise replies", clarify_engine)

    assert clarify == "downstream reply"
    assert llm_calls


def test_call_litellm_requires_api_key_in_openai_mode(monkeypatch) -> None:
    monkeypatch.delenv("PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(module, "_get_litellm_completion", lambda: lambda **_: {})

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required in openai mode"):
        module._call_litellm([{"role": "user", "content": "hello"}])


def test_call_litellm_rejects_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER", "bedrock")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(module, "_get_litellm_completion", lambda: lambda **_: {})

    with pytest.raises(
        RuntimeError,
        match="Invalid PROVIDER value 'bedrock'. Allowed values: openai, ollama, openai_compatible",
    ):
        module._call_litellm([{"role": "user", "content": "hello"}])


def test_call_litellm_openai_compatible_requires_base_url(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER", "openai_compatible")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(module, "_get_litellm_completion", lambda: lambda **_: {})

    with pytest.raises(
        RuntimeError,
        match="OPENAI_BASE_URL is required when PROVIDER=openai_compatible.",
    ):
        module._call_litellm([{"role": "user", "content": "hello"}])


def test_call_litellm_base_url_override_wins_over_provider(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def completion(**kwargs: Any) -> dict[str, object]:
        seen.update(kwargs)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setenv("PROVIDER", "ollama")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.compat/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(module, "_get_litellm_completion", lambda: completion)

    assert module._call_litellm([{"role": "user", "content": "hello"}]) == "ok"
    assert seen["api_base"] == "https://example.compat/v1"
    assert "api_key" not in seen


def test_call_litellm_logs_startup_config_once(
    monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    from context_compiler_example_integrations.examples._shared import provider_mode

    provider_mode._STARTUP_LOGGED = False

    monkeypatch.setenv("MODEL", "openai/demo-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        module,
        "_get_litellm_completion",
        lambda: lambda **_: {"choices": [{"message": {"content": "ok"}}]},
    )

    with caplog.at_level("INFO"):
        assert module._call_litellm([{"role": "user", "content": "hello"}]) == "ok"
        assert module._call_litellm([{"role": "user", "content": "again"}]) == "ok"

    matches = [
        record
        for record in caplog.records
        if record.getMessage().startswith("litellm_config mode=openai_compatible")
    ]
    assert len(matches) == 1
    message = matches[0].getMessage()
    assert "base_url=http://localhost:11434/v1" in message
    assert "model=openai/demo-model" in message
    assert "source=OPENAI_BASE_URL override" in message


def test_preprocessor_model_defaults_to_model(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def completion(**kwargs: Any) -> dict[str, object]:
        seen.update(kwargs)
        return {"choices": [{"message": {"content": "use docker"}}]}

    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MODEL", "openai/main-model")
    monkeypatch.delenv("PREPROCESSOR_MODEL", raising=False)
    monkeypatch.setattr(module, "_get_litellm_completion", lambda: completion)
    monkeypatch.setattr(module, "get_converter_prompt", lambda: "prompt")

    assert module._llm_fallback_candidate("please use docker") == "use docker"
    assert seen["model"] == "openai/main-model"


def test_preprocessor_model_override_wins(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def completion(**kwargs: Any) -> dict[str, object]:
        seen.update(kwargs)
        return {"choices": [{"message": {"content": "use docker"}}]}

    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MODEL", "openai/main-model")
    monkeypatch.setenv("PREPROCESSOR_MODEL", "openai/preprocessor-model")
    monkeypatch.setattr(module, "_get_litellm_completion", lambda: completion)
    monkeypatch.setattr(module, "get_converter_prompt", lambda: "prompt")

    assert module._llm_fallback_candidate("please use docker") == "use docker"
    assert seen["model"] == "openai/preprocessor-model"


def test_fallback_accepts_structurally_valid_output_without_source_awareness(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MODEL", "openai/main-model")
    monkeypatch.delenv("PREPROCESSOR_MODEL", raising=False)
    monkeypatch.setattr(
        module,
        "_get_litellm_completion",
        lambda: (
            lambda **_: {
                "choices": [{"message": {"content": "set premise concise replies"}}]
            }
        ),
    )
    monkeypatch.setattr(module, "get_converter_prompt", lambda: "prompt")

    assert (
        module._llm_fallback_candidate("set premise to concise replies")
        == "set premise concise replies"
    )


def test_directive_shaped_malformed_inputs_can_fall_through_to_normal_turn_flow(
    monkeypatch,
) -> None:
    fallback_calls = 0

    def fallback(_message: str) -> str | None:
        nonlocal fallback_calls
        fallback_calls += 1
        return None

    monkeypatch.setattr(module, "_llm_fallback_candidate", fallback)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(
            fallback=module._llm_fallback_candidate,
            fallback_source="litellm_fallback",
        ),
    )
    monkeypatch.setattr(module, "_call_litellm", lambda _messages: "downstream reply")

    assert (
        module.handle_turn("use docker instead of", create_engine())
        == "downstream reply"
    )
    assert fallback_calls == 1


def test_compound_directives_fall_through_when_not_applied(monkeypatch) -> None:
    downstream_calls = 0

    def downstream(_messages: list[dict[str, str]]) -> str:
        nonlocal downstream_calls
        downstream_calls += 1
        return "downstream reply"

    monkeypatch.setattr(module, "_call_litellm", downstream)
    monkeypatch.setattr(
        module,
        "_DIRECTIVE_DRAFTER",
        DirectiveDrafter(fallback=lambda _message: "use docker and prohibit peanuts"),
    )

    result = module.handle_turn(
        "please use docker and prohibit peanuts",
        create_engine(),
    )

    assert result == "downstream reply"
    assert downstream_calls == 1


def test_handle_turn_has_no_session_or_resume_behavior(monkeypatch) -> None:
    monkeypatch.setattr(module, "_call_litellm", lambda _messages: "ok")
    monkeypatch.setattr(module, "_preprocess_user_input", lambda _text: None)

    engine = create_engine()

    assert module.handle_turn("hello", engine) == "ok"
