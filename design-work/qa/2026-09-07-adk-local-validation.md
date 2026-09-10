# ADK and local data checkpoint — 2026-09-07

Status: IN PROGRESS, not a production acceptance certificate.

## Scope implemented

- Optional ADK 2.8 adapter with user/session-isolated SQLite persistence, governed
  tools, bounded calls and selective model fallback. LangGraph remains the default
  configuration and rollback path. Existing LangGraph messages remain readable,
  but are not imported into ADK's model context.
- Deterministic Decimal calculator; no expression evaluation or code execution.
- Explicitly saved artifacts, optimistic revision checks, retry deduplication,
  archive and Markdown attachment export. Revision count is NOT version history.
- Local UTF-8 TXT/MD/CSV/notebook imports, bounded size, tenant-filtered name search
  and text reads. Notebook outputs are ignored and code is never executed.
  This is not local vector RAG and does not yet support PDF/DOCX/XLSX imports.
- Drive RAG tool now checks current file access and modified time before releasing
  indexed snippets. Four tests cover fresh/stale/missing metadata/revoked access.
- Direct local-source and artifact export routes now enforce read permission in
  addition to ownership. HTTP tests cover cross-user 404, role 403, nosniff,
  no-store and non-HTML content types.
- Whitespace-only artifact input is rejected without stripping Markdown indentation.
- Pin google-api-core below 2.36 for ADK 2.8's OpenTelemetry compatibility.

## Actual checks in this continuation

- Initial full backend suite: 80 passed, 2 dependency deprecation warnings.
- After blank-input regressions: 87 passed, 2 warnings, 39.51 seconds.
- New HTTP route test: 1 passed, 1.51 seconds. Final aggregate rerun tracked below.
- Ruff check: passed. pip check: no broken requirements found.
- Frontend production build: passed (TypeScript and Vite).
- Local runner configuration: every check reported OK, secrets not printed.
- Server started via scripts/run-local.ps1, ADK process override, loopback only.
- Real browser found previous local-study-smoke.md import after restart (225 chars).
- Real ADK local search/read answered LOCAL-STUDY-2026 and 135 minutes and linked
  the local-source endpoint. Fixture source: backend/tests/fixtures/local-study-smoke.md.
- Next turn requested only a calculator result: rendered 0.3 with no stale citation.
- Browser error log at that point: empty. This is not an all-route network audit.
- Initial browser connection refused because previous process was no longer running;
  startup resolved it. A browser-generated error tab could not be selected under its
  URL policy; a fresh localhost tab loaded successfully. No interstitial bypass.

## Evidence and tooling

Real tools: exec_command, apply_patch, CUA browser/Playwright DOM inspection.
No new design generation or Stitch invocation in this functional validation pass.
Previous Stitch evidence remains in stitch-implementation-report.md.
No external visual assets added. No full-product design score assigned.

## Remaining release gates

- Live Drive/RAG acceptance of latest changes and broader two-user browser tests.
- ADK context handover/compaction and migration acceptance before default cutover.
- Artifact history, more import/export formats, local vector indexing and manifest.
- Streaming/cancellation, source selection, truthful telemetry/feedback dashboard.
- Scoped additional connectors, MCP/A2A and multi-agent workflows from accepted plan.
- Meaningful labelled quality benchmark, claim-level citation checks and human usability.
- Full restore rehearsal. Earlier backup had 19 verified files and SQLite integrity
  checks; this does not prove a complete application restore or cover subsequent data.
- Final all-screen responsive/focus/network QA and operational documentation.

No commit/push or full-product completion claim is made by this checkpoint.

## Final checks and live finding

- Full suite after access-route test: 88 passed, 2 warnings, 17.13 seconds.
- Frontend lint and git diff --check: passed in the same command sequence.
- Real Drive search/read succeeded; trace showed drive_search_files and drive_read_file.
  Primary gemini-3.8-flash and fallback gemini-3.5-flash-lite were both observed.
- Live RAG returned State/Nodes/Edges, but unexpectedly invoked rag_index_drive_file
  despite an existing-index-only instruction. This is a scope-control bug, not a pass.
- Fixed with server-owned requires_user_action policy: index/save tools are hidden
  from both orchestrators and registry rejects non-API attempts, with denied audit.
  Deliberate existing UI/API operations remain available subject to RBAC.
- Removed artificial empty plan events for ADK responses with no planner output.
- Final full backend suite after these fixes: 91 passed, 2 warnings, 15.29 seconds.
  Ruff passed after formatting a long line. Latest server restarted with these patches.
- Live provider logs confirmed gemini-embedding-2 requests returned HTTP 200.

Do not treat the initial RAG answer as scope-compliant. Post-fix live retest is separate.

## Post-fix RAG and citation follow-up

- Real rerun after the action gate called only rag_search (one tool, six trace events).
  No index or read tool appeared. Empty plan event was absent.
- That rerun exposed a second bug: answer cited [7], whereas UI listed six sources.
  Raw chunk positions were available without explicit citation numbering.
- Added ADK source_references numbered by the exact deduplicated current-turn evidence
  order, plus an instruction distinguishing reference numbers from chunk_index.
  This numbering fix is ADK-specific; it does not prove claim-level support or solve
  historical LangGraph citation mapping. A malformed model answer remains possible.
- Two numbering regression tests added. Full suite: 93 passed, 2 warnings, 15.36 seconds.
- Ruff and final git diff --check passed. Server restarted with source-number patch.
- Final real-browser rerun answered all three requested bullets with [2], which exists
  in the displayed six-source list. This demonstrates resolution for this regression
  case, not universal citation correctness. Browser error log remained empty.
- Application left running on http://localhost:8000 with the ADK process override;
  final browser tab retained for inspection. No .env secrets or defaults changed.
