"""Provider-agnostic LLM client for deployment analysis.

AI_PROVIDER selects the backend:
  bedrock (default) - Amazon Bedrock Converse API, authenticated with the pipeline's AWS credentials.
                      Requires BEDROCK_MODEL_ID (model or inference profile ID from the Bedrock console).
  github            - GitHub Models, authenticated with GITHUB_TOKEN. Optional GITHUB_MODEL.
  none              - Skip AI analysis; the pipeline relies on hard checks only.

Any failure returns None so a broken or unavailable AI never blocks a deployment decision.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
MAX_TOKENS = 800


def analyze(system_prompt: str, evidence: dict) -> dict | None:
    provider = os.getenv("AI_PROVIDER", "bedrock").lower()
    user_message = json.dumps(evidence, indent=2, default=str)

    try:
        if provider == "bedrock":
            raw = _call_bedrock(system_prompt, user_message)
        elif provider == "github":
            raw = _call_github_models(system_prompt, user_message)
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


def _call_github_models(system_prompt: str, user_message: str) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")

    body = {
        "model": os.getenv("GITHUB_MODEL", "openai/gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
    }
    request = urllib.request.Request(
        GITHUB_MODELS_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as resp:
        raw = resp.read().decode(errors="replace")
        try:
            return json.loads(raw)["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            content_type = resp.headers.get("Content-Type")
            raise RuntimeError(
                f"unexpected response (HTTP {resp.status}, {content_type}): {raw[:200]!r}"
            ) from exc


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
