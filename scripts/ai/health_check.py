"""Post-deployment health gate: deterministic hard checks + AI analysis.

Exit code 0 = keep the release, 1 = roll back.

Decision rules (the AI can make the gate stricter, never looser):
  1. Any hard-check failure  -> unhealthy, regardless of the AI's opinion.
  2. AI says unhealthy with confidence >= threshold -> unhealthy.
  3. Otherwise healthy. If the AI is unavailable, hard checks alone decide.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import ai_client

BAD_WAITING_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "CreateContainerError",
    "InvalidImageName",
}
MAX_LOG_LINES = 80


def kubectl(*args: str) -> str:
    result = subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=60)
    return result.stdout if result.returncode == 0 else result.stderr


def collect_pods(namespace: str, release: str) -> list[dict]:
    raw = kubectl("get", "pods", "-n", namespace, "-l", f"app.kubernetes.io/instance={release}", "-o", "json")
    try:
        items = json.loads(raw)["items"]
    except (json.JSONDecodeError, KeyError):
        return []

    pods = []
    for item in items:
        statuses = item.get("status", {}).get("containerStatuses", [])
        pods.append(
            {
                "name": item["metadata"]["name"],
                "component": item["metadata"].get("labels", {}).get("app.kubernetes.io/component", ""),
                "phase": item.get("status", {}).get("phase", "Unknown"),
                "ready": bool(statuses) and all(s.get("ready") for s in statuses),
                "restarts": sum(s.get("restartCount", 0) for s in statuses),
                "waiting_reasons": [
                    s["state"]["waiting"].get("reason", "")
                    for s in statuses
                    if "waiting" in s.get("state", {})
                ],
            }
        )
    return pods


def probe(url: str, attempts: int = 1, delay: float = 10.0) -> dict:
    """GET a URL, retrying (a new cloud load balancer's DNS can take a few minutes to resolve)."""
    last = {"url": url, "status": None, "ok": False, "error": "not attempted"}
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return {"url": url, "status": resp.status, "ok": 200 <= resp.status < 300, "error": ""}
        except urllib.error.HTTPError as exc:
            last = {"url": url, "status": exc.code, "ok": False, "error": str(exc.reason)}
        except Exception as exc:
            last = {"url": url, "status": None, "ok": False, "error": str(exc)}
        if attempt < attempts:
            time.sleep(delay)
    return last


def collect_evidence(namespace: str, release: str, base_url: str) -> dict:
    events = kubectl("get", "events", "-n", namespace, "--sort-by=.lastTimestamp").splitlines()[-30:]
    logs = kubectl(
        "logs", "-n", namespace,
        "-l", f"app.kubernetes.io/instance={release},app.kubernetes.io/component=backend",
        f"--tail={MAX_LOG_LINES}", "--prefix", "--all-containers",
    ).splitlines()[-MAX_LOG_LINES:]

    pods = collect_pods(namespace, release)
    # A crash-looping container has usually just restarted, so its current log is nearly empty;
    # the actual error is in the log of the previous (crashed) attempt.
    for pod in pods:
        if pod["restarts"] > 0 and not pod["ready"]:
            previous = kubectl(
                "logs", "-n", namespace, pod["name"], "--previous", "--all-containers", "--tail=40"
            ).splitlines()
            logs += [f"[{pod['name']} previous crash] {line}" for line in previous]

    probes = []
    if base_url:
        base_url = base_url.rstrip("/")
        probes.append(probe(f"{base_url}/api/health", attempts=18))  # up to ~3 min for LB/DNS
        probes.append(probe(f"{base_url}/api/ideas", attempts=3))
        probes.append(probe(f"{base_url}/", attempts=3))

    return {
        "release": release,
        "namespace": namespace,
        "pods": pods,
        "events": events,
        "backend_logs": logs,
        "http_probes": probes,
    }


CRASH_RESTART_THRESHOLD = 2


def hard_checks(evidence: dict) -> list[str]:
    problems = []
    pods = evidence["pods"]

    # During a rolling update the old pods keep serving traffic, so the URL can look fine while the
    # new version never becomes ready. Helm's own rollout result catches that.
    if evidence.get("rollout_status") == "failure":
        problems.append("Helm rollout failed or timed out: the new version never became ready.")

    if not pods:
        problems.append("No pods found for the release.")
    for pod in pods:
        bad = BAD_WAITING_REASONS.intersection(pod["waiting_reasons"])
        if bad:
            problems.append(f"Pod {pod['name']} is in {', '.join(sorted(bad))}.")
        elif not pod["ready"] and pod.get("restarts", 0) >= CRASH_RESTART_THRESHOLD:
            # Between restarts a crash-looping pod briefly shows no waiting reason.
            problems.append(f"Pod {pod['name']} is not ready after {pod['restarts']} restarts.")

    for component in ("backend", "frontend"):
        if pods and not any(p["ready"] for p in pods if p["component"] == component):
            problems.append(f"No ready {component} pods.")

    if not evidence["http_probes"]:
        problems.append("No public URL available to probe.")
    for result in evidence["http_probes"]:
        if not result["ok"]:
            detail = f"status={result['status']} {result['error']}".strip()
            problems.append(f"GET {result['url']} failed: {detail}")

    return problems


NOISE_PATTERNS = ("GET /health", "GET /api/health")
MAX_AI_LOG_LINES = 25
MAX_AI_EVENTS = 15


def _dedupe(lines: list[str]) -> list[str]:
    seen, out = set(), []
    for line in lines:
        # Drop the per-pod "[pod/name/container]" prefix so identical errors from replicas collapse.
        key = line.split("] ", 1)[-1].strip()
        if key and key not in seen:
            seen.add(key)
            out.append(line)
    return out


def condense_for_ai(evidence: dict) -> dict:
    """Keep the signal, drop the noise: small models on CPU need a short, focused prompt.

    The full evidence still goes into the report artifact; only the LLM sees this condensed view.
    """
    logs = [line for line in evidence["backend_logs"] if not any(p in line for p in NOISE_PATTERNS)]
    keywords = ("ERROR", "WARN", "EXCEPTION", "FAIL")
    important = [line for line in logs if any(k in line.upper() for k in keywords)]
    events = [e for e in evidence["events"] if "Warning" in e] or evidence["events"]

    return {
        "pods": [
            {k: p[k] for k in ("name", "component", "phase", "ready", "restarts", "waiting_reasons")}
            for p in evidence["pods"]
        ],
        "events": _dedupe(events)[-MAX_AI_EVENTS:],
        "backend_logs": _dedupe(important or logs)[-MAX_AI_LOG_LINES:],
        "http_probes": evidence["http_probes"],
        "rollout_status": evidence.get("rollout_status", ""),
        "hard_check_problems": evidence.get("hard_check_problems", []),
    }


def decide(problems: list[str], verdict: dict | None, threshold: float) -> tuple[bool, str]:
    if problems:
        return False, "Hard checks failed."
    if verdict and not verdict["healthy"] and verdict["confidence"] >= threshold:
        return False, f"AI flagged the release as unhealthy (confidence {verdict['confidence']:.0%})."
    if verdict is None:
        return True, "Hard checks passed (AI analysis unavailable)."
    return True, "Hard checks passed and AI analysis found no blocking issues."


def render_summary(healthy: bool, reason: str, problems: list[str], verdict: dict | None) -> str:
    title = "✅ Deployment healthy" if healthy else "❌ Deployment unhealthy"
    lines = [f"## {title}", "", f"**Decision:** {reason}", ""]
    if problems:
        lines += ["### Hard-check failures", *[f"- {p}" for p in problems], ""]
    if verdict:
        lines += [
            "### 🤖 AI analysis",
            f"- **Verdict:** {'healthy' if verdict['healthy'] else 'unhealthy'} "
            f"(confidence {verdict['confidence']:.0%})",
            f"- **Summary:** {verdict['summary']}",
        ]
        if verdict["likely_cause"]:
            lines.append(f"- **Likely cause:** {verdict['likely_cause']}")
        if verdict["suggested_fix"]:
            lines.append(f"- **Suggested fix:** {verdict['suggested_fix']}")
    else:
        lines.append("_AI analysis was not available for this run._")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--url", default="", help="Public base URL of the application")
    parser.add_argument("--settle-seconds", type=int, default=45, help="Wait before collecting evidence")
    parser.add_argument("--threshold", type=float, default=0.7, help="Min AI confidence to fail the gate")
    parser.add_argument("--report", default="health-report.json")
    parser.add_argument(
        "--rollout-status", default="", help="Outcome of the helm upgrade step (success/failure)"
    )
    args = parser.parse_args()

    print(f"Waiting {args.settle_seconds}s for the rollout to settle...")
    time.sleep(args.settle_seconds)

    evidence = collect_evidence(args.namespace, args.release, args.url)
    evidence["rollout_status"] = args.rollout_status
    problems = hard_checks(evidence)
    evidence["hard_check_problems"] = problems

    prompt = (Path(__file__).parent / "prompt.md").read_text()
    started = time.time()
    verdict = ai_client.analyze(prompt, condense_for_ai(evidence))
    print(f"AI analysis took {time.time() - started:.0f}s")
    healthy, reason = decide(problems, verdict, args.threshold)

    summary = render_summary(healthy, reason, problems, verdict)
    print(summary)
    if step_summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(step_summary, "a") as fh:
            fh.write(summary)

    Path(args.report).write_text(
        json.dumps({"healthy": healthy, "reason": reason, "verdict": verdict, "evidence": evidence}, indent=2)
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
