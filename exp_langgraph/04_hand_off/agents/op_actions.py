from __future__ import annotations

from typing import Any


def validate_op_actions(actions: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Validate OP action payload for current supported action contracts.

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
        if action_name in {"show_layer", "show_existing_layer"}:
            artifact = action.get("artifact")
            catalog_item_id = action.get("catalogItemId")
            layer_id = action.get("layerId")
            selectors: list[tuple[str, str]] = []
            if isinstance(artifact, str) and artifact.strip():
                selectors.append(("artifact", artifact.strip()))
            if isinstance(catalog_item_id, str) and catalog_item_id.strip():
                selectors.append(("catalogItemId", catalog_item_id.strip()))
            if isinstance(layer_id, str) and layer_id.strip():
                selectors.append(("layerId", layer_id.strip()))
            if len(selectors) != 1:
                return [], (
                    f"Invalid show_layer action at index {idx}: exactly one of "
                    "`artifact`, `catalogItemId`, or `layerId` is required."
                )
            normalized = {"action": "show_layer", selectors[0][0]: selectors[0][1]}
            validated.append(normalized)
            continue

        if action_name == "create_layer_from_artifact":
            artifact_obj = action.get("artifact")
            if not isinstance(artifact_obj, dict):
                return [], (
                    f"Invalid create_layer_from_artifact at index {idx}: "
                    "`artifact` object is required."
                )
            path = artifact_obj.get("path")
            if not isinstance(path, str) or not path.strip():
                return [], (
                    f"Invalid create_layer_from_artifact at index {idx}: "
                    "non-empty `artifact.path` is required."
                )
            normalized_artifact: dict[str, Any] = {"path": path.strip()}
            fmt = artifact_obj.get("format")
            if isinstance(fmt, str) and fmt.strip():
                normalized_artifact["format"] = fmt.strip()
            desc = artifact_obj.get("description")
            if isinstance(desc, str) and desc.strip():
                normalized_artifact["description"] = desc.strip()
            validated.append(
                {"action": "create_layer_from_artifact", "artifact": normalized_artifact}
            )
            continue

        if action_name == "show_created_layer":
            source_idx = action.get("sourceActionIndex")
            if not isinstance(source_idx, int):
                return [], (
                    f"Invalid show_created_layer at index {idx}: "
                    "integer `sourceActionIndex` is required."
                )
            validated.append(
                {"action": "show_created_layer", "sourceActionIndex": source_idx}
            )
            continue

        if action_name == "rename_layer":
            layer_id = action.get("layerId")
            name = action.get("name")
            if not isinstance(layer_id, str) or not layer_id.strip():
                return [], (
                    f"Invalid rename_layer at index {idx}: non-empty `layerId` is required."
                )
            if not isinstance(name, str) or not name.strip():
                return [], (
                    f"Invalid rename_layer at index {idx}: non-empty `name` is required."
                )
            validated.append(
                {
                    "action": "rename_layer",
                    "layerId": layer_id.strip(),
                    "name": name.strip(),
                }
            )
            continue

        return [], f"Unsupported action at index {idx}: {action_name!r}."

    return validated, None
