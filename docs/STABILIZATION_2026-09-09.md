# Stabilization checkpoint — Evaluation remains gated

## Executed evidence

- Full backend regression after shallow Gemini wire-schema fix: **160 passed,
  13 dependency deprecation warnings, 30.63 seconds**. JUnit evidence:
  `design-work/qa/validation-stabilization.xml`.
- Actual application at localhost:8000, authenticated browser, Gemini
  `gemini-3.5-flash-lite`: one request produced both typed Docs and Sheets
  proposals. No recurrence of the previous HTTP 400 in this request.
- Browser previews matched the requested document text and two spreadsheet
  rows (Sách 120; Xe buýt 30), with a column chart proposal. This is synthetic
  acceptance content, not user financial data. No Google files created yet.
- Preparing the document correctly stopped on missing `drive.file` permission.
  User approved starting the OAuth upgrade; Google account chooser opened for
  the user to complete consent. Do not claim the permission has been granted.
- A second live chat request searched and read langgraph-react-agent.ipynb.
  Response contained three requested points and a Drive citation; UI trace
  reported drive_search_files and drive_read_file completed, one ADK generation,
  model gemini-3.5-flash-lite. No creation proposals for this read request.
- Memory page retained existing records after the server restart.

## Newly reproduced defect

Searching Memory for `DA-QA-NO-MATCH-20260909` returned both unrelated stored
preferences. Service uses semantic ranking; a minimum-relevance/no-match policy
needs investigation and regression coverage. Not fixed or accepted yet.

## Still open

- Complete user OAuth consent, then verify actual Docs/Sheets creation and
  read-back, formulas/charts, duplicate prevention and failure recovery.
- Full current-feature browser acceptance, tenant isolation, protocol clients,
  edit flows, keyboard/mobile/console/network checks and final screenshots.
- Existing checkpoint documents contain historical runtime PIDs; they are not
  statements about the currently running process.
- No Evaluation implementation/run and no all-features/bug-free release claim.

Tools actually used for this checkpoint: PowerShell pytest through the project
virtual environment, and CUA browser actions/accessibility snapshots. No design
generation, judge scoring, or final visual-quality pass occurred in this slice.
