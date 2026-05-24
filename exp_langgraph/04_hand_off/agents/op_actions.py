from __future__ import annotations

from typing import Any


def validate_op_actions(actions: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Validate OP action payload for current supported action contracts.

    Current scope:
    - Supports only `{"action":"show_layer","artifact":"..."}`.
    - Other action families from ARCH-002 (`create_layer_from_artifact`,
      `show_created_layer`, `rename_layer`) are intentionally not enabled yet
      and will be introduced in follow-up work items (BACKEND-017 series).

    Returns:
    - (validated_actions, None) when valid
    - ([], error_message) when invalid
    """
    if actions is None:
        return [], None
    if not isinstance(actions, list):
        return [], "Invalid actions payload: expected a list."

    validated: list[dict[str, Any]] = []
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            return [], f"Invalid action at index {idx}: expected object."

        action_name = action.get("action")
        if action_name != "show_layer":
            return [], f"Unsupported action at index {idx}: {action_name!r}."

        artifact = action.get("artifact")
        if not isinstance(artifact, str) or not artifact.strip():
            return [], (
                f"Invalid show_layer action at index {idx}: "
                "non-empty `artifact` is required."
            )

        validated.append({"action": "show_layer", "artifact": artifact.strip()})

    return validated, None
