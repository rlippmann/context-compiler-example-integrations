import asyncio
import builtins
import importlib.util
import sys
import types
from pathlib import Path
from types import MappingProxyType

import pytest
from context_compiler.grammar import CanonicalDirective, DirectiveKind
from context_compiler_directive_drafter import (
    DraftResult,
    NoDirective,
    UnknownDirective,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT
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

    async def _chat_completion(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
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
    monkeypatch.setitem(
        sys.modules, "open_webui.models.users", open_webui_models_users_mod
    )
    monkeypatch.setitem(sys.modules, "open_webui.utils", open_webui_utils_mod)
    monkeypatch.setitem(sys.modules, "open_webui.utils.chat", open_webui_utils_chat_mod)
    monkeypatch.setitem(
        sys.modules, "open_webui.utils.models", open_webui_utils_models_mod
    )

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
    module._PENDING_PROPOSALS_BY_CHAT_KEY.clear()
    return module


def test_canonical_draft_creates_approval_prompt_and_does_not_mutate_state(
    monkeypatch,
) -> None:
    module = _load_module("owui_with_drafter_before_step", monkeypatch)

    async def fake_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", fake_draft)

    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"
    chat_id = "chat-before-step"

    result = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )
    show_state = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "show state"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )

    assert result == (
        "This is what I think the directive is:\nuse docker\nApply it? (y/n)"
    )
    assert show_state == "Premise: none\nUse: none\nProhibit: none"


def test_approval_applies_stored_directive(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_failed_transition_followup", monkeypatch)
    compile_inputs: list[str] = []
    real_create_engine = module.create_engine

    def create_engine_with_tracking():
        engine = real_create_engine()
        original_step = engine.step

        def tracked_step(user_input: str):
            compile_inputs.append(user_input)
            return original_step(user_input)

        engine.step = tracked_step
        return engine

    monkeypatch.setattr(module, "create_engine", create_engine_with_tracking)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def update_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", update_draft)
    seed = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-failed-transition",
        )
    )
    follow_up = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "y"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-failed-transition",
        )
    )
    show_state = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "show state"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-failed-transition",
        )
    )

    assert seed == (
        "This is what I think the directive is:\nuse docker\nApply it? (y/n)"
    )
    assert follow_up == "State updated."
    assert show_state == "Premise: none\nUse: docker\nProhibit: none"
    assert compile_inputs == ["use docker"]

    second_follow_up = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "yes"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-failed-transition",
        )
    )

    assert second_follow_up != "State updated."
    assert compile_inputs == ["use docker"]


def test_rejection_does_not_mutate_state(monkeypatch) -> None:
    module = _load_module(
        "owui_with_drafter_failed_transition_state_preserved", monkeypatch
    )
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def update_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", update_draft)
    asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-state-preserved",
        )
    )
    rejected = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "n"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-state-preserved",
        )
    )

    show_state = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "show state"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-state-preserved",
        )
    )

    assert rejected == "Directive discarded. No state change was applied."
    assert show_state == "Premise: none\nUse: none\nProhibit: none"

    after_rejection = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "yes"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-state-preserved",
        )
    )

    assert after_rejection != "State updated."


def test_pending_approval_does_not_affect_show_state(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_pending_show_state", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def update_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", update_draft)
    asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-pending-show-state",
        )
    )

    show_state = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "show state"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-pending-show-state",
        )
    )

    assert show_state == "Premise: none\nUse: none\nProhibit: none"


def test_unrelated_follow_up_while_pending_does_not_apply_proposal(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_pending_unrelated_followup", monkeypatch)
    compile_inputs: list[str] = []
    forwarded: list[dict[str, object]] = []
    real_create_engine = module.create_engine

    def create_engine_with_tracking():
        engine = real_create_engine()
        original_step = engine.step

        def tracked_step(user_input: str):
            compile_inputs.append(user_input)
            return original_step(user_input)

        engine.step = tracked_step
        return engine

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    monkeypatch.setattr(module, "create_engine", create_engine_with_tracking)
    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def update_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    async def no_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", update_draft)
    proposal = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-pending-unrelated-followup",
        )
    )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", no_draft)
    follow_up = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-pending-unrelated-followup",
        )
    )

    assert proposal == (
        "This is what I think the directive is:\nuse docker\nApply it? (y/n)"
    )
    assert follow_up == {"choices": [{"message": {"content": "downstream"}}]}
    assert compile_inputs == []
    assert len(forwarded) == 1


def test_no_stale_pending_proposal_remains_after_non_approval_response(
    monkeypatch,
) -> None:
    module = _load_module("owui_with_drafter_no_stale_pending", monkeypatch)
    compile_inputs: list[str] = []
    forwarded: list[dict[str, object]] = []
    real_create_engine = module.create_engine

    def create_engine_with_tracking():
        engine = real_create_engine()
        original_step = engine.step

        def tracked_step(user_input: str):
            compile_inputs.append(user_input)
            return original_step(user_input)

        engine.step = tracked_step
        return engine

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    monkeypatch.setattr(module, "create_engine", create_engine_with_tracking)
    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def update_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    async def no_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", update_draft)
    asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-no-stale-pending",
        )
    )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", no_draft)
    asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-no-stale-pending",
        )
    )
    later_yes = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "yes"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-no-stale-pending",
        )
    )

    assert later_yes == {"choices": [{"message": {"content": "downstream"}}]}
    assert compile_inputs == []
    assert len(forwarded) == 2


