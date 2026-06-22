import json
from typing import Any, cast

import pytest
from context_compiler import create_engine

from python.examples.prompt_construction.litellm import with_directive_drafter as module


def setup_function() -> None:
    module._CHECKPOINTS_BY_SESSION_KEY.clear()
    module._RESTORED_ENGINE_BY_SESSION_KEY.clear()


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
        "preprocess_heuristic",
        lambda message: {
            "outcome": module.PREPROCESS_OUTCOME_DIRECTIVE,
            "directive": "use docker",
        },
    )
    monkeypatch.setattr(
        module, "parse_preprocessor_output", lambda value, **kwargs: value
    )

    result = module.handle_turn("please use docker", engine)

    assert result == "State updated: Use docker."
    assert compile_inputs == ["use docker"]


def test_pending_clarification_bypasses_drafting(monkeypatch) -> None:
    engine = create_engine()
    first = engine.step("use docker instead of kubectl")
    assert str(first["kind"]) == "clarify"

    compile_inputs: list[str] = []
    real_step = engine.step

    def step_with_capture(user_input: str):
        compile_inputs.append(user_input)
        return real_step(user_input)

    monkeypatch.setattr(engine, "step", step_with_capture)
    monkeypatch.setattr(
        module,
        "_preprocess_user_input",
        lambda message, state: (_ for _ in ()).throw(
            AssertionError("should not draft")
        ),
    )

    second = module.handle_turn("yes", engine)

    assert second == "State updated: Use docker."
    assert compile_inputs == ["yes"]


def test_unknown_or_unsafe_drafting_falls_back_to_raw_input(monkeypatch) -> None:
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
        "preprocess_heuristic",
        lambda message: {"outcome": "no_directive", "directive": None},
    )
    monkeypatch.setattr(module, "_llm_fallback_preprocess", lambda message, state: None)
    monkeypatch.setattr(
        module,
        "_call_litellm",
        lambda messages: llm_calls.append(messages) or "stubbed reply",
    )

    result = module.handle_turn("hello there", engine)

    assert compile_inputs == ["hello there"]
    assert result == "stubbed reply"
    assert len(llm_calls) == 1


def test_local_update_and_clarify_responses_skip_downstream_litellm_call(
    monkeypatch,
) -> None:
    llm_calls: list[object] = []
    monkeypatch.setattr(
        module,
        "_call_litellm",
        lambda messages: llm_calls.append(messages) or "should not be called",
    )
    monkeypatch.setattr(
        module,
        "preprocess_heuristic",
        lambda message: {
            "outcome": module.PREPROCESS_OUTCOME_DIRECTIVE,
            "directive": "use docker",
        },
    )
    monkeypatch.setattr(
        module, "parse_preprocessor_output", lambda value, **kwargs: value
    )

    update_engine = create_engine()
    update = module.handle_turn("please use docker", update_engine)

    monkeypatch.setattr(
        module,
        "preprocess_heuristic",
        lambda message: {"outcome": "no_directive", "directive": None},
    )
    monkeypatch.setattr(module, "_llm_fallback_preprocess", lambda message, state: None)
    clarify_engine = create_engine()
    clarify = module.handle_turn("set premise to concise replies", clarify_engine)

    assert update == "State updated: Use docker."
    assert clarify == "Invalid premise syntax.\nUse 'set premise <value>'."
    assert llm_calls == []


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
    import host_support.provider_mode as provider_mode

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
    monkeypatch.setattr(module, "render_prompt", lambda *_: "prompt")
    monkeypatch.setattr(
        module, "parse_preprocessor_output", lambda value, **_kwargs: value
    )

    assert module._llm_fallback_preprocess("please use docker", {}) == "use docker"
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
    monkeypatch.setattr(module, "render_prompt", lambda *_: "prompt")
    monkeypatch.setattr(
        module, "parse_preprocessor_output", lambda value, **_kwargs: value
    )

    assert module._llm_fallback_preprocess("please use docker", {}) == "use docker"
    assert seen["model"] == "openai/preprocessor-model"


def test_fallback_rejects_premise_near_miss_rewrites(monkeypatch) -> None:
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
    monkeypatch.setattr(module, "render_prompt", lambda *_: "prompt")

    assert module._llm_fallback_preprocess("set premise to concise replies", {}) is None


def test_directive_shaped_malformed_inputs_skip_fallback(monkeypatch) -> None:
    fallback_calls = 0
    downstream_calls = 0

    monkeypatch.setattr(
        module,
        "preprocess_heuristic",
        lambda _text: {"outcome": "no_directive", "directive": None},
    )

    def fallback(_message: str, _state: dict[str, object]) -> None:
        nonlocal fallback_calls
        fallback_calls += 1
        raise AssertionError("fallback should not run")

    def downstream(_messages: list[dict[str, str]]) -> str:
        nonlocal downstream_calls
        downstream_calls += 1
        raise AssertionError("downstream should not run")

    monkeypatch.setattr(module, "_llm_fallback_preprocess", fallback)
    monkeypatch.setattr(module, "_call_litellm", downstream)

    assert (
        module.handle_turn("use docker instead of", create_engine())
        == "Replacement requires both new and old items.\nUse 'use <new item> instead of <old item>' with non-empty values."
    )
    assert fallback_calls == 0
    assert downstream_calls == 0


