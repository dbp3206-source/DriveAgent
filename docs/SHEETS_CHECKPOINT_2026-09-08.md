# Sheets implementation checkpoint — not final acceptance

## Implemented

- `services/sheet_creator.py`: typed workbook, up to ten uniquely named tabs,
  10,000 data cells total and a bounded serialized payload. Explicit string,
  number and boolean values prevent formula injection from imported text.
- Structured local SUM/AVERAGE/MIN/MAX/COUNT formulas; numeric-only source ranges
  reject cycles, external imports and arbitrary formula execution. Read-back
  checks the stored formula and independently calculated numeric result.
- Optional COLUMN/BAR/LINE charts tied to validated numeric data. Verification
  checks chart identity, title, type and source ranges, plus every expected cell.
- All tab/cell/chart data is sent in one create request, with no automatic write
  retry. Persisted resource ID precedes read-back so failed verification does not
  hide a created Google file.
- `/api/sheets/prepare`, `/approve`, `/operations/{id}` registered in the app;
  same-origin request, current application write permission and `drive.file`
  consent are required. Model gathering and protocol callers cannot approve.
- Existing durable ledger provides user isolation, digest-bound approval,
  pending expiry, atomic claim and an uncertain state after execution failure.
  Repeated execution cannot create a second workbook for the same operation.

## Actual verification

- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q
  --junitxml=design-work/qa/validation-sheets-regression.xml`:
  **152 passed, 13 dependency deprecation warnings, 32.36 seconds**.
- Targeted Ruff checks passed for the new Sheets modules, app registration and
  the affected tests. Formatter ran on new test/service/tool modules.
- Existing running server `/api/health`: HTTP 200. It was NOT restarted in this
  slice, so this health result does not prove the new routes are deployed there.
- Google boundary was mocked: tests cover create/checkpoint ordering, no retries,
  read-back mismatch, formula errors, chart changes, user/scope policy and ledger
  success/failure/repeat behavior. No paid model call or real Google write occurred.
- One final validation condition was reordered to reject oversized integers
  before float conversion; targeted tests were rerun after that small change.

## Not yet complete

- This is a backend creation slice, not a completed Sheets user experience.
  Compiler proposal generation and the reviewed nontechnical UI are still needed.
- Google Sheets API must be enabled, and the user must consent to the opt-in
  Workspace permission before real end-to-end creation acceptance.
- Existing-workbook edits are not implemented here. Sheets does not expose the
  same required-revision guard as Docs; do not claim race-free editing simply
  because a batch update is atomic. Arbitrary formulas are intentionally unsupported.
- Chart read-back is structural, not rendered visual QA; no chart screenshot or
  workbook rendering is claimed. Large-number precision is bounded but not a
  substitute for a financial-decimal engine.
- Slides, Visual, Skills, compiler bundle integration and final whole-product
  benchmark remain pending. Sandbox, Gmail, dashboard and expanded import remain
  deferred by the user, not accidentally included in this milestone.
- The requested YouTube reference could not be read by the web tool (Internal
  Error). No benchmark claims are attributed to the unviewed video.

## References

- Google Sheets cell contract:
  https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/cells
- Atomic batch semantics and collaboration caveat:
  https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate

No external templates, design assets, or third-party source code were copied.
No design skill invocation or browser visual acceptance is claimed in this slice.
