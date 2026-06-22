import asyncio
import builtins
import importlib.util
import sys
import types
from pathlib import Path

import pytest

MODULE_PATH = (
    Path("/Users/rlippmann/Source/context-compiler-example-integrations")
    / "python"
    / "reference_integrations"
    / "openwebui_pipe"
    / "open_webui_pipe_with_directive_drafter.py"
)


def _load_module(module_name: str, monkeypatch: pytest.MonkeyPatch):
    fastapi_mod = types.ModuleType("fastapi")

    class _Request:
        pass

    fastapi_mod.Request = _Request

    open_webui_mod = types.ModuleType("open_webui")
    open_webui_models_mod = types.ModuleType("open_webui.models")
    open_webui_models_users_mod = types.ModuleType("open_webui.models.users")
    open_webui_utils_mod = types.ModuleType("open_webui.utils")
    open_webui_utils_chat_mod = types.ModuleType("open_webui.utils.chat")
    open_webui_utils_models_mod = types.ModuleType("open_webui.utils.models")

    class _Users:
        @staticmethod
        def get_user_by_id(user_id: object) -> dict[str, object]:
            return {"id": user_id}

    async def _chat_completion(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        return {"choices": [{"message": {"content": payload.get("_mock_content", "")}}]}

    async def _all_models(_: object, user: object = None) -> list[dict[str, str]]:
        del user
        return [{"id": "base-model"}, {"id": "prep-model"}, {"id": "pipe-model"}]

    open_webui_models_users_mod.Users = _Users
    open_webui_utils_chat_mod.generate_chat_completion = _chat_completion
    open_webui_utils_models_mod.get_all_models = _all_models

    monkeypatch.setitem(sys.modules, "fastapi", fastapi_mod)
    monkeypatch.setitem(sys.modules, "open_webui", open_webui_mod)
    monkeypatch.setitem(sys.modules, "open_webui.models", open_webui_models_mod)
    monkeypatch.setitem(sys.modules, "open_webui.models.users", open_webui_models_users_mod)
    monkeypatch.setitem(sys.modules, "open_webui.utils", open_webui_utils_mod)
    monkeypatch.setitem(sys.modules, "open_webui.utils.chat", open_webui_utils_chat_mod)
    monkeypatch.setitem(sys.modules, "open_webui.utils.models", open_webui_utils_models_mod)

    real_import = builtins.__import__

    def _guarded_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "pydantic":
            raise ModuleNotFoundError("No module named 'pydantic'")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._ENGINES_BY_CHAT_KEY.clear()
    module._CHECKPOINTS_BY_CHAT_KEY.clear()
    return module


def test_directive_drafting_runs_before_compiler_step(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_before_step", monkeypatch)
    compile_inputs: list[str] = []

    class FakeEngine:
        def __init__(self) -> None:
            self.state = {"premise": None, "policies": {}, "version": 2}

        def has_pending_clarification(self) -> bool:
            return False

        def step(self, user_input: str) -> dict[str, object]:
            compile_inputs.append(user_input)
            self.state = {"premise": None, "policies": {"docker": "use"}, "version": 2}
            return {"kind": "update", "state": self.state}

        def export_checkpoint_json(self) -> str:
            return '{"checkpoint_version":1,"authoritative_state":{"premise":null,"policies":{"docker":"use"},"version":2},"pending":null}'

    monkeypatch.setattr(module, "create_engine", lambda: FakeEngine())

    async def fake_preprocess(*args, **kwargs):
        return "use docker", None

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", fake_preprocess)

    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "please use docker"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-before-step",
        )
    )

    assert result == "State updated: Use docker."
    assert compile_inputs == ["use docker"]


def test_pending_clarification_bypasses_drafting(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_pending", monkeypatch)
    compile_inputs: list[str] = []

    class FakeEngine:
        def __init__(self) -> None:
            self._pending = True
            self.state = {"premise": None, "policies": {}, "version": 2}

        def has_pending_clarification(self) -> bool:
            return self._pending

        def step(self, user_input: str) -> dict[str, object]:
            compile_inputs.append(user_input)
            self._pending = False
            self.state = {"premise": None, "policies": {"docker": "use"}, "version": 2}
            return {"kind": "update", "state": self.state}

        def export_checkpoint_json(self) -> str:
            return '{"checkpoint_version":1,"authoritative_state":{"premise":null,"policies":{"docker":"use"},"version":2},"pending":null}'

    monkeypatch.setattr(module, "create_engine", lambda: FakeEngine())

    async def should_not_run(*args, **kwargs):
        raise AssertionError("drafting should be bypassed")

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", should_not_run)

    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "yes"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-pending",
        )
    )

    assert result == "State updated."
    assert compile_inputs == ["yes"]


def test_fallback_to_raw_input_path_preserves_host_behavior(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_raw", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward

    async def no_draft(*args, **kwargs):
        return None, None

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", no_draft)

    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-raw",
        )
    )

    assert result == {"choices": [{"message": {"content": "downstream"}}]}
    assert forwarded[0]["messages"] == [{"role": "user", "content": "hello"}]


