"""Read-only live smoke for private DriveAgent surfaces; never prints user content."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from qa_google_read_smoke import BASE, _cookie


def get_json(path: str, cookie: str):
    request = urllib.request.Request(
        BASE + path,
        headers={
            "Cookie": f"drive_agent_session={cookie}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return (
            response.status,
            response.headers,
            json.loads(response.read().decode("utf-8")),
        )


def safe_failure(exc: Exception) -> dict[str, object]:
    return {
        "type": type(exc).__name__,
        "http_status": getattr(exc, "code", None),
    }


def main() -> None:
    cookie = _cookie()
    result: dict[str, object] = {
        "cloud_writes": 0,
        "local_registry_reads_may_append_metadata_audit": True,
        "surfaces": {},
        "failures": [],
    }
    failures: list[dict[str, object]] = result["failures"]  # type: ignore[assignment]

    def read_surface(name: str, path: str):
        try:
            _status, _headers, payload = get_json(path, cookie)
            result["surfaces"][name] = payload
            return payload
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            ValueError,
            KeyError,
        ) as exc:
            failures.append({"surface": name, **safe_failure(exc)})
            return None

    local_sources = read_surface("local_sources", "/api/local-sources")
    if isinstance(local_sources, list):
        local_summary: dict[str, object] = {"status": "ok", "count": len(local_sources)}
        if local_sources:
            source_id = urllib.parse.quote(
                str(local_sources[0].get("id") or ""), safe=""
            )
            request = urllib.request.Request(
                f"{BASE}/api/local-sources/{source_id}/text",
                headers={"Cookie": f"drive_agent_session={cookie}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    text = response.read().decode("utf-8")
                    local_summary["sample_read"] = {
                        "status": response.status,
                        "chars": len(text),
                        "no_store": "no-store"
                        in response.headers.get("Cache-Control", ""),
                        "nosniff": response.headers.get("X-Content-Type-Options")
                        == "nosniff",
                    }
            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                UnicodeDecodeError,
            ) as exc:
                failures.append({"surface": "local_source_read", **safe_failure(exc)})
                local_summary["sample_read"] = {"status": "error"}
        result["surfaces"]["local_sources"] = local_summary
    elif local_sources is not None:
        failures.append({"surface": "local_sources", "type": "UnexpectedShape"})

    artifacts = read_surface("artifacts", "/api/artifacts")
    if isinstance(artifacts, dict) and isinstance(artifacts.get("items"), list):
        items = artifacts["items"]
        artifact_summary: dict[str, object] = {
            "status": "ok",
            "count": len(items),
            "kinds": sorted(
                {str(item.get("kind")) for item in items if isinstance(item, dict)}
            ),
        }
        if items:
            artifact_id = urllib.parse.quote(str(items[0].get("id") or ""), safe="")
            try:
                request = urllib.request.Request(
                    f"{BASE}/api/artifacts/{artifact_id}/export",
                    headers={"Cookie": f"drive_agent_session={cookie}"},
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    body = response.read().decode("utf-8")
                    artifact_summary["export"] = {
                        "status": response.status,
                        "markdown": response.headers.get_content_type()
                        == "text/markdown",
                        "attachment": "attachment;"
                        in response.headers.get("Content-Disposition", ""),
                        "chars": len(body),
                        "markdown_heading": body.startswith("# "),
                        "no_store": "no-store"
                        in response.headers.get("Cache-Control", ""),
                    }
            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                UnicodeDecodeError,
            ) as exc:
                failures.append({"surface": "artifact_export", **safe_failure(exc)})
                artifact_summary["export"] = {"status": "error"}
        result["surfaces"]["artifacts"] = artifact_summary
    elif artifacts is not None:
        failures.append({"surface": "artifacts", "type": "UnexpectedShape"})

    memories = read_surface("memories", "/api/memories")
    if isinstance(memories, dict) and isinstance(memories.get("memories"), list):
        rows = memories["memories"]
        result["surfaces"]["memories"] = {
            "status": "ok",
            "active_count": len(rows),
            "kinds": sorted(
                {str(item.get("kind")) for item in rows if isinstance(item, dict)}
            ),
        }
    elif memories is not None:
        failures.append({"surface": "memories", "type": "UnexpectedShape"})

    skills = read_surface("skills", "/api/skills")
    skill_items = (
        skills.get("data", {}).get("items") if isinstance(skills, dict) else None
    )
    if isinstance(skill_items, list):
        daily = next(
            (
                item
                for item in skill_items
                if isinstance(item, dict) and item.get("name") == "daily_news_brief"
            ),
            None,
        )
        result["surfaces"]["skills"] = {
            "status": "ok",
            "active_count": len(skill_items),
            "daily_news_brief_revision": daily.get("revision") if daily else None,
        }
    elif skills is not None:
        failures.append({"surface": "skills", "type": "UnexpectedShape"})

    overview = read_surface("agentops", "/api/harness/overview")
    if isinstance(overview, dict):
        runtime = overview.get("runtime", {})
        window = overview.get("telemetry_window", {})
        counters = overview.get("context", {})
        tools = overview.get("tools", {})
        evaluation = overview.get("evaluation", {})
        regression_summaries = {}
        for key in (
            "routing_regression",
            "output_quality_regression",
            "answer_contract_benchmark",
            "adversarial_mutation_regression",
        ):
            summary = evaluation.get(key, {})
            if isinstance(summary, dict):
                regression_summaries[key] = {
                    field: summary.get(field)
                    for field in ("passed", "total", "pass_rate")
                }
        task_lineage = evaluation.get("metric_lineage", {}).get("tasks", {})
        recent_quality = evaluation.get("recent_output_quality", {})
        result["surfaces"]["agentops"] = {
            "status": "ok",
            "runtime_pid_present": bool(runtime.get("runtime_pid")),
            "telemetry_days": window.get("days"),
            "external_exporter": window.get("external_exporter"),
            "sessions_count": counters.get("sessions"),
            "tools_available": tools.get("available"),
            "tools_total": tools.get("total"),
            "recent_run_count": len(overview.get("recent_runs", [])),
            "business_task_success_measured": evaluation.get("task_success_rate")
            is not None,
            "task_execution_count": task_lineage.get("completed_sample_size"),
            "recent_output_quality_measured": recent_quality.get("measured"),
            "deterministic_regressions": regression_summaries,
        }
    elif overview is not None:
        failures.append({"surface": "agentops", "type": "UnexpectedShape"})

    result["surfaces"] = {
        key: value
        for key, value in result["surfaces"].items()
        if key in {"local_sources", "artifacts", "memories", "skills", "agentops"}
    }
    result["passed"] = not failures and len(result["surfaces"]) == 5
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
