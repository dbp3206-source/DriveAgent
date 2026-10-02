"""Upload the six user-supplied PDFs through the local API; no model calls.

Scan-only samples are expected to finish as ``needs_attention``.  OCR is outside
the release scope, so the QA probe records that rejection instead of trying to
read or resume a source that was intentionally not indexed.
"""

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def run(*, reextract=False):
    from evaluate_gate2_live import _session_cookie
    from qa_google_read_smoke import _connected_owner_id

    samples = Path("C:/Users/Bao Phuc/Documents/Test_RAG")
    names = [
        "1769754182481-20260130-CBTTBáocáoTìnhhìnhqu_ntr_côngtyn_m2025.pdf",
        "1777855011444-MASVN_RS_Strategy_2026_05_VN.pdf",
        "Bao-cao-dien-bien-thi-truong-nam-2025-gui-TTTT-1.pdf",
        "DubaoKQKD_Nganhdien_20260408.pdf",
        "Ngan-hang_20260330.pdf",
        "The_He_Cho_Duoc_Hieu_aa1ad8d7a3.pdf",
    ]
    owner = _connected_owner_id()
    results = []
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=45,
                                 cookies={"drive_agent_session": _session_cookie(owner)}) as http:
        for name in names:
            path = samples / name
            if not path.is_file():
                results.append({"name": name, "status": "NOT VERIFIED", "reason": "missing_sample"})
                continue
            raw = path.read_bytes()
            response = await http.post("/api/local-sources", params={"name": name}, content=raw,
                                       headers={"Content-Type": "application/octet-stream"})
            response.raise_for_status()
            initial = response.json()
            if initial.get("kind") != "pdf_job":
                raise ValueError("Expected real PDF job")
            if reextract or initial["status"] in {"failed", "cancelled"}:
                resumed = await http.post(f"/api/local-sources/pdf-jobs/{initial['id']}/reextract")
                resumed.raise_for_status()
                initial = resumed.json()
            started = time.monotonic()
            job = initial
            while job["status"] in {"queued", "running"}:
                if time.monotonic() - started > 900:
                    break
                await asyncio.sleep(2)
                listing = await http.get("/api/local-sources/pdf-jobs")
                listing.raise_for_status()
                job = next(row for row in listing.json() if row["id"] == initial["id"])
            text = ""
            if job.get("source_id") and job["status"] == "completed":
                source = await http.get(f"/api/local-sources/{job['source_id']}/text")
                source.raise_for_status()
                text = source.text
            record = {"name": name, "file_sha256": hashlib.sha256(raw).hexdigest(),
                      "bytes": len(raw), "job": job, "extracted_characters": len(text),
                      "page_markers": text.count("<!-- page:"),
                      "elapsed_seconds": round(time.monotonic() - started, 2),
                      "semantic_and_numeric_oracle": "NOT VERIFIED",
                      "scan_only_rejected": job["status"] == "needs_attention"}
            if name.startswith("The_He"):
                left = text.find("cả một thế hệ")
                right = text.find("Điều nghịch lý")
                record["page_2_column_order"] = bool(0 <= left < right)
            original_hash = hashlib.sha256()
            async with http.stream("GET", f"/api/local-sources/pdf-jobs/{job['id']}/original") as download:
                download.raise_for_status()
                record["original_download_private"] = (
                    download.headers.get("cache-control") == "no-store"
                    and download.headers.get("content-disposition", "").startswith("attachment;")
                )
                async for chunk in download.aiter_bytes():
                    original_hash.update(chunk)
            record["original_sha256_matches"] = original_hash.hexdigest() == record["file_sha256"]
            results.append(record)
            print(json.dumps({"name": name, "status": job["status"], "pages": job["pages"],
                              "processed": job["processed_pages"], "characters": len(text)},
                             ensure_ascii=True), flush=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / f"design-work/qa/RELEASE-20261002/pdf-ingestion-live-{stamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps({"model_calls": 0, "samples": results}, ensure_ascii=False, indent=2)
    output.write_text(serialized, encoding="utf-8")
    print(json.dumps({"report": str(output), "samples": len(results), "model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reextract", action="store_true")
    options = parser.parse_args()
    asyncio.run(run(reextract=options.reextract))
