# Creation chat checkpoint and acceptance gate

## Latest user priority

Finish Docs/Sheets, MCP/A2A and ADK multi-agent behavior; stabilize and exercise
every supported product action FIRST. Only then implement/run Evaluation Harness
and the All Harness experience. Other feature expansions are deferred. This is
not a claim of a bug-free product or a completed release.

## Changes in this slice

- ADK's one-generation response now supports up to four typed Docs/Sheets
  proposals. It still has no execution tools or automatic write approval.
- A new `creation_proposals` table persists user/message-bound proposals without
  altering existing message columns. Chat history and POST responses expose owned
  proposals; another account cannot prepare or read them.
- Preparing a saved proposal uses its server-stored spec and stable proposal ID
  as request key. Browser-supplied replacement content is not used.
- Chat UI shows full document/tab/cell/formula/chart-spec previews, separates
  preparation from explicit approval, inspects operation status after errors,
  removes approval after running/success, and links verified output when available.
- Reused the current Fluent components, table styling and product design system;
  no new independent visual direction or third-party assets.

## Evidence

- Full backend suite: **154 passed, 13 dependency warnings, 33.70 s**.
  JUnit: `design-work/qa/validation-creation-regression.xml`.
- Targeted Ruff checks pass. `git diff --check` passes.
- TypeScript/Vite production build passes, latest build 35.51 s.
- Real Chrome DevTools browser against `scripts/qa_creation_ui.py`, isolated
  loopback port 8002, serving the actual frontend build and clearly labelled
  synthetic data. No credentials, live model or Google write in this fixture.
- Actual UI: open saved chat, see both proposals, expand Sheets data, prepare,
  confirm, inspect succeeded state and absence of another approval button.
- Desktop inspected at innerWidth 1366: no root horizontal overflow. At final
  emulated 390 px: `innerWidth == documentElement.scrollWidth == 390`.
- An early inline desktop screenshot revealed cramped table cells; the component
  now reuses `.table-scroll` and translates chart type labels into Vietnamese.
- Browser control limitation: select `fill` timed out; click/ArrowDown/Enter
  worked. Some node IDs expired after viewport changes; snapshots were refreshed.
  Approval click reported timeout, but subsequent authoritative snapshot confirmed
  succeeded state, so it was NOT resent.
- Saving screenshot to repo failed with the MCP server's configured-root access
  denial. A later inline screenshot hung and its orchestration cell was terminated.
  No final screenshot file or complete visual acceptance is claimed.
- Existing real runtime remains PID 16060 on 127.0.0.1:8000; it has NOT been
  restarted to load the new backend/table initialization in this slice.

## Evaluation source intake only (no evaluation started)

User confirmed only `C:/Users/Bao Phuc/Downloads/Evaluation-Harness.pdf`, plus the
two provided screenshots, are required. PDF skill used with bundled pypdf to read
all 17 pages; Poppler rendered pages 9–12 and those renders were inspected.
Initial failures: project Python lacks pypdf; bundled Python required `-X utf8`;
PyMuPDF was absent, so the available bundled Poppler renderer was used.
Pages 4–5 are primarily images: supplied screenshot covers page 5, page 4 still
needs visual inspection. Source links on pages 9–10 may need follow-up extraction.

Intake requirements: versioned golden dataset; final task success distinct from
trajectory checks; automatic retrieval/ranking metrics distinct from semantic
Judge scores; rubric and evidence summaries; separate human review/calibration;
repeatable regression/A-B results; no invented official benchmark scores. Codex
Judge scores must not be called human judgments. No evaluation results yet.

## Remaining release gates (all must be resolved before Evaluation)

- Start updated real runtime safely and verify existing data/login are retained.
- Live Gemini creation-schema acceptance, then real Google Docs/Sheets creation,
  returned links, content/formula/chart checks, edit workflows and revision risks.
- Current Docs edit executor has no finished chat edit UI; Sheets edits remain
  unimplemented. Approval-expiry recovery and pending/uncertain UX need more tests.
- MCP/A2A connection UX, tenant and token tests, actual protocol client smoke tests.
- ADK multi-agent orchestration requested in newest scope is not implemented.
- Exercise all existing Drive/RAG/Memory/local/artifact/permission/audit/settings
  actions, restart persistence, connection errors, quota failures, and isolation.
- Full keyboard, loading/error states, console/network review, screenshots and
  live end-to-end acceptance remain incomplete. Do not treat unit tests or fixture
  success as proof that Google integrations pass.
