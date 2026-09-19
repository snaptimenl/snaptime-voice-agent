"""Overlay the admin-managed settings and knowledge base (Snaptime `/api/ai/config`) on the YAML config.

The YAML stays the fallback: when the API is unreachable, or a field is empty, the YAML value is used.
`system_prompt` in the YAML may contain: {agent_name_line}, {extra}, {faqs_ouder}, {faqs_fotograaf}.
"""
from __future__ import annotations

import logging

from receptionist.config import BusinessConfig
from receptionist.snaptime.client import SnaptimeClient

logger = logging.getLogger("receptionist.snaptime")

_GREETING_WITH_NAME = (
    "Goedendag, u spreekt met {name}, de klantenservice van Snaptime. "
    "Belt u als klant, of bent u fotograaf?"
)


def _format(items: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"V: {q}\nA: {a}" for q, a in items) or "Geen."


async def apply_remote_config(config: BusinessConfig, client: SnaptimeClient) -> BusinessConfig:
    data = await client.get_config()
    if data is None:
        logger.warning("snaptime config unavailable, using YAML defaults")
        data = {}

    name = (data.get("agentName") or "").strip()
    greeting = (data.get("greeting") or "").strip()
    extra = (data.get("extraInstructions") or "").strip()
    knowledge = data.get("knowledge") or []

    if knowledge:
        ouder = [(k["question"], k["answer"]) for k in knowledge if k["audience"] in ("ouder", "beide")]
        fotograaf = [(k["question"], k["answer"]) for k in knowledge if k["audience"] in ("fotograaf", "beide")]
    else:
        yaml_faqs = [(f.question, f.answer) for f in config.faqs]
        ouder = fotograaf = yaml_faqs

    update: dict = {}
    if greeting:
        update["greeting"] = greeting
    elif name:
        update["greeting"] = _GREETING_WITH_NAME.format(name=name)

    if config.system_prompt:
        update["system_prompt"] = (
            config.system_prompt
            .replace("{agent_name_line}", f"Je naam is {name}." if name else "")
            .replace("{extra}", f"EXTRA INSTRUCTIES VAN DE BEHEERDER\n{extra}" if extra else "")
            .replace("{faqs_ouder}", _format(ouder))
            .replace("{faqs_fotograaf}", _format(fotograaf))
        )
    # Keep the YAML faqs out of the prompt's plain {faqs} placeholder when knowledge comes from the API.
    if knowledge:
        update["faqs"] = []
    return config.model_copy(update=update)
