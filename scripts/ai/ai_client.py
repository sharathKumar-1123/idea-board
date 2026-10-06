"""Provider-agnostic LLM client for deployment analysis.

AI_PROVIDER selects the backend:
  ollama (default) - Open-source model served by Ollama on the CI runner itself (OLLAMA_HOST,
                     OLLAMA_MODEL). No API keys, and deployment evidence never leaves the pipeline.
  bedrock          - Amazon Bedrock Converse API, authenticated with the pipeline's AWS credentials.
                     Requires BEDROCK_MODEL_ID (model or inference profile ID from the Bedrock console).
  none             - Skip AI analysis; the pipeline relies on hard checks only.

Any failure returns None so a broken or unavailable AI never blocks a deployment decision.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

MAX_TOKENS = 800
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"


def analyze(system_prompt: str, evidence: dict) -> dict | None:
    provider = os.getenv("AI_PROVIDER", "ollama").lower()
    user_message = json.dumps(evidence, separators=(",", ":"), default=str)  # compact: fewer tokens

    try:
        if provider == "ollama":
            raw = _call_ollama(system_prompt, user_message)
        elif provider == "bedrock":
            raw = _call_bedrock(system_prompt, user_message)
        elif provider == "none":
            return None
        else:
            print(f"::warning::Unknown AI_PROVIDER '{provider}', skipping AI analysis")
            return None
    except Exception as exc:  # network, auth, throttling, missing model access...
        print(f"::warning::AI analysis unavailable ({provider}): {exc}")
        return None

    verdict = parse_verdict(raw)
    if verdict is None:
        print(f"::warning::AI returned an unparseable response: {raw[:300]!r}")
    return verdict


def _call_ollama(system_prompt: str, user_message: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    if not host.startswith("http"):
        host = f"http://{host}"

    body = {
        "model": os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "format": "json",  # constrain the model to emit valid JSON
        # Room for the evidence (logs/events) plus the answer; CPU inference, so keep it deterministic.
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": MAX_TOKENS},
    }
    request = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as resp:
        return json.load(resp)["message"]["content"]


def _call_bedrock(system_prompt: str, user_message: str) -> str:
    import boto3

    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("BEDROCK_MODEL_ID is not set")

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0},
    )
    return response["output"]["message"]["content"][0]["text"]


def parse_verdict(raw: str) -> dict | None:
    """Extract and validate the JSON verdict; reject anything that doesn't match the schema."""
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    if not isinstance(data.get("healthy"), bool):
        return None
    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        return None

    return {
        "healthy": data["healthy"],
        "confidence": max(0.0, min(1.0, confidence)),
        "summary": str(data.get("summary", "")),
        "likely_cause": str(data.get("likely_cause", "")),
        "suggested_fix": str(data.get("suggested_fix", "")),
    }
