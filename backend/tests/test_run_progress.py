from app.services.run_progress import publish_progress, read_progress


def test_progress_is_owner_scoped_and_content_free():
    publish_progress(
        "owner-a",
        "safe-run",
        {
            "stage": "tool",
            "tool": "gmail_read_thread",
            "status": "running",
            "prompt": "private",
            "thought": "private",
            "answer": "private",
        },
    )
    assert read_progress("owner-b", "safe-run") == []
    assert read_progress("owner-a", "safe-run") == [
        {
            "stage": "tool",
            "tool": "gmail_read_thread",
            "status": "running",
            "run_id": "safe-run",
        }
    ]


def test_progress_is_bounded():
    for _ in range(90):
        publish_progress("owner", "bounded-run", {"stage": "tool", "status": "running"})
    assert len(read_progress("owner", "bounded-run")) == 60
