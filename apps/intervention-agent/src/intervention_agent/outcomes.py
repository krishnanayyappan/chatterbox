from __future__ import annotations

from .policy import slack_seconds


def fill_delayed_outcome(store, client, eval_id: str, event: dict) -> None:
    """Record observable outcome data two minutes after an evaluation.

    Resolution is intentionally left null: it belongs to a separate conversation
    understanding module, not to Slack transport or this policy.
    """
    source_ts = slack_seconds(event["ts"]) or 0
    if event.get("thread_ts"):
        items = client.conversations_replies(channel=event["channel"], ts=event["thread_ts"], limit=100)["messages"]
    else:
        items = client.conversations_history(channel=event["channel"], oldest=event["ts"], limit=100)["messages"]
    replies = [item for item in items if not item.get("bot_id") and source_ts < (slack_seconds(item.get("ts")) or 0) <= source_ts + 120]
    store.merge_outcome(eval_id, {"human_replies_within_120s": len(replies), "topic_resolved_within_5_msgs": None})
