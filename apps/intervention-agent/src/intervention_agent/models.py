from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Arm = Literal["silence", "react", "ephemeral", "thread_offer", "channel_offer", "act"]


@dataclass(frozen=True)
class Message:
    ts: str
    user: str
    text: str
    channel: str
    thread_ts: str | None = None


@dataclass(frozen=True)
class SlackContext:
    channel_id: str
    in_thread: bool = False
    thread_ts: str | None = None
    channel_member_count: int | None = None


@dataclass
class GroupState:
    goal: str | None = None
    participants: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    agreements: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class AgentHistory:
    last_post_ts: str | None = None
    last_arm: str | None = None
    posts_this_session: int = 0
    offers_declined: int = 0
    last_post_message_index: int | None = None


@dataclass
class Decision:
    arm: Arm
    trigger: str
    confidence: float
    reason: str
    target_user: str | None = None
    message: str | None = None
    emoji: str | None = None
    tool: dict[str, Any] | None = None
    arm_before_downgrade: str | None = None
    suppressed_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
