# Drive recovery checkpoint — 2026-09-08

Scope: fix the current unusable Drive/chat flows before continuing Slides/Sheets,
Visual and reusable Skills. Sandbox and Gmail are deferred by the user's latest request.

## Root causes and fixes

1. The old local server ran with restricted outbound network access. Its log showed
   `Access is denied` for Google endpoints. Restarted the owned server with approved
   outbound network access; kept its listener on 127.0.0.1:8000.
2. ADK's output_schema generated the legacy responseSchema representation with
   additional_properties, rejected by Gemini with HTTP 400. The compiler now sends
   response_json_schema while retaining strict local Pydantic validation. Explicit
   SDK automatic function calling is disabled; ADK still permits one model round.
3. Drive full-text search returned a filename match plus documents mentioning that
   filename. The compiler now prefers a unique exact name before reading; duplicate
   exact names still require the user to disambiguate.
4. Deterministic routing missed explicit rag_search, the latest-file homepage prompt,
   saved-preference prompt and Google Docs titles without extensions. Added routes
   and regressions. Latest-file reads exclude folders and retain Drive's modified-time
   ordering. Explicit RAG selection takes precedence over a filename in the prompt.
5. Gemini 3.8 Flash returned 503 high-demand errors twice after the schema fix.
   Gemini 3.5 Flash Lite returned OK in a small probe and then completed both live
   acceptance prompts. Changed the local .env chat-model line to 3.5 Flash Lite,
   within the user's approved model choices. Embedding remains Gemini Embedding 2.
   This is an explicit configuration change; there is no automatic model fallback.
6. Chat now maps known Gemini quota/capacity/configuration errors to fixed actionable
   explanations with the app request ID, without returning raw provider payloads.
7. run-local.ps1 detects an occupied port before building. It reports how to use or
   stop the old instance and never kills the process owning the port automatically.
8. The default-config test now clears relevant process variables, because SDK dotenv
   loading had allowed the user's selected live model to affect a defaults assertion.

## Actual live checks

- Existing authenticated in-app browser: Drive list displayed real files.
- Search for langgraph-react-agent.ipynb displayed the notebook plus a PDF mentioning
  its name, reproducing the exact-name disambiguation case.
- Read preview displayed the notebook's text, including State/Nodes/Edges definitions.
- RAG prompt: successfully answered State/Nodes/Edges with matching citation [1].
  Real persisted trace: rag_search success, model gemini-3.5-flash-lite, one call;
  5,867 input tokens / 220 output tokens reported by provider.
- Search/read/summarize prompt: successful source-backed summary of the notebook.
  Real persisted trace: drive_search_files success, drive_read_file success, one
  gemini-3.5-flash-lite call; 5,269 input tokens / 118 output tokens.
- Existing canonical chat history remained available after restarts.
- UI production build succeeded and local config checks passed.
- Final regression evidence is saved at
  `design-work/qa/validation-drive-regression.xml`.
  Full backend suite: **128 passed**, 13 dependency deprecation warnings, 49.49 s.
- Ruff checks passed for the changed compiler, routing, chat and regression tests.

## Limits of this checkpoint

This restores the reproduced core Drive/chat/RAG failures. It is not a claim that
every possible file type, prompt, OAuth account, or future Google outage has been
tested. Google service availability remains external. No user documents were edited,
no email was sent, no paid fallback was enabled, and no credentials were exposed.

Slides/Sheets creation, Visual and Skills are not accepted as complete here. The
previous Docs backend remains mock-tested pending its UI and live write acceptance.
The latest-file and preference routes have automated regression coverage; they were
not exercised with additional live model calls in this checkpoint.

Use `scripts/run-local.ps1` from the user's normal PowerShell after reboot. When
started by a coding tool with restricted network access, approve outbound Google
access for the local server; a listening localhost port alone does not prove that
the server can reach Drive or Gemini.

At handoff the runner was launched in a separate hidden PowerShell process so its
lifetime does not depend on the test terminal. Local server logs are under
`data/logs/recovery-server.out.log` and `data/logs/recovery-server.err.log` (ignored
application data, not public QA artifacts). The access log remains disabled to avoid
recording OAuth callback query strings.

## Reference

Google structured-output contract:
https://ai.google.dev/gemini-api/docs/generate-content/structured-output
