# Veridra operations

## Resource-light default (2026-09-30)

Use `scripts/run-local.ps1` without `-WithLocalLangfuse` for normal development
and local use. Docker and the six-service Langfuse stack are optional; do not
start them automatically for Chat. Keep metadata logs/metrics/traces in the app
and use the native Windows dashboard path below when resources permit.

Historical Docker/Langfuse checks below do not certify the current build or
require that stack to stay running. No container, volume, image or cache has
been deleted to implement this resource policy. See `docs/RESOURCE-PROFILE.md`.

## Local Langfuse / OpenTelemetry (verified 2026-09-30)

The dedicated metadata-only project runs at `http://localhost:3035`. This is
not Langfuse Cloud. The app, MinIO and dashboards bind published ports to
loopback. PostgreSQL, ClickHouse, Redis and the worker have no host ports.

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe scripts\provision_langfuse_local.py
docker compose --env-file ops/secrets/langfuse.env -f docker-compose.langfuse.yml up -d
.\scripts\run-local.ps1 -WithLocalLangfuse
```

Provisioning creates secrets once and refuses to replace them. The current
`ops/secrets` directory has an owner-only ACL. Read your generated login from
`ops/secrets/langfuse-owner-login.txt` privately; do not paste it into chat or
Git. The credentials in that file are for the new local installation, not a
Grafana account. Image digests are pinned to the versions actually exercised.

Open **Tracing** in the `Veridra metadata-only` project. Request/agent/tool
spans retain parent-child links; allowlisted attributes are request ID, tool,
HTTP status and outcome. No prompts, mail bodies, arguments, exception text,
identity or keys are forwarded. Grafana continues to show Prometheus metrics;
it is not a second trace store. A healthy trace does not certify answer quality.

The app checks expired allowlisted root traces hourly using the free public
API. A synthetic 31-day-old trace was ingested, deleted and read back as absent,
while the current trace survived. The dedicated MinIO `langfuse` bucket has an
enabled 30-day lifecycle rule. Deletion is asynchronous and is not an exact
second-level purge guarantee. Keep the app running for scheduled cleanup;
recheck retention after any redeploy or restore. No enterprise retention
feature was enabled.

Real evidence: `scripts/qa_langfuse_local.py`, `qa_app_langfuse.py` and
`frontend/scripts/qa-langfuse-local.mjs`. The last one signs into the synthetic
local owner account and verifies a rendered request trace without printing its
password. Results and screenshots stay under `design-work/qa/`.

This six-service stack consumes significant RAM/disk. It is a local single-node
installation, not HA. Backups of the Veridra app volume do **not** include the
separate Langfuse database/object-store volumes. Never run `compose down -v`
unless deleting those exact stores is intended.

Licenses inspected: Langfuse upstream commit
`09a1b8484b66c4c4cbaf4ba972fc11bd699d4784` is MIT outside `ee/` paths; enterprise
paths carry additional restrictions. MinIO's bundled client identifies AGPLv3.
These are separately deployed services, not bundled proprietary app code;
review obligations before modifying, redistributing or commercially packaging
their images. No third-party GetLayers template or asset was copied.

## AgentOps dashboard

1. Set a long random `DRIVE_AGENT_METRICS_BEARER_TOKEN` in the app environment.
2. Put the same value in `ops/secrets/metrics_token` and a separate strong Grafana
   password in `ops/secrets/grafana_admin_password` (both are git-ignored).
3. Start the API on port 8000 and run
   `docker compose -f docker-compose.observability.yml up -d`.
4. Open Grafana at `http://localhost:3001`. Prometheus is at port 9090.

Metrics contain tool names, status, aggregate latency, token counts and run counts;
they do not contain prompts, email text, document text, filenames or recipient addresses.

### Native Windows QA path

For a local verification run without Docker, the checked-in configs are
`ops/native/prometheus.yml` and `ops/native/grafana.ini`. Prometheus 3.15.0 and Grafana
10.1.5 are checksum-verified under `tools/`; keep both listeners on loopback. Start the
API and Prometheus first, then run `scripts/run-grafana-native.ps1`. It sets the provisioning
and persistent data paths explicitly, loads the checked-in dashboard and Prometheus datasource,
and refuses to start if port 3001 is occupied. Data remains in `data/grafana`. On Windows
Grafana may log an access-denied symlink warning for the dashboard directory; it falls back to
the original path and the dashboard remains usable. Treat a healthy target and rendered panels
as the acceptance signal, not the absence of that non-blocking warning.

## Public demo

Do not expose a development instance. Set production mode, an HTTPS public URL,
closed-beta invite list, an explicit owner email included in that list, a unique app secret,
disabled demo login and the conservative
quota profile. Use an authenticated Cloudflare Tunnel or a hardened VPS reverse proxy.
The application startup guard rejects an unsafe production configuration.
Production also requires an absolute `DRIVE_AGENT_STATE_DIR`; the configured SQLite
database and embedded Qdrant directory must both be inside it. This check only
enforces path consistency. Verify the host volume survives an actual restart and
redeploy before claiming persistence; a Free host's ephemeral directory will not.
`scripts/backup-local.ps1` and `scripts/restore-local.ps1` cover repository-local
`data/` only and create unencrypted copies. Do not use them for a mounted
production `STATE_DIR`.

### Encrypted STATE_DIR backup and isolated restore

`scripts/state_archive.py` backs up the complete `STATE_DIR` into a new,
authenticated AES-GCM archive. It includes SQLite sidecars, Qdrant and any
other files in the state tree; it excludes `.env` and OAuth client JSON outside
the tree. The archive must be copied to encrypted storage **outside the mounted
volume** under owner-only access. Keep its passphrase in a separate secret
manager; losing the passphrase makes the backup unreadable.

1. Stop the Veridra process and every other writer to `STATE_DIR`; the script
   also refuses backup while the configured local port is listening. Confirm
   the state tree is quiescent, especially on a remote host.
2. From the repository root, use the backend virtual environment and supply
   paths for your actual persistent volume and new off-volume archive:

   ```powershell
   .\backend\.venv\Scripts\python.exe scripts\state_archive.py backup --source "X:\veridra-state" --output "Y:\encrypted-backups\veridra-20260929.vstate" --port 8000
   ```

   The tool prompts for a passphrase (at least 16 characters); it never accepts
   one on the command line. `VERIDRA_BACKUP_PASSPHRASE` is supported for a
   managed noninteractive job, but do not leave it in shell history or scripts.
3. Restore into a **new** directory on a separate test host/volume, never over
   the live state tree:

   ```powershell
   .\backend\.venv\Scripts\python.exe scripts\state_archive.py restore --archive "Y:\encrypted-backups\veridra-20260929.vstate" --destination "X:\veridra-restore-test"
   ```

   Restore verifies the encrypted stream, file sizes and SHA-256 manifest
   before exposing the destination. Then configure a separate test instance
   with that directory, restart it, and read back representative chat, skills,
   artifacts and RAG data. This final host-level step is still required; a
   successful archive command alone is not a production backup gate.
