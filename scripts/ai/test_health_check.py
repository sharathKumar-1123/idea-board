from ai_client import parse_verdict
from health_check import condense_for_ai, decide, hard_checks

HEALTHY_AI = {"healthy": True, "confidence": 0.9, "summary": "", "likely_cause": "", "suggested_fix": ""}
UNHEALTHY_AI = {**HEALTHY_AI, "healthy": False}


def evidence(waiting=(), ready=True, probe_ok=True):
    return {
        "pods": [
            {"name": "b", "component": "backend", "ready": ready, "waiting_reasons": list(waiting)},
            {"name": "f", "component": "frontend", "ready": True, "waiting_reasons": []},
        ],
        "http_probes": [{"url": "http://x/api/health", "ok": probe_ok, "status": 200, "error": ""}],
    }


def test_hard_checks_pass_for_healthy_release():
    assert hard_checks(evidence()) == []


def test_hard_checks_catch_crash_loop_and_failed_probe():
    problems = hard_checks(evidence(waiting=["CrashLoopBackOff"], ready=False, probe_ok=False))
    assert any("CrashLoopBackOff" in p for p in problems)
    assert any("No ready backend" in p for p in problems)
    assert any("failed" in p for p in problems)


def test_failed_rollout_is_caught_even_when_old_pods_still_serve():
    ev = evidence()  # old pods ready, URL healthy
    ev["pods"].append(
        {"name": "b-new", "component": "backend", "ready": False, "restarts": 3, "waiting_reasons": []}
    )
    ev["rollout_status"] = "failure"
    problems = hard_checks(ev)
    assert any("rollout failed" in p for p in problems)
    assert any("b-new is not ready after 3 restarts" in p for p in problems)


def test_ai_cannot_override_hard_failure():
    healthy, _ = decide(["pod crashing"], HEALTHY_AI, threshold=0.7)
    assert healthy is False


def test_confident_ai_can_fail_the_gate():
    healthy, _ = decide([], UNHEALTHY_AI, threshold=0.7)
    assert healthy is False


def test_low_confidence_ai_does_not_fail_the_gate():
    healthy, _ = decide([], {**UNHEALTHY_AI, "confidence": 0.4}, threshold=0.7)
    assert healthy is True


def test_missing_ai_falls_back_to_hard_checks():
    assert decide([], None, threshold=0.7)[0] is True


def test_condense_keeps_errors_and_drops_health_check_noise():
    full = {
        "pods": [{"name": "b", "component": "backend", "phase": "Running", "ready": False,
                  "restarts": 3, "waiting_reasons": ["CrashLoopBackOff"], "extra": "dropped"}],
        "events": ["Normal Pulled ...", "Warning BackOff restarting failed container"],
        "backend_logs": [
            '[pod/b-1/backend] INFO: 10.0.0.1 - "GET /health HTTP/1.1" 200 OK',
            "[pod/b-1/backend] WARNING database not ready: could not translate host name",
            "[pod/b-2/backend] WARNING database not ready: could not translate host name",
        ],
        "http_probes": [],
    }
    ai_view = condense_for_ai(full)
    assert ai_view["backend_logs"] == [full["backend_logs"][1]]
    assert ai_view["events"] == ["Warning BackOff restarting failed container"]
    assert "extra" not in ai_view["pods"][0]


def test_condense_passes_crash_message_preserved_by_kubernetes():
    message = 'could not translate host name "db.invalid.example"'
    crash = {"reason": "Error", "exit_code": 1, "message": message}
    full = {
        "pods": [{"name": "b", "component": "backend", "phase": "Running", "ready": False,
                  "restarts": 5, "waiting_reasons": [], "last_termination": [crash]}],
        "events": [], "backend_logs": [], "http_probes": [],
    }
    assert condense_for_ai(full)["pods"][0]["last_termination"] == [crash]


def test_parse_verdict_handles_fenced_json_and_rejects_garbage():
    raw = '```json\n{"healthy": false, "confidence": 1.4, "summary": "db down"}\n```'
    verdict = parse_verdict(raw)
    assert verdict["healthy"] is False
    assert verdict["confidence"] == 1.0
    assert parse_verdict("not json") is None
    assert parse_verdict('{"healthy": "yes"}') is None
