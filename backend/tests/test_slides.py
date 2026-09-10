from types import SimpleNamespace

import pytest

from app.services.slide_creator import PresentationPatchSpec, PresentationSpec, SlideCreator
from app.tools.contracts import ToolError


def response(value):
    return SimpleNamespace(execute=lambda num_retries=0: value)


def presentation(text="Cũ", revision="rev-1"):
    return {
        "presentationId": "deck123",
        "title": "Deck",
        "revisionId": revision,
        "slides": [
            {
                "objectId": "slide0",
                "pageElements": [
                    {"shape": {"text": {"textElements": [{"textRun": {"content": text}}]}}}
                ],
            }
        ],
    }


def test_slide_create_batches_and_verifies_content():
    spec = PresentationSpec(
        title="Deck",
        slides=[
            {
                "title": "Mở đầu",
                "bullets": ["Ý thứ nhất"],
                "speaker_notes": "Giải thích ý chính bằng ví dụ.",
            }
        ],
    )
    state = {
        "value": {
            "presentationId": "deck123",
            "title": "Deck",
            "slides": [
                {
                    "objectId": "slide0",
                    "pageElements": [],
                    "slideProperties": {
                        "notesPage": {
                            "notesProperties": {"speakerNotesObjectId": "notes0"},
                            "pageElements": [
                                {
                                    "objectId": "notes0",
                                    "shape": {"text": {"textElements": []}},
                                }
                            ],
                        }
                    },
                }
            ],
        }
    }
    writes = []

    def batch_update(presentationId, body):
        assert presentationId == "deck123"
        writes.append(body)
        by_id = {
            element["objectId"]: element
            for slide in state["value"]["slides"]
            for element in (
                slide.get("pageElements", [])
                + slide.get("slideProperties", {}).get("notesPage", {}).get("pageElements", [])
            )
        }
        for request in body["requests"]:
            if "createShape" in request:
                item = request["createShape"]
                element = {"objectId": item["objectId"], "shape": {"text": {"textElements": []}}}
                state["value"]["slides"][0]["pageElements"].append(element)
                by_id[item["objectId"]] = element
            if "insertText" in request:
                by_id[request["insertText"]["objectId"]]["shape"]["text"]["textElements"] = [
                    {"textRun": {"content": request["insertText"]["text"]}}
                ]
        return response({})

    api = SimpleNamespace(
        create=lambda body: response(state["value"]),
        batchUpdate=batch_update,
        get=lambda **kwargs: response(state["value"]),
    )
    service = SimpleNamespace(presentations=lambda: api)
    saved = []
    result = SlideCreator(service).create(spec, saved.append)
    assert result["verified"] and saved == ["deck123"] and len(writes) == 2


def test_slide_edit_uses_revision_and_detects_conflict():
    before = presentation()
    after = presentation("Mới", "rev-2")
    calls = []
    api = SimpleNamespace(
        get=lambda **kwargs: response(after if calls else before),
        batchUpdate=lambda **kwargs: calls.append(kwargs) or response({}),
    )
    creator = SlideCreator(SimpleNamespace(presentations=lambda: api))
    spec = PresentationPatchSpec(
        presentation_id="deck123",
        revision_id="rev-1",
        replacements=[{"old_text": "Cũ", "new_text": "Mới"}],
    )
    assert creator.apply_patch(spec)["verified"]
    assert calls[0]["body"]["writeControl"] == {"requiredRevisionId": "rev-1"}
    with pytest.raises(ToolError):
        creator.preview_patch(spec.model_copy(update={"revision_id": "wrong"}))


def test_slide_edit_accepts_new_text_that_extends_the_old_phrase():
    before = presentation("Tự đánh giá")
    after = presentation("Tự đánh giá cuối buổi", "rev-2")
    calls = []
    api = SimpleNamespace(
        get=lambda **kwargs: response(after if calls else before),
        batchUpdate=lambda **kwargs: (
            calls.append(kwargs)
            or response({"replies": [{"replaceAllText": {"occurrencesChanged": 1}}]})
        ),
    )
    creator = SlideCreator(SimpleNamespace(presentations=lambda: api))
    spec = PresentationPatchSpec(
        presentation_id="deck123",
        revision_id="rev-1",
        replacements=[{"old_text": "Tự đánh giá", "new_text": "Tự đánh giá cuối buổi"}],
    )

    assert creator.apply_patch(spec)["verified"]