def test_local_update_and_clarify_responses_skip_downstream_model(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_local", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def update_draft(*args, **kwargs):
        return "use docker", None

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", update_draft)
    update = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "please use docker"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-update",
        )
    )

    async def no_draft(*args, **kwargs):
        return None, None

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", no_draft)
    clarify = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "set premise to concise replies"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-clarify",
        )
    )

    assert update == "State updated: Use docker."
    assert clarify == "Invalid premise syntax.\nUse 'set premise <value>'."
    assert forwarded == []


def test_passthrough_injects_exactly_one_cc_state_system_message_when_state_exists(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_passthrough", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"
    chat_id = "chat-passthrough"

    async def update_draft(*args, **kwargs):
        return "use docker", None

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", update_draft)
    asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "please use docker"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )

    async def no_draft(*args, **kwargs):
        return None, None

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", no_draft)
    result = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [
                    {"role": "system", "content": "original system"},
                    {"role": "user", "content": "hello"},
                ],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )

    assert result == {"choices": [{"message": {"content": "downstream"}}]}
    cc_messages = [
        message
        for message in forwarded[0]["messages"]
        if message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and message["content"].startswith("[[cc_state]]")
    ]
    assert len(cc_messages) == 1


def test_preprocessor_model_defaults_to_base_model(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_model_default", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = None

    assert pipe._resolve_preprocessor_model_id("base-model") == "base-model"


def test_preprocessor_model_override_wins(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_model_override", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    assert pipe._resolve_preprocessor_model_id("base-model") == "prep-model"


def test_invalid_preprocessor_model_id_from_model_list(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_invalid_preprocessor_model", monkeypatch)
    pipe = module.Pipe()

    async def models(_: object, user: object = None) -> list[dict[str, str]]:
        del user
        return [{"id": "base-model"}]

    module.get_all_models = models

    error = asyncio.run(
        pipe._validate_configured_model_ids(
            request=object(),
            user_payload={"id": "u1"},
            base_model_id="base-model",
            preprocessor_model_id="missing-prep-model",
        )
    )

    assert error == (
        "Context Compiler pipe misconfigured: PREPROCESSOR_MODEL_ID was not found "
        "in Open WebUI models."
    )


def test_recursion_guard_for_preprocessor_model_id(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_recursion_guard", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "pipe-model"

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hi"}]},
            __user__={"id": "u1"},
            __request__=object(),
        )
    )

    assert result == (
        "Context Compiler pipe misconfigured: PREPROCESSOR_MODEL_ID must not "
        "match the selected pipe model id to avoid recursive routing."
    )


def test_debug_mode_missing_base_model_returns_deterministic_message(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_debug_missing_base", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = None
    pipe.valves.PREPROCESSOR_MODEL_ID = None
    pipe.valves.ALLOW_MISSING_BASE_MODEL_FOR_DEBUG = True

    async def no_draft(*args, **kwargs):
        return None, None

    monkeypatch.setattr(module.Pipe, "_preprocess_user_input", no_draft)

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-debug-missing-base",
        )
    )

    assert result == "Context Compiler debug mode: BASE_MODEL_ID is empty; skipping model passthrough."


def test_preprocessor_model_not_found_is_normalized(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_preprocessor_not_found", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def generate(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        if payload.get("model") == "prep-model":
            return {"error": {"message": "model not found"}}
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = generate
    module.preprocess_heuristic = lambda _text: {"outcome": "no_directive", "directive": None}

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-preprocessor-not-found",
        )
    )

    assert result == (
        "Context Compiler pipe misconfigured: PREPROCESSOR_MODEL_ID is invalid or "
        "not configured in Open WebUI. Configure a valid model id in "
        "Admin Panel → Settings → Models."
    )


def test_fallback_uses_preprocessor_model_then_forward_uses_base_model(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_fallback_routing", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"
    calls: list[str] = []

    async def generate(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        calls.append(str(payload.get("model", "")))
        if len(calls) == 1:
            return {"choices": [{"message": {"content": "no_directive"}}]}
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = generate
    module.preprocess_heuristic = lambda _text: {"outcome": "no_directive", "directive": None}

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "please use docker"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-routing",
        )
    )

    assert result == {"choices": [{"message": {"content": "downstream"}}]}
    assert calls == ["prep-model", "base-model"]


def test_validate_configured_model_ids_supports_async_user_lookup(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_async_user_lookup", monkeypatch)
    pipe = module.Pipe()

    async def get_user_by_id(user_id: object) -> dict[str, object]:
        return {"id": user_id}

    monkeypatch.setattr(module.Users, "get_user_by_id", get_user_by_id)

    error = asyncio.run(
        pipe._validate_configured_model_ids(
            request=object(),
            user_payload={"id": "u1"},
            base_model_id="base-model",
            preprocessor_model_id="prep-model",
        )
    )

    assert error is None
