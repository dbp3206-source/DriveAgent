"""Bounded page extraction shared by uploaded/Drive PDF ingestion.

No model call, document instruction execution, network or Java process. The job
worker runs each page in a disposable process so a pathological PDF cannot keep
Chat's event loop or a cancelled worker alive indefinitely.
"""

import argparse
import csv
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PAGES = 1000
MAX_PAGE_CHARACTERS = 250_000
OCR_MIN_CONFIDENCE = 75.0
MAX_LAYOUT_WORDS = 20_000
MAX_LAYOUT_ROWS = 256


def native_layout_page(page):
    """Remove invisible whitespace glyphs; infer spaces from visible glyph gaps.

    Some PDF producers paint padding spaces over digits. PDFMiner treats those
    as word breaks (e.g. visible 162 becomes '1 62'). No visible character is
    removed, and actual word spacing remains observable in its coordinates.
    """
    if not hasattr(page, "filter"):
        return page
    return page.filter(lambda obj: obj.get("object_type") != "char"
                       or bool(obj.get("text", "").strip()))


def aligned_numeric_rows(page) -> str:
    """Supplement native text with conservative, coordinate-backed table rows.

    Borderless tables need repeated numeric column alignment, not text-strategy
    table finding across an entire prose page. Require three rows sharing at
    least three numeric columns. Keep original headings/prose in native text;
    generated column numbers describe geometry, not inferred financial meaning.
    Multi-line labels/comments are associated only through observed horizontal
    boundaries. Without those boundaries only the observed baseline is used.
    """
    if not hasattr(page, "extract_words"):
        return ""
    words = page.extract_words(x_tolerance=1, y_tolerance=2)
    if len(words) > MAX_LAYOUT_WORDS:
        return ""
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not lines or abs(word["top"] - lines[-1][0]["top"]) > 2:
            lines.append([])
        lines[-1].append(word)
    numeric = re.compile(r"[+\-−]?(?:\d[\d,.]*)(?:%|‰)?\Z")
    candidates = [[word for word in line if numeric.fullmatch(word["text"])]
                  for line in lines]
    candidates = [row for row in candidates if len(row) >= 3]
    if not 3 <= len(candidates) <= MAX_LAYOUT_ROWS:
        return ""
    # Right alignment handles differing widths, negative signs and percentages.
    clusters: list[list[dict]] = []
    for word in sorted((word for row in candidates for word in row),
                       key=lambda item: item["x1"]):
        if not clusters or word["x1"] - clusters[-1][0]["x1"] > 3:
            clusters.append([])
        clusters[-1].append(word)
    columns = [group for group in clusters
               if len({round(word["top"], 1) for word in group}) >= 3]
    if not 3 <= len(columns) <= 12:
        return ""
    anchors = [median(word["x1"] for word in group) for group in columns]
    rows = [row for row in candidates if all(
        sum(abs(word["x1"] - anchor) <= 3 for word in row) == 1 for anchor in anchors
    )]
    if len(rows) < 3:
        return ""
    # Reject prose dates/numbers unless the row also has a label to its left.
    first_x = min(word["x0"] for row in rows for word in row
                  if abs(word["x1"] - anchors[0]) <= 3)
    row_lines = [line for line in lines if any(
        abs(line[0]["top"] - row[0]["top"]) <= 2 for row in rows
    )]
    if any(not any(word["x1"] < first_x - 4 for word in line) for line in row_lines):
        return ""
    left_x = min(word["x0"] for line in row_lines for word in line)
    boundaries = sorted({round(edge["top"], 2) for edge in getattr(page, "edges", [])
                         if abs(edge["bottom"] - edge["top"]) < 1
                         and edge["x0"] <= left_x + 3
                         and edge["x1"] >= anchors[-1]
                         and edge["width"] >= (anchors[-1] - left_x) * .8})
    output = [["Nhãn dòng trong nguồn", *[f"Cột {index + 1}"
                                      for index in range(len(anchors))], "Nội dung cùng dòng"]]
    for row, line in zip(rows, row_lines, strict=True):
        y = row[0]["top"]
        before = [value for value in boundaries if value < y]
        after = [value for value in boundaries if value > max(w["bottom"] for w in row)]
        # A boundary band must contain exactly one accepted numeric baseline.
        band = None
        if before and after and sum(before[-1] < other[0]["top"] < after[0]
                                    for other in rows) == 1:
            band = [word for word in words
                    if before[-1] <= word["top"] and word["bottom"] <= after[0]]
        observed = band if band is not None else line
        values = [next(word["text"] for word in row if abs(word["x1"] - anchor) <= 3)
                  for anchor in anchors]
        label = " ".join(word["text"] for word in observed if word["x1"] < first_x - 4)
        prose = " ".join(word["text"] for word in observed if word["x0"] > anchors[-1])
        output.append([label, *values, prose])
    return "Các dòng căn cột trong PDF (số cột chỉ vị trí từ trái sang phải, " \
        "không thay tên chỉ tiêu; tiêu đề gốc được giữ ở trên):\n" + table_markdown(output)


