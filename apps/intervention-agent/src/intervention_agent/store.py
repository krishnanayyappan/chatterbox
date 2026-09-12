from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .models import Decision, SlackContext


class EventStore:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS evaluations (
            eval_id TEXT PRIMARY KEY, ts TEXT, channel TEXT, in_thread INTEGER,
            source_ts TEXT, window_msg_ts TEXT, trigger TEXT, arm_selected TEXT, arm_before_downgrade TEXT,
            confidence REAL, reason TEXT, suppressed_by TEXT, posted INTEGER DEFAULT 0,
            outcome TEXT DEFAULT '{}')""")
        self.db.execute("CREATE TABLE IF NOT EXISTS actions (action_id TEXT PRIMARY KEY, eval_id TEXT, user_id TEXT)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS offers (
            action_id TEXT PRIMARY KEY, channel TEXT, thread_ts TEXT, research_query TEXT)""")
        self.db.commit()

    def log(self, decision: Decision, context: SlackContext, messages: list[Any]) -> str:
        eval_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO evaluations VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '{}')", (
            eval_id, context.channel_id, context.in_thread, messages[-1].ts, json.dumps([m.ts for m in messages[-15:]]),
            decision.trigger, decision.arm, decision.arm_before_downgrade, decision.confidence,
            decision.reason, decision.suppressed_by,
        ))
        self.db.commit()
        return eval_id

    def set_posted(self, eval_id: str) -> None:
        self.db.execute("UPDATE evaluations SET posted=1 WHERE eval_id=?", (eval_id,))
        self.db.commit()

    def bind_action(self, action_id: str, eval_id: str, user_id: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO actions VALUES (?, ?, ?)", (action_id, eval_id, user_id))
        self.db.commit()

    def save_offer(self, action_id: str, channel: str, thread_ts: str, research_query: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO offers VALUES (?, ?, ?, ?)", (action_id, channel, thread_ts, research_query))
        self.db.commit()

    def get_offer(self, action_id: str) -> tuple[str, str, str] | None:
        row = self.db.execute("SELECT channel, thread_ts, research_query FROM offers WHERE action_id=?", (action_id,)).fetchone()
        return row if row else None

    def record_button(self, action_id: str, button: str) -> str | None:
        row = self.db.execute("SELECT eval_id FROM actions WHERE action_id=?", (action_id,)).fetchone()
        if not row:
            return None
        self.merge_outcome(row[0], {"button": button})
        return row[0]

    def merge_outcome(self, eval_id: str, fields: dict[str, Any]) -> None:
        row = self.db.execute("SELECT outcome FROM evaluations WHERE eval_id=?", (eval_id,)).fetchone()
        if not row:
            return
        outcome = json.loads(row[0])
        outcome.update(fields)
        self.db.execute("UPDATE evaluations SET outcome=? WHERE eval_id=?", (json.dumps(outcome), eval_id))
        self.db.commit()

    def history_for(self, channel: str, messages: list[Any]):
        """Build only the state the policy owns from durable prior evaluations."""
        from .models import AgentHistory

        row = self.db.execute("SELECT source_ts, arm_selected FROM evaluations WHERE channel=? AND posted=1 ORDER BY rowid DESC LIMIT 1", (channel,)).fetchone()
        declined = self.db.execute("SELECT COUNT(*) FROM evaluations WHERE channel=? AND outcome LIKE '%\"button\": \"no%'", (channel,)).fetchone()[0]
        if not row:
            return AgentHistory(offers_declined=declined)
        source_ts, arm = row
        message_index = next((i for i, message in enumerate(messages) if message.ts == source_ts), None)
        return AgentHistory(last_post_ts=source_ts, last_arm=arm, posts_this_session=0, offers_declined=declined, last_post_message_index=message_index)
