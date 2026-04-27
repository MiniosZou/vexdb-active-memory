from concurrent.futures import ThreadPoolExecutor

from vexdb_active_memory.normalize import advisory_lock_key, canonicalize


def test_similar_concurrent_inputs_share_lock_bucket_for_same_canonical_text():
    text = canonicalize("User prefers approved hotels.")

    def key_for_same_text():
        return advisory_lock_key("default", "oa", "user:zouzh", text[:512])

    with ThreadPoolExecutor(max_workers=10) as executor:
        keys = list(executor.map(lambda _: key_for_same_text(), range(10)))

    assert len(set(keys)) == 1

