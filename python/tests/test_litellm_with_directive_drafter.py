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
    monkeypatch.setattr(module, "parse_preprocessor_output", lambda value, **kwargs: value)

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
        lambda message, state: (_ for _ in ()).throw(AssertionError("should not draft")),
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


def test_local_update_and_clarify_responses_skip_downstream_litellm_call(monkeypatch) -> None:
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
    monkeypatch.setattr(module, "parse_preprocessor_output", lambda value, **kwargs: value)

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
