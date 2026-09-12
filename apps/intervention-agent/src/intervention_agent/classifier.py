from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Protocol

from .models import GroupState, Message, SlackContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Candidate:
    trigger: str = "none"
    confidence: float = 0.0
    reason: str = "no intervention candidate"
    target_user: str | None = None
    message: str | None = None
    emoji: str | None = None
    tool: dict | None = None


class Classifier(Protocol):
    def classify(self, messages: list[Message], state: GroupState, context: SlackContext) -> Candidate: ...


class NoneClassifier:
    """Safe startup mode: wire Slack and logging before enabling the LLM."""

    def classify(self, messages: list[Message], state: GroupState, context: SlackContext) -> Candidate:
        return Candidate()


class OpenRouterClassifier:
    """One OpenRouter call; policy code, not the model, owns suppression/surfaces."""

    def __init__(self, model: str | None = None) -> None:
        from openai import OpenAI

        headers = {
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:3000"),
            "X-OpenRouter-Title": os.getenv("OPENROUTER_APP_NAME", "Quiet Slack Agent"),
        }
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"], default_headers=headers)
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    def classify(self, messages: list[Message], state: GroupState, context: SlackContext) -> Candidate:
        payload = {
            "messages": [m.__dict__ for m in messages[-15:]],
            "state": state.__dict__,
            "context": context.__dict__,
        }
        instructions = """You classify the last Slack messages for an intervention policy.
Return only one candidate trigger: direct_request, convergence, checkable_dispute,
missing_fact, circling, or none. Heat alone is never a trigger. Convergence needs
two people endorsing an option without objection in three later messages. Circling
means no new option, constraint, or fact in four messages and two positions remain.
Write the short user-facing offer/record only when useful. Do not decide suppressors
or surfaces; a deterministic policy does that after your response."""
        instructions += """ Return JSON only, with exactly these keys: trigger,
confidence, reason, target_user, message, emoji, tool. Use null where a value
does not apply. tool must be null or {\"name\": \"lookup\", \"args\": {\"query\": \"...\"}}."""
        schema = {
            "name": "intervention_candidate",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "trigger": {"type": "string", "enum": ["direct_request", "convergence", "checkable_dispute", "missing_fact", "circling", "none"]},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                    "target_user": {"type": ["string", "null"]},
                    "message": {"type": ["string", "null"]},
                    "emoji": {"type": ["string", "null"]},
                    "tool": {
                        "anyOf": [
                            {"type": "null"},
                            {
                                "type": "object", "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string", "enum": ["lookup"]},
                                    "args": {
                                        "type": "object", "additionalProperties": False,
                                        "properties": {"query": {"type": "string"}},
                                        "required": ["query"],
                                    },
                                },
                                "required": ["name", "args"],
                            },
                        ],
                    },
                },
                "required": ["trigger", "confidence", "reason", "target_user", "message", "emoji", "tool"],
            },
        }
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_schema", "json_schema": schema},
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        try:
            return Candidate(**json.loads(content))
        except (json.JSONDecodeError, TypeError) as error:
            logger.warning("Classifier returned invalid JSON (finish_reason=%s, chars=%d): %s", response.choices[0].finish_reason, len(content), error)
            return Candidate(reason="classifier returned no valid structured decision")
