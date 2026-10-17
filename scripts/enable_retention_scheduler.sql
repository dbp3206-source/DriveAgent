-- Run in the Supabase SQL Editor as postgres only after the matching Veridra
-- image is Live and /api/internal/scheduler/retention is available.
-- No user content or credential is returned. The bearer value is read from Vault
-- only when the job runs; this SQL stores no plaintext secret.

DO $preflight$
BEGIN
    IF to_regprocedure('net.http_post(text,jsonb,jsonb,jsonb,integer)') IS NULL THEN
        RAISE EXCEPTION 'pg_net http_post is not installed with the expected signature';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM vault.decrypted_secrets
        WHERE name = 'veridra_scheduler_bearer_token'
    ) THEN
        RAISE EXCEPTION 'Required scheduler token is missing from Vault';
    END IF;
END
$preflight$;

-- Keep the pg_net network functions and internal tables out of Data API roles.
-- The scheduled postgres job remains able to call them. Reapply these revokes
-- after any pg_net extension upgrade.
REVOKE ALL PRIVILEGES ON SCHEMA net FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA net FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA net FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA net FROM PUBLIC, anon, authenticated;

DO $schedule$
DECLARE
    existing_job record;
BEGIN
    FOR existing_job IN
        SELECT jobid FROM cron.job WHERE jobname = 'veridra-retention-auto-15m'
    LOOP
        PERFORM cron.unschedule(existing_job.jobid);
    END LOOP;

    PERFORM cron.schedule(
        'veridra-retention-auto-15m',
        '*/15 * * * *',
        $cron$
            SELECT net.http_post(
                url := 'https://veridra-closed-beta.onrender.com/api/internal/scheduler/retention',
                headers := jsonb_build_object(
                    'Content-Type', 'application/json',
                    'Authorization', 'Bearer ' || (
                        SELECT decrypted_secret
                        FROM vault.decrypted_secrets
                        WHERE name = 'veridra_scheduler_bearer_token'
                    )
                ),
                body := '{}'::jsonb,
                timeout_milliseconds := 60000
            );
        $cron$
    );
END
$schedule$;

-- Verify only the job name/schedule and schema isolation; do not query the Vault value.
SELECT jobname, schedule, active
FROM cron.job
WHERE jobname = 'veridra-retention-auto-15m';

SELECT
    has_schema_privilege('postgres', 'net', 'USAGE')
    AND has_function_privilege(
        'postgres', 'net.http_post(text,jsonb,jsonb,jsonb,integer)', 'EXECUTE'
    ) AS scheduler_role_can_call_net,
    NOT has_schema_privilege('anon', 'net', 'USAGE')
    AND NOT has_schema_privilege('authenticated', 'net', 'USAGE') AS api_roles_blocked_from_net;
