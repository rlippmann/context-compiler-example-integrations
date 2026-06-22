import asyncio
import builtins
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

MODULE_PATH = (
    Path("/Users/rlippmann/Source/context-compiler-example-integrations")
    / "python"
    / "reference_integrations"
    / "openwebui_pipe"
    / "open_webui_pipe.py"
)


def _load_module_with_stubs(module_name: str, monkeypatch: pytest.MonkeyPatch):
    fastapi_mod = types.ModuleType("fastapi")

    class _Request:
        pass

    fastapi_mod.Request = _Request

    open_webui_mod = types.ModuleType("open_webui")
    open_webui_models_mod = types.ModuleType("open_webui.models")
    open_webui_models_users_mod = types.ModuleType("open_webui.models.users")
    open_webui_utils_mod = types.ModuleType("open_webui.utils")
    open_webui_utils_chat_mod = types.ModuleType("open_webui.utils.chat")

    class _Users:
        @staticmethod
        def get_user_by_id(user_id: object) -> dict[str, object]:
            return {"id": user_id}

    async def _chat_completion(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        return {"choices": [{"message": {"content": payload.get("_mock_content", "")}}]}

    open_webui_models_users_mod.Users = _Users
    open_webui_utils_chat_mod.generate_chat_completion = _chat_completion

    monkeypatch.setitem(sys.modules, "fastapi", fastapi_mod)
    monkeypatch.setitem(sys.modules, "open_webui", open_webui_mod)
    monkeypatch.setitem(sys.modules, "open_webui.models", open_webui_models_mod)
    monkeypatch.setitem(sys.modules, "open_webui.models.users", open_webui_models_users_mod)
    monkeypatch.setitem(sys.modules, "open_webui.utils", open_webui_utils_mod)
    monkeypatch.setitem(sys.modules, "open_webui.utils.chat", open_webui_utils_chat_mod)

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


def test_import_works_without_pydantic(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_import_no_pydantic", monkeypatch)
    pipe = module.Pipe()
    assert pipe.valves.BASE_MODEL_ID == ""


def test_missing_base_model_id_returns_deterministic_misconfiguration_message(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_missing_base_model", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = ""

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
        )
    )

    assert result == "Context Compiler pipe misconfigured: BASE_MODEL_ID is required."


def test_recursive_base_model_id_returns_deterministic_recursion_guard_message(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_recursion_guard", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "pipe-model"

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
        )
    )

    assert result == (
        "Context Compiler pipe misconfigured: BASE_MODEL_ID must not match "
        "the selected pipe model id to avoid recursive routing."
    )


def test_checkpoint_restore_and_persist_across_chat_ids(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_checkpoint_restore", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"

    first = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "use docker instead of kubectl"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-1",
        )
    )
    assert first == 'Did you mean to use "docker" instead?'
    checkpoint = module._CHECKPOINTS_BY_CHAT_KEY["chat-1"]

    module._ENGINES_BY_CHAT_KEY.clear()

    second = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "yes"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-1",
        )
    )
    other_chat = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "show state"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-2",
        )
    )

    assert second == "State updated."
    assert checkpoint != module._CHECKPOINTS_BY_CHAT_KEY["chat-1"]
    assert other_chat == "Premise: none\nUse: none\nProhibit: none\nPending clarification: no"


def test_normal_update_returns_local_ack_and_skips_downstream(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_update_local_ack", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"ok": True}

    module.generate_chat_completion = _forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "prohibit peanuts"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-update",
        )
    )

    assert result == "State updated: Prohibit peanuts."
    assert forwarded == []


def test_confirmation_resume_returns_local_ack_and_skips_downstream(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_confirmation_resume", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"ok": True}

    module.generate_chat_completion = _forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    chat_id = "chat-confirm"

    clarify = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "use docker instead of kubectl"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )
    resumed = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "yes"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )

    assert clarify == 'Did you mean to use "docker" instead?'
    assert resumed == "State updated."
    assert forwarded == []


def test_exact_show_state_is_local_and_non_exact_forwards_normally(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_show_state", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = _forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"

    exact = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "show state"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-show",
        )
    )
    non_exact = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "show state please"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-show",
        )
    )

    assert exact == "Premise: none\nUse: none\nProhibit: none\nPending clarification: no"
    assert non_exact == {"choices": [{"message": {"content": "downstream"}}]}
    assert len(forwarded) == 1


def test_near_miss_directive_clarify_returns_deterministic_text_and_skips_downstream(
    monkeypatch,
) -> None:
    module = _load_module_with_stubs("owui_near_miss", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = _forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "set premise to concise replies"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-near-miss",
        )
    )

    assert result == "Invalid premise syntax.\nUse 'set premise <value>'."
    assert forwarded == []


def test_passthrough_with_non_empty_state_injects_exactly_one_cc_state_system_message(
    monkeypatch,
) -> None:
    module = _load_module_with_stubs("owui_passthrough_inject", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = _forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    chat_id = "chat-passthrough-state"

    asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "use docker"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )
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
    system_messages = [
        message for message in forwarded[0]["messages"] if message.get("role") == "system"
    ]
    cc_messages = [
        message for message in system_messages if isinstance(message.get("content"), str) and message["content"].startswith("[[cc_state]]")
    ]
    assert len(cc_messages) == 1


def test_empty_state_passthrough_does_not_inject_compiler_state(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_passthrough_empty", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = _forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"

    asyncio.run(
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
            __chat_id__="chat-empty-state",
        )
    )

    assert forwarded[0]["messages"] == [
        {"role": "system", "content": "original system"},
        {"role": "user", "content": "hello"},
    ]


def test_repeated_passthrough_does_not_duplicate_compiler_owned_system_message(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_passthrough_dedupe", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = _forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    chat_id = "chat-dedupe"

    asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "use docker"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )
    first_body = {
        "model": "pipe-model",
        "messages": [
            {"role": "system", "content": "original system"},
            {"role": "user", "content": "hello"},
        ],
    }
    asyncio.run(
        pipe.pipe(first_body, __user__={"id": "u1"}, __request__=object(), __chat_id__=chat_id)
    )
    forwarded_messages = forwarded[-1]["messages"]
    second_body = {"model": "pipe-model", "messages": forwarded_messages}
    asyncio.run(
        pipe.pipe(second_body, __user__={"id": "u1"}, __request__=object(), __chat_id__=chat_id)
    )

    cc_messages = [
        message
        for message in forwarded[-1]["messages"]
        if message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and message["content"].startswith("[[cc_state]]")
    ]
    assert len(cc_messages) == 1


def test_model_not_found_is_normalized(monkeypatch) -> None:
    module = _load_module_with_stubs("owui_model_not_found", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"

    async def _forward(_: object, payload: dict[str, object], __: object) -> dict[str, object]:
        return {"error": {"message": "MODEL NOT FOUND"}}

    module.generate_chat_completion = _forward

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-model-not-found",
        )
    )

    assert result == (
        "Context Compiler pipe misconfigured: BASE_MODEL_ID is invalid or not "
        "configured in Open WebUI. Configure a valid model id in "
        "Admin Panel → Settings → Models."
    )
