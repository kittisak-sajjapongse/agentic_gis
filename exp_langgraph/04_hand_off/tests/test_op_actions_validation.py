from agents.op_actions import validate_op_actions


def test_validate_actions_none_ok() -> None:
    actions, err = validate_op_actions(None)
    assert err is None
    assert actions == []


def test_validate_actions_requires_list() -> None:
    actions, err = validate_op_actions({"action": "show_layer"})
    assert actions == []
    assert err is not None


def test_validate_actions_rejects_unknown_action() -> None:
    actions, err = validate_op_actions([{"action": "unknown_action"}])
    assert actions == []
    assert "Unsupported action" in (err or "")


def test_validate_actions_rejects_non_object_action_item() -> None:
    actions, err = validate_op_actions(["show_layer"])
    assert actions == []
    assert "expected object" in (err or "")


def test_validate_actions_rejects_missing_action_field() -> None:
    actions, err = validate_op_actions([{"artifact": "cat_001"}])
    assert actions == []
    assert "Unsupported action" in (err or "")


def test_validate_actions_accepts_show_layer_artifact_selector() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_layer", "artifact": "cat_001"}]
    )
    assert err is None
    assert actions == [{"action": "show_layer", "artifact": "cat_001"}]


def test_validate_actions_accepts_show_layer_catalog_selector() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_layer", "catalogItemId": "cat_001"}]
    )
    assert err is None
    assert actions == [{"action": "show_layer", "catalogItemId": "cat_001"}]


def test_validate_actions_accepts_show_layer_layer_selector() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_layer", "layerId": "lyr_in_abcd1234"}]
    )
    assert err is None
    assert actions == [{"action": "show_layer", "layerId": "lyr_in_abcd1234"}]


def test_validate_actions_rejects_show_layer_empty_selector() -> None:
    actions, err = validate_op_actions([{"action": "show_layer", "artifact": "  "}])
    assert actions == []
    assert "exactly one of" in (err or "")


def test_validate_actions_rejects_show_layer_multiple_selectors() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_layer", "artifact": "cat_001", "layerId": "lyr_1"}]
    )
    assert actions == []
    assert "exactly one of" in (err or "")


def test_validate_actions_accepts_show_existing_layer_alias() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_existing_layer", "catalogItemId": "cat_001"}]
    )
    assert err is None
    assert actions == [{"action": "show_layer", "catalogItemId": "cat_001"}]


def test_validate_actions_accepts_create_layer_from_artifact() -> None:
    actions, err = validate_op_actions(
        [
            {
                "action": "create_layer_from_artifact",
                "artifact": {
                    "path": "/data/output/x.parquet",
                    "format": "GEOPARQUET",
                    "description": "desc",
                },
            }
        ]
    )
    assert err is None
    assert actions == [
        {
            "action": "create_layer_from_artifact",
            "artifact": {
                "path": "/data/output/x.parquet",
                "format": "GEOPARQUET",
                "description": "desc",
            },
        }
    ]


def test_validate_actions_rejects_create_layer_without_artifact_object() -> None:
    actions, err = validate_op_actions(
        [{"action": "create_layer_from_artifact", "artifact": "/data/x.parquet"}]
    )
    assert actions == []
    assert "`artifact` object is required" in (err or "")


def test_validate_actions_rejects_create_layer_without_path() -> None:
    actions, err = validate_op_actions(
        [{"action": "create_layer_from_artifact", "artifact": {}}]
    )
    assert actions == []
    assert "artifact.path" in (err or "")


def test_validate_actions_accepts_show_created_layer() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_created_layer", "sourceActionIndex": 0}]
    )
    assert err is None
    assert actions == [{"action": "show_created_layer", "sourceActionIndex": 0}]


def test_validate_actions_rejects_show_created_layer_non_int_index() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_created_layer", "sourceActionIndex": "0"}]
    )
    assert actions == []
    assert "sourceActionIndex" in (err or "")


def test_validate_actions_accepts_rename_layer() -> None:
    actions, err = validate_op_actions(
        [{"action": "rename_layer", "layerId": "lyr_1", "name": "New Name"}]
    )
    assert err is None
    assert actions == [{"action": "rename_layer", "layerId": "lyr_1", "name": "New Name"}]


def test_validate_actions_rejects_rename_layer_missing_fields() -> None:
    actions, err = validate_op_actions([{"action": "rename_layer", "layerId": "lyr_1"}])
    assert actions == []
    assert "non-empty `name`" in (err or "")
