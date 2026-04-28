from vexdb_active_memory.intelligence import auto_conflict_decision, estimate_importance, normalize_tags


def test_estimate_importance_uses_text_and_metadata_hints():
    assert estimate_importance("This is a critical policy requirement.") >= 4
    assert estimate_importance("temporary scratch note") <= 2
    assert estimate_importance("normal fact", {"importance": 5}) == 5


def test_normalize_tags_deduplicates_and_limits_values():
    assert normalize_tags([" Product ", "product", "", "User"]) == ["product", "user"]


def test_auto_conflict_decision_supports_manual_and_heuristic_policy():
    assert auto_conflict_decision("manual", nearest_distance=0.01) is None
    assert auto_conflict_decision("append", nearest_distance=0.01) == "append"
    assert auto_conflict_decision("heuristic", nearest_distance=0.04) == "update"
    assert auto_conflict_decision("heuristic", nearest_distance=0.11) == "append"