def test_fallback_to_raw_input_path_preserves_host_behavior(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_raw", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward

    async def no_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", no_draft)

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


def test_local_update_and_no_directive_passthrough_preserve_host_behavior(
    monkeypatch,
) -> None:
    module = _load_module("owui_with_drafter_local", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def update_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", update_draft)
    proposal = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-update",
        )
    )

    async def no_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", no_draft)
    passthrough = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [
                    {"role": "user", "content": "set premise to concise replies"}
                ],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-invalid-request",
        )
    )

    assert proposal == (
        "This is what I think the directive is:\nuse docker\nApply it? (y/n)"
    )
    assert passthrough == {"choices": [{"message": {"content": "downstream"}}]}
    assert len(forwarded) == 1


def test_no_directive_passthrough_does_not_change_existing_engine_state(
    monkeypatch,
) -> None:
    module = _load_module("owui_with_drafter_no_directive_state_preserved", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def no_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", no_draft)
    chat_id = "chat-near-miss-followup"

    passthrough = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [
                    {"role": "user", "content": "set premise to concise replies"}
                ],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )
    follow_up = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "yes"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )
    show_state = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "show state"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )

    assert passthrough == {"choices": [{"message": {"content": "downstream"}}]}
    assert follow_up == {"choices": [{"message": {"content": "downstream"}}]}
    assert show_state == "Premise: none\nUse: none\nProhibit: none"
    assert len(forwarded) == 2


def test_compound_directives_fall_through_to_normal_forwarding(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_compound", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def compound_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=UnknownDirective(reason="reject.multi_candidate_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", compound_draft)
    result = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [
                    {
                        "role": "user",
                        "content": "please use docker and prohibit peanuts",
                    }
                ],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-compound",
        )
    )

    assert result == {"choices": [{"message": {"content": "downstream"}}]}
    assert len(forwarded) == 1


def test_passthrough_injects_exactly_one_cc_state_system_message_when_state_exists(
    monkeypatch,
) -> None:
    module = _load_module("owui_with_drafter_passthrough", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"
    chat_id = "chat-passthrough"

    async def update_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=CanonicalDirective(
                text="use docker",
                kind=DirectiveKind.USE_ITEM,
                operands=MappingProxyType({"item": "docker"}),
            ),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", update_draft)
    asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )
    asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "y"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__=chat_id,
        )
    )

    async def no_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", no_draft)
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


def test_debug_mode_missing_base_model_returns_deterministic_message(
    monkeypatch,
) -> None:
    module = _load_module("owui_with_drafter_debug_missing_base", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = None
    pipe.valves.PREPROCESSOR_MODEL_ID = None
    pipe.valves.ALLOW_MISSING_BASE_MODEL_FOR_DEBUG = True

    async def no_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=NoDirective(reason="reject.confident_non_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", no_draft)

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-debug-missing-base",
        )
    )

    assert (
        result
        == "Context Compiler debug mode: BASE_MODEL_ID is empty; skipping model passthrough."
    )


def test_preprocessor_model_not_found_is_normalized(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_preprocessor_not_found", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def generate(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        if payload.get("model") == "prep-model":
            return {"error": {"message": "model not found"}}
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = generate
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


def test_fallback_uses_preprocessor_model_then_forward_uses_base_model(
    monkeypatch,
) -> None:
    module = _load_module("owui_with_drafter_fallback_routing", monkeypatch)
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"
    calls: list[str] = []

    async def generate(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        calls.append(str(payload.get("model", "")))
        if len(calls) == 1:
            return {"choices": [{"message": {"content": "no_directive"}}]}
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = generate
    result = asyncio.run(
        pipe.pipe(
            {
                "model": "pipe-model",
                "messages": [{"role": "user", "content": "please use docker"}],
            },
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-routing",
        )
    )

    assert result == {"choices": [{"message": {"content": "downstream"}}]}
    assert calls == ["prep-model", "base-model"]


def test_extract_drafted_text_only_applies_canonical_directive(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_extract_text", monkeypatch)
    pipe = module.Pipe()

    canonical = DraftResult(
        source="test",
        result=CanonicalDirective(
            text="use docker",
            kind=DirectiveKind.USE_ITEM,
            operands=MappingProxyType({"item": "docker"}),
        ),
    )
    no_directive = DraftResult(
        source="test",
        result=NoDirective(reason="reject.confident_non_directive"),
    )
    unknown = DraftResult(
        source="test",
        result=UnknownDirective(reason="reject.multi_candidate_directive"),
    )

    assert pipe._extract_drafted_text(canonical) == "use docker"
    assert pipe._extract_drafted_text(no_directive) is None
    assert pipe._extract_drafted_text(unknown) is None


def test_unknown_directive_falls_back_to_normal_user_input_flow(monkeypatch) -> None:
    module = _load_module("owui_with_drafter_unknown_falls_back", monkeypatch)
    forwarded: list[dict[str, object]] = []

    async def forward(
        _: object, payload: dict[str, object], __: object
    ) -> dict[str, object]:
        forwarded.append(payload)
        return {"choices": [{"message": {"content": "downstream"}}]}

    module.generate_chat_completion = forward
    pipe = module.Pipe()
    pipe.valves.BASE_MODEL_ID = "base-model"
    pipe.valves.PREPROCESSOR_MODEL_ID = "prep-model"

    async def unknown_draft(*args, **kwargs):
        return DraftResult(
            source="test",
            result=UnknownDirective(reason="reject.multi_candidate_directive"),
        )

    monkeypatch.setattr(module.Pipe, "_draft_user_input", unknown_draft)

    result = asyncio.run(
        pipe.pipe(
            {"model": "pipe-model", "messages": [{"role": "user", "content": "hello"}]},
            __user__={"id": "u1"},
            __request__=object(),
            __chat_id__="chat-unknown-raw",
        )
    )

    assert result == {"choices": [{"message": {"content": "downstream"}}]}
    assert forwarded[0]["messages"] == [{"role": "user", "content": "hello"}]


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
