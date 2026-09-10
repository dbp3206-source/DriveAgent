"""Deterministic Google Slides executor with targeted edits and read-back verification."""

from collections.abc import Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.visuals import VisualSpec
from app.tools.contracts import ToolError


class SlideSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=180)
    bullets: list[str] = Field(default_factory=list, max_length=10)
    speaker_notes: str = Field(default="", max_length=3000)
    visual: VisualSpec | None = None
    visual_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")

    @model_validator(mode="after")
    def bounded(self):
        if any(not item.strip() or len(item) > 500 for item in self.bullets):
            raise ValueError("Each bullet must contain 1–500 visible characters")
        if self.visual is not None and self.visual_id is not None:
            raise ValueError("Use visual or visual_id, not both")
        return self


class PresentationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    slides: list[SlideSpec] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def bounded(self):
        if sum(len(s.title) + sum(map(len, s.bullets)) for s in self.slides) > 80000:
            raise ValueError("Presentation exceeds the content budget")
        return self


class SlideReplacement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_text: str = Field(min_length=1, max_length=5000)
    new_text: str = Field(max_length=5000)


class SlideVisualUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slide_id: str = Field(min_length=3, max_length=200)
    visual: VisualSpec | None = None
    visual_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")

    @model_validator(mode="after")
    def one_visual(self):
        if (self.visual is None) == (self.visual_id is None):
            raise ValueError("Use exactly one of visual or visual_id")
        return self


class PresentationPatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,200}$")
    revision_id: str = Field(min_length=1, max_length=500)
    replacements: list[SlideReplacement] = Field(default_factory=list, max_length=20)
    add_slides: list[SlideSpec] = Field(default_factory=list, max_length=10)
    delete_slide_ids: list[str] = Field(default_factory=list, max_length=10)
    visual_updates: list[SlideVisualUpdate] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def has_change(self):
        if not (
            self.replacements or self.add_slides or self.delete_slide_ids or self.visual_updates
        ):
            raise ValueError("At least one edit operation is required")
        if len(set(self.delete_slide_ids)) != len(self.delete_slide_ids):
            raise ValueError("Slide IDs must be unique")
        return self


class PresentationEditIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,200}$")
    replacements: list[SlideReplacement] = Field(default_factory=list, max_length=20)
    add_slides: list[SlideSpec] = Field(default_factory=list, max_length=10)
    delete_slide_ids: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def has_change(self):
        if not (self.replacements or self.add_slides or self.delete_slide_ids):
            raise ValueError("At least one edit operation is required")
        return self


def _id(prefix: str) -> str:
    return prefix + uuid4().hex[:20]


def _text_box(
    page_id: str,
    object_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    size: int,
    bold: bool = False,
) -> list[dict]:
    return [
        {
            "createShape": {
                "objectId": object_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": page_id,
                    "size": {
                        "width": {"magnitude": w, "unit": "PT"},
                        "height": {"magnitude": h, "unit": "PT"},
                    },
                    "transform": {
                        "scaleX": 1,
                        "scaleY": 1,
                        "translateX": x,
                        "translateY": y,
                        "unit": "PT",
                    },
                },
            }
        },
        {"insertText": {"objectId": object_id, "text": text}},
        {
            "updateTextStyle": {
                "objectId": object_id,
                "textRange": {"type": "ALL"},
                "style": {
                    "fontFamily": "Arial",
                    "fontSize": {"magnitude": size, "unit": "PT"},
                    "bold": bold,
                    "foregroundColor": {
                        "opaqueColor": {"rgbColor": {"red": 0.10, "green": 0.11, "blue": 0.14}}
                    },
                },
                "fields": "fontFamily,fontSize,bold,foregroundColor",
            }
        },
    ]


