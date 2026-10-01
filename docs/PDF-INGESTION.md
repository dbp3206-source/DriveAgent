# PDF ingestion: bounded, durable, owner-scoped

## Scope decision — 2026-09-30

The owner explicitly removed OCR from the release plan because recognition quality
was insufficient. `DRIVE_AGENT_PDF_OCR_ENABLED=false` is the product default.
PDF text layers remain supported; scanned/image-only pages report `unsupported_scan`
and `pdf_ocr_excluded`, never empty success. OCR/table-image accuracy is EXCLUDED, not
an outstanding required gate. Historical OCR tests/outputs remain evidence, not a
certification or a supported beta capability. No original file was deleted.

Upload PDF on **Tài liệu local**, up to 25 MiB per file. Text formats retain their
2 MB limit. The backend streams upload size checks and queues one serial worker.
Each page runs in a bounded subprocess; closing the browser does not cancel it.
Progress and checkpoints live in the application SQL database, not in browser memory.

There are at most four pending PDF jobs and 200 MiB of uploaded PDFs per user.
Upload reservations are serialized per owner in the local process and additionally
lock the owner row in PostgreSQL. Duplicate inputs reuse the existing job. The
application does not accept a fifth queued PDF or an upload above the owner's cap.

## Reading and verification

Native text uses pdfplumber, with persistent-gutter two-column reading for unambiguous
prose and separate Markdown tables. Ambiguous or mixed layouts require source review.
Extracted sections retain `<!-- page:N -->` markers. A text-ready job is not proof of
semantic indexing or factual answer quality. Do not equate character count with fidelity.

Chat reads explicitly named local PDFs through owner-scoped keyword retrieval over
page-aware chunks. Each named file is queried separately, so one file cannot displace
the other from the evidence window. This path does not require an embedding API call.
The bounded retrieved excerpts are not a claim that every page has been reviewed.

The following OCR configuration is retained for historical/optional developer tests,
not required setup or part of closed-beta support:

```dotenv
DRIVE_AGENT_PDF_TESSERACT_BINARY=C:/path/to/tesseract.exe
DRIVE_AGENT_PDF_PDFTOPPM_BINARY=C:/path/to/pdftoppm.exe
DRIVE_AGENT_PDF_TESSDATA_DIR=C:/path/to/tessdata
```

The tessdata directory must contain `vie.traineddata` and `eng.traineddata`.
It does not need a `configs/tsv` file: the worker enables the TSV renderer directly.
TSV parsing treats literal quotation marks as document text, not CSV delimiters.
Low-confidence pages are retried at quarter-turn orientations within one 75-second
OCR budget; the selected rotation is retained as metadata. This is not a table-cell
reconstruction guarantee. Blank scans/illustrated covers can still require review.
OCR runs with one OpenMP thread. Confidence below 75/100 is excluded from retrieval;
confidence is not a guarantee that financial figures are correct. Check numbers on
the original page. Missing dependencies produce **Cần kiểm tra**, not empty success.

## Recovery and source evidence

- Cancel stops queued/running work and fences its lease so a stale worker cannot publish.
- Resume retains verified preceding pages and starts at the first uncertain page.
- Owner API `POST /api/local-sources/pdf-jobs/{id}/reextract` rereads the original after
  parser changes and updates the existing source rather than duplicating it.
- Owner API `GET /api/local-sources/pdf-jobs/{id}/original` downloads the original PDF;
  it uses attachment disposition, no-store and a sandbox policy. Other users receive 404.
- Failed jobs do not discard their source input or checkpoint. Application restart
  recovers expired leases. Three automatic attempts bound repeated failure.

## Current release limitations

The new serial PDF worker publishes keyword-readable sources. PDF semantic embedding,
shared Drive integration, full six-document numeric oracles, public Storage persistence
are not yet certified. These remain release gates. OCR itself is explicitly excluded.
The original six supplied PDFs and QA renders are private, not redistribution assets.

pdfplumber's upstream MIT license was inspected at
https://raw.githubusercontent.com/jsvine/pdfplumber/stable/LICENSE.txt.
Preserve its copyright/license when redistributing bundled dependencies.
