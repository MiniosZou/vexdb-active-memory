from vexdb_active_memory.normalize import advisory_lock_key, canonicalize, content_hash


def test_canonicalize_and_hash_are_stable():
    a = canonicalize("  Hello   VexDB Memory  ")
    b = canonicalize("hello vexdb memory")
    assert a == b
    assert content_hash(a) == content_hash(b)


def test_advisory_lock_key_is_signed_int64():
    key = advisory_lock_key("tenant", "namespace", "scope", "text")
    assert isinstance(key, int)
    assert -(2**63) <= key < 2**63