def slide_requests(page_id: str, slide: SlideSpec) -> list[dict]:
    requests: list[dict] = []
    title_id, body_id = _id("title"), _id("body")
    requests.extend(_text_box(page_id, title_id, 42, 35, 630, 60, slide.title, 28, True))
    body_width = 360 if slide.visual else 630
    body = "\n".join(f"• {item}" for item in slide.bullets) or " "
    requests.extend(_text_box(page_id, body_id, 48, 118, body_width, 250, body, 17))
    if slide.visual:
        panel = _id("panel")
        requests.append(
            {
                "createShape": {
                    "objectId": panel,
                    "shapeType": "ROUND_RECTANGLE",
                    "elementProperties": {
                        "pageObjectId": page_id,
                        "size": {
                            "width": {"magnitude": 245, "unit": "PT"},
                            "height": {"magnitude": 245, "unit": "PT"},
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": 430,
                            "translateY": 120,
                            "unit": "PT",
                        },
                    },
                }
            }
        )
        visual_text = (
            slide.visual.title
            + "\n\n"
            + "\n".join(f"{i + 1}. {s.title}" for i, s in enumerate(slide.visual.sections[:6]))
        )
        visual_id = _id("visual")
        requests.extend(_text_box(page_id, visual_id, 450, 140, 205, 205, visual_text, 14, False))
    return requests


def presentation_text(presentation: dict) -> str:
    text = []
    for slide in presentation.get("slides", []):
        for element in slide.get("pageElements", []):
            for part in element.get("shape", {}).get("text", {}).get("textElements", []):
                content = part.get("textRun", {}).get("content")
                if content:
                    text.append(content)
    return "".join(text)


def notes_object_id(slide: dict) -> str:
    notes_page = slide.get("slideProperties", {}).get("notesPage", {})
    object_id = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")
    if not object_id:
        raise ToolError("Google Slides không trả vùng speaker notes.", code="notes_unavailable")
    return object_id


def speaker_notes_text(slide: dict) -> str:
    notes_page = slide.get("slideProperties", {}).get("notesPage", {})
    target = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")
    for element in notes_page.get("pageElements", []):
        if element.get("objectId") != target:
            continue
        return "".join(
            part.get("textRun", {}).get("content", "")
            for part in element.get("shape", {}).get("text", {}).get("textElements", [])
        )
    return ""


