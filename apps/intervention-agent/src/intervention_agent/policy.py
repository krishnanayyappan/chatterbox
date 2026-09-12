from __future__ import annotations

import re
from dataclasses import replace

from .classifier import Candidate, Classifier
from .models import AgentHistory, Decision, GroupState, Message, SlackContext

ARM_BY_TRIGGER = {
    "direct_request": "act", "convergence": "act", "checkable_dispute": "thread_offer",
    "missing_fact": "thread_offer", "circling": "channel_offer", "none": "silence",
}
RANK = {"silence": 0, "react": 1, "ephemeral": 2, "thread_offer": 3, "channel_offer": 4, "act": 5}
CLAIM_RE = re.compile(r"\b(?:i(?:'ll|’ll|\s+will)|let\s+me|on\s+it|i\s+can)\s+(?:check|look|find|verify|handle|do)\b", re.I)


def slack_seconds(ts: str | None) -> float | None:
    try:
        return float(ts) if ts else None
    except (TypeError, ValueError):
        return None


class InterventionPolicy:
    def __init__(self, classifier: Classifier) -> None:
        self.classifier = classifier

    def decide(self, messages: list[Message], state: GroupState, agent_history: AgentHistory, context: SlackContext, *, app_mentioned: bool = False) -> Decision:
        messages = messages[-15:]
        if not messages:
            return Decision("silence", "none", 0, "no messages")
        if app_mentioned:
            return Decision("act", "direct_request", 1.0, "app mention overrides gates", message="What should I check?")

        suppressed = self._suppressed(messages, agent_history)
        if suppressed:
            return Decision("silence", "none", 0, suppressed, suppressed_by=suppressed)

        candidate = self.classifier.classify(messages, state, context)
        decision = self._candidate_to_decision(candidate, messages[-1])
        return self._apply_surface_rules(decision, messages[-1], agent_history, context)

    def _suppressed(self, messages: list[Message], history: AgentHistory) -> str | None:
        newest = slack_seconds(messages[-1].ts)
        last_post = slack_seconds(history.last_post_ts)
        if newest is not None and last_post is not None and newest - last_post < 90:
            return "refractory: agent posted within 90s"
        recent = [slack_seconds(m.ts) for m in messages[-3:]]
        if None not in recent and recent[-1] - recent[0] <= 30:
            return "rally: three messages within 30s"
        if any(CLAIM_RE.search(m.text) for m in messages[-5:]):
            return "claimed: someone is already checking"
        return None

    def _candidate_to_decision(self, candidate: Candidate, source: Message) -> Decision:
        arm = ARM_BY_TRIGGER.get(candidate.trigger, "silence")
        if candidate.confidence < 0.50:
            arm = "silence"
        elif candidate.confidence < 0.60:
            arm = "react"
        elif candidate.confidence < 0.70 and arm in {"act", "channel_offer"}:
            arm = "thread_offer"
        elif candidate.confidence < 0.75 and arm == "act":
            arm = "channel_offer"
        if arm == "react":
            return Decision(arm, candidate.trigger, candidate.confidence, candidate.reason, emoji=candidate.emoji or "white_check_mark")
        return Decision(arm, candidate.trigger, candidate.confidence, candidate.reason, candidate.target_user, candidate.message, candidate.emoji, candidate.tool)

    def _apply_surface_rules(self, decision: Decision, source: Message, history: AgentHistory, context: SlackContext) -> Decision:
        before = decision.arm
        arm = decision.arm
        if source.thread_ts and arm == "channel_offer":
            arm = "thread_offer"
        if decision.trigger == "missing_fact" and decision.target_user and arm not in {"silence", "react"}:
            arm = "ephemeral"
        if 0.60 <= decision.confidence < 0.70 and RANK[arm] > 0:
            arm = self._lower(arm)
        if history.offers_declined >= 2 and RANK[arm] > RANK["ephemeral"]:
            arm = "ephemeral"
        if arm == "ephemeral" and not decision.target_user:
            # An offer that cannot be private must remain a lower-impact thread offer.
            arm = "thread_offer" if source.thread_ts or context.in_thread else "react"
        return replace(decision, arm=arm, arm_before_downgrade=before if arm != before else None)

    @staticmethod
    def _lower(arm: str) -> str:
        return {"act": "channel_offer", "channel_offer": "thread_offer", "thread_offer": "ephemeral", "ephemeral": "react", "react": "silence"}.get(arm, "silence")
