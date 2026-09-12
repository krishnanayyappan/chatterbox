import unittest

from intervention_agent.classifier import Candidate
from intervention_agent.models import AgentHistory, GroupState, Message, SlackContext
from intervention_agent.policy import InterventionPolicy


class StubClassifier:
    def __init__(self, candidate): self.candidate = candidate
    def classify(self, *_): return self.candidate


def window(*texts, start=1000, step=40, thread=False):
    return [Message(str(start + i * step), f"U{i % 3}", text, "C1", str(start) if thread else None) for i, text in enumerate(texts)]


class PolicyTests(unittest.TestCase):
    def decide(self, candidate, messages, history=None, context=None):
        return InterventionPolicy(StubClassifier(candidate)).decide(messages, GroupState(), history or AgentHistory(), context or SlackContext("C1"))

    def test_rally_is_silent_even_when_a_candidate_exists(self):
        result = self.decide(Candidate("circling", .9, "would otherwise interrupt"), window(*["new information" for _ in range(8)], step=10))
        self.assertEqual((result.arm, result.suppressed_by.split(":")[0]), ("silence", "rally"))

    def test_circling_reaches_channel_offer(self):
        result = self.decide(Candidate("circling", .80, "same two positions restated"), window(*["same disagreement" for _ in range(8)]))
        self.assertEqual(result.arm, "channel_offer")

    def test_dispute_is_thread_offer(self):
        result = self.decide(Candidate("checkable_dispute", .80, "conflicting opening hours"), window(*["venue facts" for _ in range(8)]))
        self.assertEqual(result.arm, "thread_offer")

    def test_convergence_acts(self):
        result = self.decide(Candidate("convergence", .80, "two people chose Saturday", message="Recording: Saturday 4pm."), window(*["Saturday" for _ in range(8)]))
        self.assertEqual(result.arm, "act")

    def test_claimed_suppresses_missing_fact(self):
        result = self.decide(Candidate("missing_fact", .80, "opening time unknown"), window("What time does it open?", "Maybe later", "I don't know", "I'll check the hours", *["waiting" for _ in range(4)]))
        self.assertEqual((result.arm, result.suppressed_by.split(":")[0]), ("silence", "claimed"))

    def test_noise_stays_silent(self):
        result = self.decide(Candidate(), window(*["lol anyway how are you" for _ in range(8)]))
        self.assertEqual(result.arm, "silence")

    def test_thread_never_becomes_channel_offer(self):
        messages = window(*["same disagreement" for _ in range(8)], thread=True)
        result = self.decide(Candidate("circling", .80, "same positions"), messages, context=SlackContext("C1", True, messages[0].ts))
        self.assertEqual(result.arm, "thread_offer")

    def test_mention_overrides_every_gate(self):
        result = self.decide(Candidate(), window(*["fast" for _ in range(8)], step=5))
        mentioned = InterventionPolicy(StubClassifier(Candidate())).decide(window(*["fast" for _ in range(8)], step=5), GroupState(), AgentHistory(), SlackContext("C1"), app_mentioned=True)
        self.assertEqual(mentioned.arm, "act")


if __name__ == "__main__":
    unittest.main()