@dataclass
class PageExtraction:
    page: int
    status: str
    text: str = ""
    confidence: float | None = None
    error_code: str | None = None
    ocr_rotation: int = 0

    @property
    def indexable(self) -> bool:
        return self.status in {"text", "ocr"} and bool(self.text.strip())

    def markdown(self) -> str:
        if not self.indexable:
            return ""
        notice = "\nVăn bản OCR: cần đối chiếu ảnh gốc khi sử dụng số liệu.\n" \
            if self.status == "ocr" else ""
        return f"<!-- page:{self.page} -->\n{notice}\n{self.text.strip()}\n"


def inspect_pdf(path: Path) -> int:
    import pdfplumber

    if path.stat().st_size > MAX_PDF_BYTES:
        raise ValueError("pdf_too_large")
    with path.open("rb") as handle:
        if not handle.read(1024).lstrip().startswith(b"%PDF-"):
            raise ValueError("invalid_pdf_signature")
    with pdfplumber.open(path) as pdf:
        count = len(pdf.pages)
        if count < 1 or count > MAX_PAGES:
            raise ValueError("pdf_page_limit")
        return count


def table_markdown(rows: list[list]) -> str:
    def cell(value) -> str:
        return str("" if value is None else value).replace("|", "\\|").replace("\n", " ").strip()

    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [[cell(value) for value in row] + [""] * (width - len(row)) for row in rows]
    header = "| " + " | ".join(normalized[0]) + " |"
    separator = "| " + " | ".join(["---"] * width) + " |"
    body = ["| " + " | ".join(row) + " |" for row in normalized[1:]]
    return "\n".join([header, separator, *body])


