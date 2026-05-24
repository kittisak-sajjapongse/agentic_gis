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
    actions, err = validate_op_actions([{"action": "rename_layer", "layerId": "x"}])
    assert actions == []
    assert "Unsupported action" in (err or "")


def test_validate_actions_rejects_empty_artifact() -> None:
    actions, err = validate_op_actions([{"action": "show_layer", "artifact": "  "}])
    assert actions == []
    assert "non-empty `artifact`" in (err or "")


def test_validate_actions_accepts_show_layer() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_layer", "artifact": "cat_001"}]
    )
    assert err is None
    assert actions == [{"action": "show_layer", "artifact": "cat_001"}]


def test_validate_actions_accepts_multiple_show_layer_actions() -> None:
    actions, err = validate_op_actions(
        [
            {"action": "show_layer", "artifact": "cat_001"},
            {"action": "show_layer", "artifact": "lyr_in_abcd1234"},
            {"action": "show_layer", "artifact": "/data/hotspot_2024.parquet"},
        ]
    )
    assert err is None
    assert actions == [
        {"action": "show_layer", "artifact": "cat_001"},
        {"action": "show_layer", "artifact": "lyr_in_abcd1234"},
        {"action": "show_layer", "artifact": "/data/hotspot_2024.parquet"},
    ]


def test_validate_actions_trims_artifact_whitespace() -> None:
    actions, err = validate_op_actions(
        [{"action": "show_layer", "artifact": "  cat_001  "}]
    )
    assert err is None
    assert actions == [{"action": "show_layer", "artifact": "cat_001"}]


def test_validate_actions_rejects_non_object_action_item() -> None:
    actions, err = validate_op_actions(["show_layer"])
    assert actions == []
    assert "expected object" in (err or "")


def test_validate_actions_rejects_missing_action_field() -> None:
    actions, err = validate_op_actions([{"artifact": "cat_001"}])
    assert actions == []
    assert "Unsupported action" in (err or "")


def test_validate_actions_rejects_non_string_artifact() -> None:
    actions, err = validate_op_actions([{"action": "show_layer", "artifact": 123}])
    assert actions == []
    assert "non-empty `artifact`" in (err or "")
