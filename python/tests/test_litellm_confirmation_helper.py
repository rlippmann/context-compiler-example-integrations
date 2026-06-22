from python.examples.prompt_construction.litellm.confirmation_helper import (
    is_confirmation_text,
    summarize_confirmation_update,
    summarize_confirmation_update_from_checkpoint,
)


def test_accepted_confirmation_tokens() -> None:
    accepted = [
        "yes",
        " YES ",
        "yes please!",
        "Yep.",
        "yeah",
        "sure",
        "ok",
        "okay??",
        "no",
        "Nope!",
        "no thanks...",
    ]

    for value in accepted:
        assert is_confirmation_text(value)


def test_rejects_near_miss_confirmation_tokens() -> None:
    rejected = ["yess", "okayy", "sure thing", "affirmative", "nop", "no thank"]

    for value in rejected:
        assert not is_confirmation_text(value)


def test_deterministic_summary_for_use_only_confirmation() -> None:
    checkpoint = {
        "pending": {
            "kind": "replacement",
            "replacement": {"kind": "use_only", "new_item": "podman", "old_item": None},
            "prompt_to_user": 'Did you mean to use "podman" instead?',
        }
    }

    assert (
        summarize_confirmation_update_from_checkpoint("yes", checkpoint)
        == "State updated: Use podman."
    )


def test_deterministic_summary_for_replacement_confirmation() -> None:
    checkpoint = {
        "pending": {
            "kind": "replacement",
            "replacement": {
                "kind": "replace_use",
                "new_item": "podman",
                "old_item": "docker",
            },
            "prompt_to_user": 'Did you mean to replace "docker" with "podman"?',
        }
    }

    assert (
        summarize_confirmation_update_from_checkpoint("yes please", checkpoint)
        == "State updated: Replaced docker with podman."
    )


def test_deterministic_summary_for_prohibited_old_item_replacement() -> None:
    checkpoint = {
        "pending": {
            "kind": "replacement",
            "replacement": {
                "kind": "replace_use",
                "new_item": "podman",
                "old_item": "docker",
            },
            "prompt_to_user": (
                '"docker" is currently prohibited. '
                'Did you mean to remove it and use "podman" instead?'
            ),
        }
    }

    assert (
        summarize_confirmation_update_from_checkpoint("okay", checkpoint)
        == "State updated: Removed prohibition on docker; use podman."
    )


def test_safe_fallback_on_unknown_pending_shapes() -> None:
    assert (
        summarize_confirmation_update("yes", {"unexpected": "shape"})
        == "State updated."
    )
    assert summarize_confirmation_update_from_checkpoint(
        "yes", {"pending": "unexpected"}
    ) == ("State updated.")
    assert (
        summarize_confirmation_update("no", {"unexpected": "shape"})
        == "State unchanged."
    )