def parse_ocr_tsv(raw: str) -> tuple[str, float]:
    lines: dict[tuple[str, ...], list[str]] = {}
    weighted = total = 0.0
    # TSV words may themselves be a literal quote. They are not CSV-quoted
    # fields; interpreting them as such can consume subsequent word records.
    for row in csv.DictReader(io.StringIO(raw), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row.get("level") != "5" or not (row.get("text") or "").strip():
            continue
        word = row["text"].strip()
        try:
            confidence = float(row.get("conf", "-1"))
        except (TypeError, ValueError):
            confidence = 0.0
        if not math.isfinite(confidence):
            confidence = 0.0
        confidence = max(0.0, min(100.0, confidence))
        weight = max(1, len(word))
        weighted += confidence * weight
        total += weight
        key = tuple(row.get(key, "") for key in ("block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(word)
    text = "\n".join(" ".join(words) for words in lines.values())
    return text, weighted / total if total else 0.0


def _binary(configured: str | None, name: str) -> str | None:
    if configured:
        candidate = Path(configured)
        return str(candidate.resolve()) if candidate.is_file() else None
    return shutil.which(name)


def native_page_text(page, *, has_tables: bool) -> str:
    """Read two-column prose in column order only with a persistent clear gutter.

    Tables and ambiguous/full-width layouts retain their original extraction.
    Character counts alone cannot identify reading order or extraction fidelity.
    """
    ordinary = (page.extract_text(layout=False, x_tolerance=1) or "").strip()
    if has_tables or not hasattr(page, "extract_words"):
        return ordinary
    words = page.extract_words(x_tolerance=1)
    if len(words) < 80:
        return ordinary
    width = page.width
    candidates = []
    for position in range(int(width * .35), int(width * .65)):
        if not any(word["x0"] - 2 < position < word["x1"] + 2 for word in words):
            candidates.append(position)
    runs: list[list[int]] = []
    for position in candidates:
        if not runs or position != runs[-1][-1] + 1:
            runs.append([])
        runs[-1].append(position)
    for run in sorted(runs, key=len, reverse=True):
        if len(run) < 5:
            continue
        split = (run[0] + run[-1]) / 2
        left = [word for word in words if word["x1"] <= split]
        right = [word for word in words if word["x0"] >= split]
        if min(len(left), len(right)) < len(words) * .25:
            continue
        if any(max(w["x1"] for w in side) - min(w["x0"] for w in side) < width * .2
               for side in (left, right)):
            continue
        x0, top, x1, bottom = page.bbox
        columns = [page.crop(box).extract_text(layout=False, x_tolerance=1) or "" for box in
                   ((x0, top, split, bottom), (split, top, x1, bottom))]
        return "\n\n".join(text.strip() for text in columns if text.strip())
    return ordinary


def prominent_text_lines(page) -> str:
    """Preserve observable typography, without guessing which line is the title.

    Flattened text can join a cover subtitle to unrelated column labels. Retain
    large-font lines separately as evidence; never rewrite the underlying text.
    """
    sizes = [char.get("size", 0) for char in getattr(page, "chars", [])
             if char.get("text", "").strip() and char.get("size", 0) > 0]
    if not sizes or not hasattr(page, "extract_words"):
        return ""
    threshold = max(18, median(sizes) * 1.6)
    words = [word for word in page.extract_words(extra_attrs=["size"], x_tolerance=1)
             if word.get("size", 0) >= threshold]
    groups: list[list[dict]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not groups or abs(word["top"] - groups[-1][0]["top"]) > 3 or (
            word["x0"] - groups[-1][-1]["x1"] > word["size"] * 2
        ):
            groups.append([])
        groups[-1].append(word)
    lines = [" ".join(word["text"] for word in group) for group in groups[:16]]
    if not lines:
        return ""
    content = "\n".join(f"- {line}" for line in lines)
    if len(content) > 3000:
        return ""
    from app.core.source_evidence import PROMINENT_LINES_LABEL

    return PROMINENT_LINES_LABEL + "\n" + content


def extract_page(path: Path, page_number: int, *, tesseract: str | None = None,
                 pdftoppm: str | None = None, tessdata: str | None = None,
                 ocr_enabled: bool = True) -> PageExtraction:
    import pdfplumber

    try:
        with pdfplumber.open(path) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                return PageExtraction(page_number, "error", error_code="page_out_of_range")
            page = native_layout_page(pdf.pages[page_number - 1])
            raw_tables = page.extract_tables(table_settings={"text_x_tolerance": 1})
            aligned = aligned_numeric_rows(page) if not raw_tables else ""
            text = native_page_text(page, has_tables=bool(raw_tables or aligned))
            typography = prominent_text_lines(page)
            tables = [table_markdown(table) for table in raw_tables]
            # Keep searchable native text and structured tables on the same page.
            text = "\n\n".join(
                [text, *[table for table in tables if table], aligned, typography]
            ).strip()
        if len(text) > MAX_PAGE_CHARACTERS:
            return PageExtraction(page_number, "error", error_code="page_text_limit")
        if len(text) >= 40:
            return PageExtraction(page_number, "text", text=text)
    except Exception:
        return PageExtraction(page_number, "error", error_code="pdf_parse_error")
    if not ocr_enabled:
        return PageExtraction(page_number, "unsupported_scan", text=text,
                              error_code="pdf_ocr_excluded")
    render = _binary(pdftoppm, "pdftoppm")
    ocr = _binary(tesseract, "tesseract")
    if not render or not ocr:
        return PageExtraction(page_number, "needs_ocr", text=text,
                              error_code="ocr_dependencies_missing")
    environment = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    if tessdata:
        environment["TESSDATA_PREFIX"] = tessdata
    try:
        with tempfile.TemporaryDirectory(prefix="veridra-page-") as folder:
            prefix = str(Path(folder) / "page")
            subprocess.run([render, "-f", str(page_number), "-l", str(page_number),
                            "-singlefile", "-scale-to", "2400", "-png", str(path), prefix],
                           check=True, capture_output=True, timeout=45, env=environment)
            deadline = time.monotonic() + 75
            recognized, confidence, rotation = "", 0.0, 0
            for angle in (0, 90, 180, 270):
                image_path = prefix + ".png"
                if angle:
                    from PIL import Image

                    image_path = prefix + f"-{angle}.png"
                    with Image.open(prefix + ".png") as image:
                        image.rotate(angle, expand=True).save(image_path)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                result = subprocess.run([ocr, image_path, "stdout", "-l", "vie+eng",
                                         "--psm", "3", "-c", "tessedit_create_tsv=1"],
                                        check=True, capture_output=True, timeout=remaining,
                                        env=environment)
                raw_tsv = result.stdout.decode("utf-8", errors="replace")
                # Language-only tessdata need not contain configs/tsv.
                if not raw_tsv.startswith("level\tpage_num\t"):
                    return PageExtraction(page_number, "error", error_code="ocr_invalid_output")
                candidate, score = parse_ocr_tsv(raw_tsv)
                if score > confidence or not recognized:
                    recognized, confidence, rotation = candidate, score, angle
                if angle == 0 and candidate.strip() and score >= OCR_MIN_CONFIDENCE:
                    break
        if len(recognized) > MAX_PAGE_CHARACTERS:
            return PageExtraction(page_number, "error", error_code="page_text_limit")
        status = "ocr" if recognized.strip() and confidence >= OCR_MIN_CONFIDENCE \
            else "low_confidence"
        return PageExtraction(page_number, status, recognized, round(confidence, 2),
                              ocr_rotation=rotation)
    except subprocess.TimeoutExpired:
        return PageExtraction(page_number, "error", error_code="ocr_timeout")
    except (subprocess.CalledProcessError, OSError):
        return PageExtraction(page_number, "error", error_code="ocr_failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--page", type=int)
    parser.add_argument("--tesseract")
    parser.add_argument("--pdftoppm")
    parser.add_argument("--tessdata")
    parser.add_argument("--no-ocr", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.page is None:
            output = {"pages": inspect_pdf(arguments.path)}
        else:
            output = asdict(extract_page(arguments.path, arguments.page,
                                        tesseract=arguments.tesseract,
                                        pdftoppm=arguments.pdftoppm, tessdata=arguments.tessdata,
                                        ocr_enabled=not arguments.no_ocr))
    except Exception:
        output = {"error_code": "invalid_pdf"}
    # ASCII JSON survives Windows pipe codepages; json.loads restores Unicode.
    print(json.dumps(output, ensure_ascii=True))