class SlideCreator:
    def __init__(self, service):
        self.presentations = service.presentations()

    def read(self, presentation_id: str) -> dict:
        return self.presentations.get(presentationId=presentation_id).execute(num_retries=0)

    def create(self, spec: PresentationSpec, on_created: Callable[[str], None]) -> dict:
        created = self.presentations.create(body={"title": spec.title}).execute(num_retries=0)
        presentation_id = created["presentationId"]
        on_created(presentation_id)
        initial = created.get("slides", [])
        page_ids = [initial[0]["objectId"]] if initial else []
        requests: list[dict] = []
        if not page_ids:
            first = _id("slide")
            requests.append(
                {
                    "createSlide": {
                        "objectId": first,
                        "slideLayoutReference": {"predefinedLayout": "BLANK"},
                    }
                }
            )
            page_ids.append(first)
        for _ in spec.slides[len(page_ids) :]:
            page_id = _id("slide")
            requests.append(
                {
                    "createSlide": {
                        "objectId": page_id,
                        "slideLayoutReference": {"predefinedLayout": "BLANK"},
                    }
                }
            )
            page_ids.append(page_id)
        for page_id, slide in zip(page_ids, spec.slides, strict=True):
            requests.extend(slide_requests(page_id, slide))
        self.presentations.batchUpdate(
            presentationId=presentation_id, body={"requests": requests}
        ).execute(num_retries=0)
        actual = self.read(presentation_id)
        notes_requests = []
        for slide, expected_slide in zip(actual.get("slides", []), spec.slides, strict=True):
            if expected_slide.speaker_notes:
                notes_requests.append(
                    {
                        "insertText": {
                            "objectId": notes_object_id(slide),
                            "insertionIndex": 0,
                            "text": expected_slide.speaker_notes,
                        }
                    }
                )
        if notes_requests:
            self.presentations.batchUpdate(
                presentationId=presentation_id, body={"requests": notes_requests}
            ).execute(num_retries=0)
            actual = self.read(presentation_id)
        text = presentation_text(actual)
        expected = [item for slide in spec.slides for item in [slide.title, *slide.bullets]]
        if (
            actual.get("title") != spec.title
            or len(actual.get("slides", [])) != len(spec.slides)
            or any(item not in text for item in expected)
            or any(
                expected_slide.speaker_notes
                and expected_slide.speaker_notes not in speaker_notes_text(slide)
                for slide, expected_slide in zip(actual.get("slides", []), spec.slides, strict=True)
            )
        ):
            raise ToolError(
                "Đã tạo Slides nhưng nội dung chưa qua kiểm tra.", code="verification_failed"
            )
        return {
            "presentation_id": presentation_id,
            "verified": True,
            "slide_count": len(spec.slides),
            "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit",
        }

    def preview_patch(self, spec: PresentationPatchSpec) -> dict:
        actual = self.read(spec.presentation_id)
        if actual.get("revisionId") != spec.revision_id:
            raise ToolError("Slides đã thay đổi; cần xem lại bản sửa.", code="revision_conflict")
        text = presentation_text(actual)
        for change in spec.replacements:
            if text.count(change.old_text) != 1:
                raise ToolError("Đoạn cần sửa phải khớp chính xác một lần.", code="ambiguous_patch")
        ids = {slide["objectId"] for slide in actual.get("slides", [])}
        if not set(spec.delete_slide_ids) <= ids or len(ids - set(spec.delete_slide_ids)) < 1:
            raise ToolError(
                "Không thể xóa slide không tồn tại hoặc xóa toàn bộ.", code="invalid_patch"
            )
        if not {item.slide_id for item in spec.visual_updates} <= ids:
            raise ToolError("Không tìm thấy slide cần thêm visual.", code="invalid_patch")
        return actual

    def apply_patch(self, spec: PresentationPatchSpec) -> dict:
        before = self.preview_patch(spec)
        requests: list[dict] = []
        for change in spec.replacements:
            requests.append(
                {
                    "replaceAllText": {
                        "containsText": {"text": change.old_text, "matchCase": True},
                        "replaceText": change.new_text,
                    }
                }
            )
        for slide_id in spec.delete_slide_ids:
            requests.append({"deleteObject": {"objectId": slide_id}})
        for slide in spec.add_slides:
            page_id = _id("slide")
            requests.append(
                {
                    "createSlide": {
                        "objectId": page_id,
                        "slideLayoutReference": {"predefinedLayout": "BLANK"},
                    }
                }
            )
            requests.extend(slide_requests(page_id, slide))
        for update in spec.visual_updates:
            assert update.visual is not None
            visual_slide = SlideSpec(title="Visual", visual=update.visual)
            # Only keep the native visual panel, not the temporary title/body boxes.
            visual_requests = slide_requests(update.slide_id, visual_slide)
            requests.extend(visual_requests[6:])
        update_result = self.presentations.batchUpdate(
            presentationId=spec.presentation_id,
            body={"requests": requests, "writeControl": {"requiredRevisionId": spec.revision_id}},
        ).execute(num_retries=0)
        actual = self.read(spec.presentation_id)
        text = presentation_text(actual)
        replies = update_result.get("replies", [])
        replacement_counts = [
            reply.get("replaceAllText", {}).get("occurrencesChanged")
            for reply in replies[: len(spec.replacements)]
        ]
        if any(count is not None and count != 1 for count in replacement_counts):
            raise ToolError("Bản sửa Slides chưa qua kiểm tra.", code="verification_failed")
        if any(
            (change.new_text and change.new_text not in text)
            or (not change.new_text and change.old_text in text)
            # A common edit extends the original text (for example "Draft" ->
            # "Draft reviewed"). In that case the old phrase is intentionally a
            # substring of the new one and must not be treated as stale content.
            or (change.old_text not in change.new_text and change.old_text in text)
            for change in spec.replacements
        ):
            raise ToolError("Bản sửa Slides chưa qua kiểm tra.", code="verification_failed")
        if any(
            update.visual is not None and update.visual.title not in text
            for update in spec.visual_updates
        ):
            raise ToolError("Visual chưa được thêm đúng vào Slides.", code="verification_failed")
        expected_count = (
            len(before.get("slides", [])) - len(spec.delete_slide_ids) + len(spec.add_slides)
        )
        if len(actual.get("slides", [])) != expected_count:
            raise ToolError("Số slide sau chỉnh sửa không khớp.", code="verification_failed")
        return {
            "presentation_id": spec.presentation_id,
            "verified": True,
            "slide_count": expected_count,
            "url": f"https://docs.google.com/presentation/d/{spec.presentation_id}/edit",
        }
