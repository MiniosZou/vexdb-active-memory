from vexdb_active_memory.models import MemoryRecord, SearchResult


def test_search_result_mcp_shape():
    result = SearchResult(
        [
            MemoryRecord(
                id="abc",
                content="hello",
                metadata={"wing": "demo"},
                distance=0.12,
            )
        ]
    )
    shaped = result.to_mcp_compatible()
    assert shaped["ids"] == [["abc"]]
    assert shaped["documents"] == [["hello"]]
    assert shaped["metadatas"] == [[{"wing": "demo"}]]
    assert shaped["distances"] == [[0.12]]

