# Chat durable execution — candidate, not release certification

Implemented owner-scoped SQL task queue, duplicate submission keys, bounded pending
requests, two workers, 120-second fenced leases and three recovery attempts. New-session
user message is persisted at enqueue. Completed answer/proposals and task result checkpoint
share one transaction. Explicit cancellation revokes publication rights; process shutdown
leaves a recoverable lease. Worker restart re-executes an unfinished whole turn, not a
token-level continuation. Ambiguous memory saves stop automatic recovery. Provider calls
can consume quota again after interruption. Google approval writes remain outside Chat.

Frontend sends to `/api/chat/tasks`, polls persisted state and discovers pending tasks after
reload. Polling retries transport/server outages, but not authentication errors. Closing a
tab stops observation without cancelling server work. Cancel is a separate authenticated call.

Actual checks so far:

- Queue lifecycle tests expanded to duplicate retries, ambiguous memory writes, cancellation
  of completed tasks, in-flight cancellation and a real disposable worker process crash.
  The process crash used only the isolated SQLite fixture and a synthetic model; after a
  fresh process resumed the expired lease, there were exactly two messages and attempt 2.
  Lease eligibility was advanced in the fixture rather than sleeping for 120 seconds.
- Full backend: 847 passed / 9 PostgreSQL skipped, coverage 85.37%, 140.48 seconds.
- Frontend: 142 passed; lint and production build passed.
- Browser on local restarted runtime: sent synthetic one-line math prompt, reloaded while
  pending, answer `2 + 2 = 4` appeared afterward. SQL task `1cf446c0-e71e-4e6e-9725-01f203b92865`
  completed on attempt 1 with exactly two messages. No captured console error. One live
  synthetic model turn, no Google writes, no private documents sent.
- PostgreSQL parallel claim/duplicate submit/isolation test added for isolated CI only;
  not yet executed locally. More cancel/fault tests and deployed restart evidence required.

Compatibility: direct `/api/chat` remains the synchronous 60-second API for existing clients;
the product's Chat screen uses the durable `/api/chat/tasks` API. Cloud pool connections are
released after credential resolution before ADK starts its independent tool sessions. There
are two Chat workers, not four unlimited concurrent model loops. Four users can queue their
own requests; concurrent cloud latency/resources still require actual staging measurements.

No production-ready claim. Cloud URL, actual OAuth/BYOK multi-user behavior, restored database
and Storage, full live oracle/holdout benchmark and final same-build verification remain HOLD.
