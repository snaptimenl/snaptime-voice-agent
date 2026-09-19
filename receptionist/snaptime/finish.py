"""End-of-call reporting to Snaptime: duration, estimated cost and a privacy-safe summary."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

import httpx

from receptionist.snaptime.client import SnaptimeClient

logger = logging.getLogger("receptionist.snaptime")

SUMMARY_PROMPT = (
    "Je vat een Nederlands telefoongesprek met een klantenservice samen voor intern gebruik. "
    "Schrijf maximaal twee korte zinnen: waar ging het over en wat was de uitkomst. "
    "Vermeld GEEN namen, telefoonnummers, e-mailadressen, adressen, inlogcodes of andere persoonsgegevens. "
    'Antwoord uitsluitend met JSON: {"summary": "...", "resolved": true|false}. '
    "resolved is true als de vraag van de beller beantwoord is zonder dat een terugbelverzoek nodig was."
)


def _rate(name: str) -> float:
    try:
        return float(os.environ.get(name, "0") or 0)
    except ValueError:
        return 0.0


def _transcript(receptionist) -> str:
    capture = getattr(receptionist.lifecycle, "transcript_capture", None)
    lines = []
    for seg in getattr(capture, "segments", []) or []:
        role = getattr(getattr(seg, "role", None), "value", None)
        if role == "user":
            lines.append(f"Beller: {seg.text}")
        elif role == "assistant":
            lines.append(f"Assistent: {seg.text}")
    return "\n".join(lines)


def _fallback_summary(toolkit) -> str:
    """Deterministic summary from what the tools did — no model involved, no personal data."""
    parts = []
    if toolkit.caller_kind == "ouder":
        parts.append("Klant (inlogcode herkend)")
    elif toolkit.caller_kind == "fotograaf":
        parts.append("Fotograaf (nummer herkend)")
    else:
        parts.append("Beller niet herkend")
    if toolkit.knowledge_searches:
        parts.append(f"{toolkit.knowledge_hits} van {toolkit.knowledge_searches} kennisvragen beantwoord")
    if toolkit.callback_created:
        parts.append("terugbelverzoek vastgelegd")
    return ", ".join(parts) + "."


async def _llm_summary(transcript: str) -> tuple[str, bool] | None:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip().strip("'\"")
    model = os.environ.get("SNAPTIME_SUMMARY_MODEL", "gpt-4o-mini")
    if not api_key or not transcript:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            res = await http.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": SUMMARY_PROMPT},
                        {"role": "user", "content": transcript[:12000]},
                    ],
                },
            )
        if res.status_code >= 400:
            logger.warning("summary request failed: %s %s", res.status_code, res.text[:200])
            return None
        data = json.loads(res.json()["choices"][0]["message"]["content"])
        return str(data.get("summary", ""))[:1000], bool(data.get("resolved"))
    except Exception:
        logger.exception("summary failed")
        return None


async def finish_call(client: SnaptimeClient, receptionist, call_id: str) -> None:
    seconds = max(0, round(time.monotonic() - getattr(receptionist, "started_at", time.monotonic())))
    minutes = seconds / 60
    fields: dict = {
        "endedAt": datetime.now(timezone.utc).isoformat(),
        "durationSec": seconds,
        "aiCostCents": round(minutes * _rate("SNAPTIME_AI_CENTS_PER_MINUTE")),
        "telephonyCostCents": round(minutes * _rate("SNAPTIME_TELEPHONY_CENTS_PER_MINUTE")),
    }
    toolkit = receptionist.toolkit
    result = await _llm_summary(_transcript(receptionist))
    if result and result[0]:
        fields["summary"] = result[0]
        if result[1] and not toolkit.callback_created:
            fields["outcome"] = "opgelost"
    else:
        fields["summary"] = _fallback_summary(toolkit)
    await client.end_call(call_id, **fields)