@pytest.mark.parametrize(
    ("confirmation", "expected_policies", "expected_response"),
    [
        ("yes", {"kubectl": "use"}, "State updated: Use kubectl."),
        ("no thanks.", {}, "State unchanged."),
    ],
)
def test_checkpoint_resume_bypasses_preprocess_and_downstream_while_pending(
    monkeypatch,
    confirmation: str,
    expected_policies: dict[str, str],
    expected_response: str,
) -> None:
    preprocess_inputs: list[str] = []
    llm_calls = 0
    session_key = "resume-with-drafter"

    def preprocess_before_pending(text: str, _state: dict[str, object]) -> None:
        preprocess_inputs.append(text)
        return None

    def fail_preprocess(_text: str, _state: dict[str, object]) -> None:
        raise AssertionError("preprocess should be bypassed while pending")

    def downstream(_messages: list[dict[str, str]]) -> str:
        nonlocal llm_calls
        llm_calls += 1
        raise AssertionError("downstream model should not be called")

    monkeypatch.setattr(module, "_call_litellm", downstream)
    monkeypatch.setattr(module, "_preprocess_user_input", preprocess_before_pending)

    first_engine = create_engine()
    clarify = module.handle_turn(
        "use kubectl instead of docker",
        first_engine,
        session_key=session_key,
    )

    assert clarify == 'Did you mean to use "kubectl" instead?'
    assert preprocess_inputs == ["use kubectl instead of docker"]
    assert session_key in module._CHECKPOINTS_BY_SESSION_KEY

    monkeypatch.setattr(module, "_preprocess_user_input", fail_preprocess)
    resumed_engine = create_engine()
    resumed = module.handle_turn(confirmation, resumed_engine, session_key=session_key)

    assert resumed == expected_response
    assert llm_calls == 0
    assert resumed_engine.state == {
        "premise": None,
        "policies": expected_policies,
        "version": 2,
    }
    resumed_checkpoint = json.loads(module._CHECKPOINTS_BY_SESSION_KEY[session_key])
    assert resumed_checkpoint["pending"] is None


def test_checkpoint_restore_and_persist_by_session_key(monkeypatch) -> None:
    class FakeEngine:
        def __init__(
            self, kind: str, checkpoint_out: str, *, has_pending: bool = False
        ) -> None:
            self.kind = kind
            self.state: dict[str, object] = {
                "premise": None,
                "policies": {"peanuts": "prohibit"},
                "version": 2,
            }
            self._checkpoint_out = checkpoint_out
            self._has_pending = has_pending
            self.imported: list[str] = []
            self.export_calls = 0

        def import_checkpoint_json(self, payload: str) -> None:
            self.imported.append(payload)

        def export_checkpoint_json(self) -> str:
            self.export_calls += 1
            return self._checkpoint_out

        def export_checkpoint(self) -> dict[str, object]:
            pending: object = None
            if self._has_pending:
                pending = {
                    "kind": "replacement",
                    "replacement": {
                        "kind": "use_only",
                        "new_item": "kubectl",
                        "old_item": None,
                    },
                    "prompt_to_user": "confirm?",
                }
            return {
                "checkpoint_version": 1,
                "authoritative_state": self.state,
                "pending": pending,
            }

        def has_pending_clarification(self) -> bool:
            return self._has_pending

        def step(self, _text: str) -> dict[str, object]:
            if self.kind == "clarify":
                return {"kind": "clarify", "state": None, "prompt_to_user": "confirm?"}
            return {"kind": self.kind, "state": self.state}

    checkpoints = cast(dict[str, str], module._CHECKPOINTS_BY_SESSION_KEY)
    restored = cast(dict[str, int], module._RESTORED_ENGINE_BY_SESSION_KEY)
    checkpoints.clear()
    restored.clear()
    checkpoints["s1"] = "ckpt-in"
    monkeypatch.setattr(module, "_call_litellm", lambda _messages: "ok")
    monkeypatch.setattr(module, "_preprocess_user_input", lambda _text, _state: None)

    passthrough_engine = FakeEngine("passthrough", "ckpt-passthrough")
    assert module.handle_turn("hello", passthrough_engine, session_key="s1") == "ok"
    assert passthrough_engine.imported == ["ckpt-in"]
    assert passthrough_engine.export_calls == 0
    assert checkpoints["s1"] == "ckpt-in"

    update_engine = FakeEngine("update", "ckpt-update")
    assert (
        module.handle_turn("use docker", update_engine, session_key="s1")
        == "State updated: Use docker."
    )
    assert update_engine.imported == ["ckpt-in"]
    assert update_engine.export_calls == 1
    assert checkpoints["s1"] == "ckpt-update"

    clarify_engine = FakeEngine("clarify", "ckpt-clarify")
    assert (
        module.handle_turn(
            "use kubectl instead of docker", clarify_engine, session_key="s1"
        )
        == "confirm?"
    )
    assert clarify_engine.imported == ["ckpt-update"]
    assert clarify_engine.export_calls == 1
    assert checkpoints["s1"] == "ckpt-clarify"
