from scripts.qa_google_read_smoke import smoke_passed


def test_google_smoke_rejects_masked_integration_failures():
    healthy = {
        "gmail_list": {"status": "ok"},
        "gmail_threads": {"status": "ok"},
        "gmail_inline_attachment": {"status": 200},
        "drive_list": {"status": "ok"},
        "drive_content": {"google_doc": {"status": "ok"}},
    }
    assert smoke_passed(healthy)
    assert not smoke_passed({**healthy, "gmail_error": {"status": 503}})
    assert not smoke_passed({**healthy, "drive_error": {"status": 503}})
    assert not smoke_passed(
        {**healthy, "drive_content": {"google_doc": {"status": "read_error"}}}
    )
    assert not smoke_passed({**healthy, "gmail_inline_attachment": {"status": 400}})
