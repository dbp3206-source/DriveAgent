# V2 source audit — 2026-09-08

Source of truth: current dirty worktree; preserve all previous changes.

The table below records the initial audit, not the latest implementation state.
See `V2_PROGRESS_2026-09-08.md` for the tested ADK/quota/protocol/Docs checkpoint.

| Area | Actual implementation | Reuse / gap |
|---|---|---|
| Entry | app/main.py FastAPI lifespan | Shared registry, local SQLite/Qdrant |
| Chat | api/chat.py, db Message/ChatSession | User-isolated history independent of framework |
| ADK | agent/adk_orchestrator.py, google-adk 2.8 | Persisted session, tools, multiple model rounds; not quota-first |
| Legacy | agent/orchestrator.py LangGraph | Planner + tools + fallback; expensive under 20 RPD |
| Embedding | services/embeddings.py | Gemini Embedding 2, individual text requests; no durable quota |
| RAG | services/rag.py | Local hybrid fusion, checksum skip, online freshness/access gate |
| Memory | services/memory.py | User-filtered SQLite/Qdrant, dedup, secret filtering |
| Tools | tools/registry.py, contracts.py | RBAC, OAuth, schema, rate/timeout/retry, audit, explicit-action gate |
| Google | auth/google_oauth.py, tools/drive.py | Encrypted per-user OAuth; read-only scopes by default |
| UI | frontend/src/App.tsx and pages | Fluent/React, rounded existing design; preserve, no dashboard/import expansion |
| Verification | backend/tests, scripts/verify.ps1 | Baseline last checkpoint 93 tests; rerun after changes |

Seven requested knowledge tools exist and must remain registered. Existing calculator,
local text sources and saved artifacts also remain. No Workspace/Gmail creators or
MCP/A2A adapters currently exist. Docker/Podman were not found on PATH during audit;
ordinary Python subprocess is NOT an acceptable execution sandbox.

## Accepted updated scope

Single agent, deterministic gather → one ADK compiler call → typed specs → executors
→ verification. MCP/A2A are interoperability boundaries, not extra reasoning agents.
Only the five requested creation groups; dashboard/import expansion is deferred.
Google writes require appropriate incremental OAuth and risk/approval handling.
No live Gmail send or edits to user's existing artifacts during QA without exact approval.

## External constraints researched

- https://ai.google.dev/gemini-api/docs/rate-limits : quotas per project, daily reset Pacific midnight.
- https://ai.google.dev/gemini-api/docs/billing : free and paid tiers depend on billing configuration.
- https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization : transport auth boundaries.
- https://a2a-protocol.org/v0.3.0/specification/ : authenticated AgentCard/task contract.

User confirmed on 2026-09-08 that the configured project is Free tier without billing.
Local accounting cannot observe other apps using the same Google project, nor prove
that billing will never be changed later. No paid fallback should run automatically.

## Milestones (not completion claims)

1. Durable quota guards, single-call ADK compiler, deterministic routes/context handover.
2. Typed Workspace creators/patches with validation, approvals and result verification.
3. Deterministic local visuals and isolated workspace execution (fail closed if unavailable).
4. Gmail draft-first and reusable procedures; protocol adapters with tenant boundaries.
5. Regression, protocol integration, real local verification, setup/docs and limitations.
