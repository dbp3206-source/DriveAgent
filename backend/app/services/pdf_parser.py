"""Engine bóc tách tài liệu PDF nâng cao sử dụng OpenDataLoader-PDF.

Bảo toàn cấu trúc Markdown Table, giữ nguyên toàn vẹn các chữ số trong biểu bảng tài chính,
đọc thứ tự cột theo thuật toán XY-Cut++, và phân định rõ ràng giữa Text, Table và Image.
"""

import json
import logging
import re
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


_MARKDOWN_IMAGE = re.compile(r"(!\[[^\]]*\]\()([^\)]+)(\))")
_HTML_IMAGE = re.compile(r"(<img\b[^>]*\bsrc=[\"'])([^\"']+)([\"'])", re.IGNORECASE)
_ANGLE_IMAGE = re.compile(r"<([^>]+\.(?:png|jpe?g|gif|webp))>", re.IGNORECASE)


def _canonical_text(value: str) -> str:
    """Compare PDF text without Markdown punctuation or line-wrap noise."""

    return " ".join(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


def _append_text_recovery(content: str, pdf_path: Path) -> str:
    """Recover text OpenDataLoader lost to a broken PDF glyph map.

    Keep OpenDataLoader's tables/images as the primary rendering. Only add text
    lines that a second extractor finds but the primary rendering lacks. The
    lines are inserted into their original page block so the preview and RAG
    never show duplicate pages at the end of the document.
    """

    try:
        import pdfplumber

        canonical_primary = _canonical_text(content)
        recoveries: list[tuple[int, list[str]]] = []
        added_characters = 0
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                missing: list[str] = []
                for line in (page.extract_text() or "").splitlines():
                    normalized = _canonical_text(line)
                    if len(normalized) < 16 or normalized in canonical_primary:
                        continue
                    if added_characters + len(line) > 50_000:
                        break
                    missing.append(line.strip())
                    added_characters += len(line)
                if missing:
                    recoveries.append((page_number, missing))
                if added_characters >= 50_000:
                    break
        # Work backwards so inserting into a page does not invalidate the
        # offsets of pages that still need recovery text.
        for page_number, lines in reversed(recoveries):
            marker = f"<!-- page:{page_number} -->"
            page_start = content.find(marker)
            if page_start < 0:
                continue
            next_marker = content.find("<!-- page:", page_start + len(marker))
            insert_at = len(content) if next_marker < 0 else next_marker
            recovered = "\n\n" + "\n".join(lines).strip() + "\n\n"
            content = content[:insert_at].rstrip() + recovered + content[insert_at:].lstrip()
        if recoveries:
            return content
    except Exception as exc:
        # The secondary extractor must never break an otherwise readable PDF.
        logger.warning("Không thể đối chiếu văn bản PDF %s: %s", pdf_path.name, exc)
    return content


def _persist_image_references(
    content: str,
    source_root: Path,
    asset_dir: Path | None,
    asset_base_url: str | None,
) -> tuple[str, list[str]]:
    """Copy parser-owned images out of TemporaryDirectory and rewrite safe URLs."""

    if asset_dir is None:
        return content, []
    asset_dir.mkdir(parents=True, exist_ok=True)
    persisted: list[str] = []
    counter = 0

    def persist(raw_value: str) -> str | None:
        nonlocal counter
        raw = raw_value.strip().replace("\\", "/")
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1].strip()
        if raw.startswith(("http://", "https://", "data:", "/api/")):
            return None
        candidate = (source_root / raw).resolve()
        try:
            candidate.relative_to(source_root.resolve())
        except ValueError:
            return None
        if not candidate.is_file():
            return None
        counter += 1
        suffix = candidate.suffix.lower() if candidate.suffix else ".bin"
        filename = f"image-{counter:03d}{suffix}"
        shutil.copyfile(candidate, asset_dir / filename)
        persisted.append(filename)
        return f"{asset_base_url.rstrip('/')}/{filename}" if asset_base_url else filename

    def replace(match: re.Match[str]) -> str:
        url = persist(match.group(2))
        return match.group(0) if url is None else f"{match.group(1)}{url}{match.group(3)}"

    def replace_angle(match: re.Match[str]) -> str:
        url = persist(match.group(1))
        return "" if url is None else f"![]({url})"

    content = _MARKDOWN_IMAGE.sub(replace, content)
    content = _HTML_IMAGE.sub(replace, content)
    content = _ANGLE_IMAGE.sub(replace_angle, content)
    if persisted:
        # Asset inventory belongs beside the files, never in searchable text.
        # The old HTML comment could span multiple chunks for image-heavy PDFs
        # and polluted both embeddings and retrieval results.
        (asset_dir / "manifest.json").write_text(
            json.dumps({"assets": persisted}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return content, persisted


def parse_pdf_to_markdown(
    pdf_path: str | Path,
    *,
    asset_dir: Path | None = None,
    asset_base_url: str | None = None,
) -> str:
    """Chuyển đổi PDF sang Markdown và giữ ảnh ở asset store bền vững.

    ``asset_dir`` bắt buộc cho đường production. Không truyền nó chỉ dành cho
    offline parser probes; khi đó các image reference của OpenDataLoader không có
    vòng đời sau khi hàm trả về.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file PDF tại {path}")

    # 1. Thử dùng OpenDataLoader-PDF trước tiên
    try:
        import opendataloader_pdf

        with tempfile.TemporaryDirectory() as temp_dir:
            opendataloader_pdf.convert(
                input_path=[str(path.resolve())],
                output_dir=temp_dir,
                format="markdown",
                # The marker remains machine-readable but invisible in rendered
                # Markdown. RAG chunking uses it to bind evidence to a PDF page.
                markdown_page_separator="\n\n<!-- page:%page-number% -->\n\n",
            )
            md_files = list(Path(temp_dir).glob("*.md"))
            if md_files:
                content = md_files[0].read_text(encoding="utf-8")
                if content.strip():
                    content, _assets = _persist_image_references(
                        content, Path(temp_dir), asset_dir, asset_base_url
                    )
                    return _append_text_recovery(content, path)
    except Exception as exc:
        logger.warning(
            "OpenDataLoader-PDF gặp lỗi khi xử lý %s; đang chuyển sang fallback: %s",
            path.name,
            exc,
        )

    # 2. Fallback: Dùng MarkItDown nếu OpenDataLoader-PDF không khả dụng
    try:
        from markitdown import MarkItDown

        return MarkItDown().convert(str(path)).text_content
    except Exception as exc:
        logger.error("Cả OpenDataLoader-PDF và MarkItDown đều thất bại trên %s: %s", path.name, exc)
        raise
