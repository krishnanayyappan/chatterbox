from __future__ import annotations

import os
import re
import threading
import logging
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .classifier import NoneClassifier, OpenRouterClassifier
from .models import Message, SlackContext
from .outcomes import fill_delayed_outcome
from .policy import InterventionPolicy
from .responder import OpenRouterResponder, needs_lookup
from .state import EmptyStateProvider, StateProvider
from .store import EventStore
from .tools import ExaLookupTimeout, ExaSearch, mention_query

logger = logging.getLogger(__name__)


def as_message(event: dict) -> Message:
    return Message(
        ts=event["ts"], user=event.get("user", "unknown"), text=event.get("text", ""),
        channel=event["channel"], thread_ts=event.get("thread_ts"),
    )


def fetch_window(client, event: dict) -> list[Message]:
    """Fetch a 15-message channel or thread window; policy has no Slack dependency."""
    if event.get("thread_ts"):
        raw = client.conversations_replies(channel=event["channel"], ts=event["thread_ts"], limit=15)["messages"]
    else:
        raw = client.conversations_history(channel=event["channel"], limit=15)["messages"]
        raw.reverse()
    return [as_message({**item, "channel": event["channel"]}) for item in raw if not item.get("bot_id")]


def default_text(decision) -> str:
    if decision.message:
        return decision.message
    return {
        "checkable_dispute": "There are conflicting factual claims here. Want me to check?",
        "missing_fact": "This depends on a missing fact. Want me to look?",
        "circling": "The same positions are repeating. Want me to help narrow this down?",
        "convergence": "Recording the decision. Say so if that's wrong.",
    }.get(decision.trigger, "What should I check?")


def offer_blocks(text: str, eval_id: str) -> list[dict]:
    elements = []
    for label, value, style in (("Yes", "yes", "primary"), ("No", "no", "danger"), ("Not now", "not_now", None)):
        button = {"type": "button", "text": {"type": "plain_text", "text": label}, "action_id": f"intervention:{eval_id}:{value}", "value": value}
        if style:
            button["style"] = style
        elements.append(button)
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "actions", "elements": elements},
    ]


def offer_action_id(eval_id: str, value: str) -> str:
    return f"intervention:{eval_id}:{value}"


