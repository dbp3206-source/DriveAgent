from app.agent.evidence import source_references


def test_reference_numbers_are_not_document_chunk_positions():
    citations = [
        {"file_id": "a", "chunk_index": 7, "snippet": "State"},
        {"file_id": "b", "chunk_index": 100, "snippet": "Nodes"},
    ]
    references = source_references(citations)
    assert [item["reference"] for item in references] == [1, 2]
    assert [item["chunk_index"] for item in references] == [7, 100]
    assert "reference" not in citations[0]


def test_empty_evidence_has_no_invented_reference():
    assert source_references([]) == []
