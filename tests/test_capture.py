from vexdb_active_memory.capture import capture_candidates, classify_memory_type, extract_tags, should_capture


def test_should_capture_triggered_memory_messages():
    assert should_capture("Please remember that the user prefers quiet hotels.")
    assert should_capture("用户电话是 138 0000 0000")
    assert not should_capture("ok")


def test_classify_memory_type_detects_decision_and_entity():
    assert classify_memory_type("We decided to use VexDB for active memory.") == "decision"
    assert classify_memory_type("用户电话是 138 0000 0000") == "entity"
    assert classify_memory_type("User prefers aisle seats.") == "preference"


def test_capture_candidates_respects_cursor_and_extracts_tags():
    messages = [
        {"id": "1", "content": "Please remember that the user prefers quiet hotels."},
        {"id": "2", "content": "We decided to use VexDB for active memory."},
    ]
    candidates = capture_candidates(messages, after_message_id="1")

    assert len(candidates) == 1
    assert candidates[0].message_id == "2"
    assert candidates[0].memory_type == "decision"
    assert "vexdb" in candidates[0].tags


def test_extract_tags_limits_noise():
    assert "vexdb" in extract_tags("Please remember VexDB Active Memory decision")
