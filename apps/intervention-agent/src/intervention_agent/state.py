from __future__ import annotations

from typing import Protocol

from .models import GroupState, Message, SlackContext


class StateProvider(Protocol):
    """Implemented by the separate conversation-understanding module."""

    def get_state(self, messages: list[Message], context: SlackContext) -> GroupState: ...


class EmptyStateProvider:
    """Useful for build step 1; replace without changing intervention policy."""

    def get_state(self, messages: list[Message], context: SlackContext) -> GroupState:
        return GroupState(participants=list(dict.fromkeys(message.user for message in messages)))
