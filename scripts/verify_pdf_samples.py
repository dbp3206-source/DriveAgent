"""Check the locked six-source manifest locally, without uploading or model calls.

Run with the bundled PDF runtime (pypdf), or a Python environment containing it.
This proves source preparation only, never retrieval or answer quality.
"""

import argparse
import hashlib
import json
from pathlib import Path


def verify_samples(manifest: dict, directory: Path) -> list[dict]:
    from pypdf import PdfReader

    records = []
    for source in manifest["sources"]:
        filename = source["filename"]
        if Path(filename).name != filename:
            raise ValueError("Manifest filenames must not escape the sample directory")
        path = directory / filename
        if not path.is_file():
            records.append({"source": source["id"], "status": "FAIL", "reason": "missing"})
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source["sha256"]:
            records.append({"source": source["id"], "status": "FAIL", "reason": "checksum"})
            continue
        reader = PdfReader(path)
        lengths = [len((page.extract_text() or "").strip()) for page in reader.pages]
        records.append({
            "source": source["id"], "sha256": digest, "bytes": path.stat().st_size,
            "pages": len(lengths),
            "pages_without_native_text": [i + 1 for i, length in enumerate(lengths) if length < 40],
            "status": "PASS" if len(lengths) == source["pages"] else "FAIL",
            "scope": "Checksum/page inspection only; product parser and live answers not verified",
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", required=True, type=Path)
    args = parser.parse_args()
    manifest_path = Path(__file__).resolve().parents[1] / "backend/evals/pdf_acceptance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = verify_samples(manifest, args.samples)
    print(json.dumps({"model_calls": 0, "uploads": 0, "sources": records}, ensure_ascii=True, indent=2))
    return 0 if all(record["status"] == "PASS" for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
