from __future__ import annotations

import os
import re

from .models import Message


LOOKUP_RE = re.compile(r"\b(find|search|look up|lookup|research|latest|current|hours|menu|price|news)\b", re.I)


class OpenRouterResponder:
    """The response module for explicit requests; separate from intervention policy."""

    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:3000"),
                "X-OpenRouter-Title": os.getenv("OPENROUTER_APP_NAME", "Quiet Slack Agent"),
            },
        )
        self.model = os.getenv("OPENROUTER_MODEL", "openrouter/free")

    def answer(self, question: str, messages: list[Message], research: str | None = None) -> str:
        transcript = "\n".join(f"{message.user}: {message.text}" for message in messages[-15:])
        context = f"\n\nRecent channel transcript (oldest first):\n{transcript}"
        if research:
            context += f"\n\nExa research (use it as evidence; retain its links):\n{research}"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise, useful participant in a Slack conversation. Use the supplied recent channel transcript when it is relevant. Answer the direct request; if asked to summarize, summarize the transcript. Do not claim you cannot see the channel: the supplied transcript is the context you can see. Do not use greetings, preambles, or claim certainty beyond provided research. Keep the answer under 180 words.",
                },
                {"role": "user", "content": question + context},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or "I couldn't generate a response."


def needs_lookup(question: str) -> bool:
    return bool(LOOKUP_RE.search(question))