class SlackAgent:
    def __init__(self, state_provider: StateProvider | None = None) -> None:
        load_dotenv()
        db_path = os.getenv("INTERVENTION_DB", "data/intervention.sqlite3")
        self.store = EventStore(db_path)
        classifier = OpenRouterClassifier() if os.getenv("OPENROUTER_API_KEY") else NoneClassifier()
        self.policy = InterventionPolicy(classifier)
        self.state_provider = state_provider or EmptyStateProvider()
        self.log_channel = os.getenv("AGENT_LOG_CHANNEL_ID")
        self.search = ExaSearch() if os.getenv("EXA_API_KEY") else None
        self.responder = OpenRouterResponder() if os.getenv("OPENROUTER_API_KEY") else None

    def evaluate(self, client, event: dict, *, app_mentioned: bool = False) -> None:
        try:
            logger.info("Received %s in channel %s", "app mention" if app_mentioned else "message", event.get("channel"))
            messages = fetch_window(client, event)
            if not messages:
                logger.warning("No usable human messages in the evaluation window")
                return
            context = SlackContext(event["channel"], bool(event.get("thread_ts")), event.get("thread_ts"))
            history = self.store.history_for(event["channel"], messages)
            state = self.state_provider.get_state(messages, context)
            decision = self.policy.decide(messages, state, history, context, app_mentioned=app_mentioned)
            eval_id = self.store.log(decision, context, messages)
            logger.info("Decision %s → %s (%.2f): %s", decision.trigger, decision.arm, decision.confidence, decision.reason)
            threading.Timer(120, fill_delayed_outcome, args=(self.store, client, eval_id, event)).start()
            if self.log_channel:
                try:
                    client.chat_postMessage(
                        channel=self.log_channel,
                        text=f"{decision.trigger} → {decision.arm} ({decision.confidence:.2f}) — {decision.reason}" + (f" [suppressed: {decision.suppressed_by}]" if decision.suppressed_by else ""),
                    )
                except Exception:
                    # The observability panel must never prevent an otherwise
                    # valid intervention in the working channel.
                    logger.exception(
                        "Could not post to AGENT_LOG_CHANNEL_ID=%s. "
                        "Invite the bot to that channel or clear the setting.",
                        self.log_channel,
                    )
            if decision.arm == "silence":
                return
            source = messages[-1]
            if decision.arm in {"ephemeral", "thread_offer", "channel_offer"}:
                # Persist the button mapping before the post so an immediate
                # click can always be correlated and fulfilled.
                thread_ts = event.get("thread_ts") or source.ts
                research_query = "Find current, reliable information needed to resolve this Slack discussion:\n" + "\n".join(f"{message.user}: {message.text}" for message in messages[-8:])
                for value in ("yes", "no", "not_now"):
                    action_id = offer_action_id(eval_id, value)
                    self.store.bind_action(action_id, eval_id, source.user)
                    self.store.save_offer(action_id, event["channel"], thread_ts, research_query)
            if decision.arm == "react":
                client.reactions_add(channel=event["channel"], timestamp=source.ts, name=decision.emoji or "white_check_mark")
            elif decision.arm == "ephemeral":
                client.chat_postEphemeral(channel=event["channel"], user=decision.target_user or source.user, text=default_text(decision), blocks=offer_blocks(default_text(decision), eval_id))
            elif decision.arm in {"thread_offer", "channel_offer"}:
                kwargs = {"channel": event["channel"], "text": default_text(decision), "blocks": offer_blocks(default_text(decision), eval_id)}
                if decision.arm == "thread_offer":
                    kwargs["thread_ts"] = event.get("thread_ts") or source.ts
                client.chat_postMessage(**kwargs)
            else:  # act: direct request or convergence record
                text = default_text(decision)
                if app_mentioned:
                    query = mention_query(event.get("text", ""))
                    if not query:
                        text = "What should I check?"
                    elif not self.responder:
                        text = "I need an OPENROUTER_API_KEY before I can answer requests."
                    else:
                        try:
                            research = self.search.answer(query) if self.search and needs_lookup(query) else None
                            text = self.responder.answer(query, messages, research)
                        except ExaLookupTimeout:
                            logger.warning("Direct Exa lookup timed out")
                            text = "That Exa lookup timed out. Try a narrower question."
                        except Exception:
                            logger.exception("The model response call failed")
                            text = "I couldn't reach the configured model. Check the app terminal for the provider error."
                kwargs = {"channel": event["channel"], "text": text}
                if event.get("thread_ts"):
                    kwargs["thread_ts"] = event["thread_ts"]
                client.chat_postMessage(**kwargs)
            self.store.set_posted(eval_id)
            logger.info("Posted %s for evaluation %s", decision.arm, eval_id)
        except Exception:
            # The evaluation is intentionally retained even if Slack rejects a post.
            logger.exception("Evaluation failed; Slack sent the event but the agent could not complete it")

    def fulfill_offer(self, client, action_id: str) -> None:
        offer = self.store.get_offer(action_id)
        if not offer:
            logger.warning("No persisted offer context for action %s", action_id)
            return
        channel, thread_ts, query = offer
        try:
            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text="Checking current sources…")
            if not self.search:
                text = "Research isn’t configured yet: add EXA_API_KEY and restart the agent."
            else:
                text = self.search.answer(query)
            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
            logger.info("Fulfilled approved offer %s", action_id)
        except ExaLookupTimeout:
            logger.warning("Approved research offer timed out: %s", action_id)
            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text="That Exa lookup timed out. Try again with a narrower question.")
        except Exception:
            logger.exception("Approved research offer failed")
            client.chat_postMessage(channel=channel, thread_ts=thread_ts, text="I couldn’t complete that Exa lookup. Check the agent terminal for the provider error.")


def build_app() -> App:
    agent = SlackAgent()
    app = App(token=os.environ["SLACK_BOT_TOKEN"])

    @app.event("message")
    def handle_message(event, client, logger):
        if event.get("bot_id") or event.get("subtype"):
            return
        if "<@" in event.get("text", ""):
            # app_mention is handled below; avoid evaluating the same event twice.
            return
        threading.Thread(target=agent.evaluate, args=(client, event), daemon=True).start()

    @app.event("app_mention")
    def handle_mention(event, client):
        threading.Thread(target=agent.evaluate, args=(client, event), kwargs={"app_mentioned": True}, daemon=True).start()

    @app.action(re.compile(r"^intervention:"))
    def handle_offer(ack, body, action, client):
        ack()  # Slack requires this within 3 seconds.
        eval_id = agent.store.record_button(action["action_id"], action["value"])
        logger.info("Button %s recorded for evaluation %s", action["value"], eval_id)
        message = body.get("message")
        channel = body.get("channel", {}).get("id")
        if message and channel:
            # Keep the observation, but remove the now-resolved Yes/No/Not now row.
            client.chat_update(
                channel=channel,
                ts=message["ts"],
                text=message.get("text", "Offer resolved"),
                blocks=[block for block in message.get("blocks", []) if block.get("type") != "actions"],
            )
        if action["value"] == "yes":
            threading.Thread(target=agent.fulfill_offer, args=(client, action["action_id"]), daemon=True).start()

    return app


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    if os.getenv("CONTROL_API_ENABLED", "true").lower() == "true":
        try:
            from .control_api import run_control_api

            threading.Thread(target=run_control_api, daemon=True).start()
            logger.info("Control API available at http://127.0.0.1:%s", os.getenv("CONTROL_API_PORT", "8765"))
        except ModuleNotFoundError:
            logger.warning("Control API disabled: run pip install -r requirements.txt to install FastAPI and Uvicorn")
    app = build_app()
    logger.info("Starting Slack intervention agent (Socket Mode)")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
