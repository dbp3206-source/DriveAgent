from types import SimpleNamespace

from app.agent.compiler import conversation_context


def message(role, content):
    return SimpleNamespace(role=role, content=content)


def test_more_than_twelve_turns_preserves_chronological_context():
    rows = [message("user", f"turn {i}") for i in range(20, 0, -1)]
    result = conversation_context(rows, "new request")
    assert len(result) == 20
    assert result[0]["text"] == "turn 1"
    assert result[-1]["text"] == "turn 20"


def test_long_instruction_keeps_tail_and_marks_omission():
    text = "Khách hàng Sao Mai. " + "x" * 18000 + "Ngân sách chưa biết, không tự đoán."
    result = conversation_context([message("user", text)], "next")
    assert result[0]["text"].startswith("Khách hàng Sao Mai.")
    assert result[0]["text"].endswith("Ngân sách chưa biết, không tự đoán.")
    assert "đã được lược bớt" in result[0]["text"]
    assert len(result[0]["text"]) <= 16000


def test_current_request_removed_by_full_equality_not_truncated_prefix():
    first = "a" * 4000 + "old"
    current = "a" * 4000 + "new"
    result = conversation_context([message("user", first)], current)
    assert result[0]["text"] == first
    assert conversation_context([message("user", current)], current) == []


def test_total_budget_and_explicit_missing_history():
    rows = [message("assistant", str(i) + "x" * 20000) for i in range(32)]
    result = conversation_context(rows, "next")
    assert result[0]["role"] == "system"
    assert "hỏi lại" in result[0]["text"]
    assert sum(len(row["text"]) for row in result[1:]) <= 64000
    assert result[-1]["text"].startswith("0")
