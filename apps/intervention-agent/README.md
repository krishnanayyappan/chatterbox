# Slack Intervention Agent

A deliberately restrained Slack agent. It decides **whether** to speak and uses
the cheapest helpful surface: react, ephemeral message, thread offer, channel
offer, or action. Slack I/O and the LLM classifier are adapters around an
offline-testable policy engine.

## Run locally

1. Create a Slack app, enable **Socket Mode**, and subscribe to
   `message.channels` and `app_mention` (also `message.groups` for private
   channels). Add `channels:history`, `chat:write`, `reactions:write`,
   `app_mentions:read`, and `groups:history` for private channels.
2. Copy `.env.example` to `.env` and supply the two Slack tokens. `OPENROUTER_API_KEY`
   is optional: without it the agent logs decisions but stays silent unless
   directly mentioned.
   Add `EXA_API_KEY` to let an @mention such as `@agent find current AI news`
   run a three-result Exa search. Exa is used only after the policy has chosen
   the `act` arm; it never influences whether the bot interrupts.
3. From the Chatterbox repository root, install once and run:

   ```powershell
   npm run setup:intervention
   npm run dev:intervention
   ```

## Test the policy without Slack

```powershell
python -m unittest discover -s tests -v
```

The fixtures model the six transcript cases in the spec. They exercise the
policy with a deterministic classifier; no Slack, API key, or network is used.

## Important operating details

- Every evaluation, including silence, is stored in `data/intervention.sqlite3`.
- Set `AGENT_LOG_CHANNEL_ID` to post a compact #agent-log panel line for each
  evaluation.
- Button actions are mapped to their evaluation ID; click outcomes are saved
  immediately. `outcomes.py` has the delayed two-minute outcome pass seam.
- The app acks interactions before it writes to SQLite or calls Slack.

`chat:write.customize` is not required by this implementation; only add it if
you deliberately want to customize the app identity.

## Provider architecture

- **OpenRouter** supplies the one classification call over the message window
  and writes replies to direct `@mentions`. Set `OPENROUTER_MODEL` to a model
  slug available to your account. Direct mentions include the latest 15 human
  channel messages as response context; the app does not send the entire channel
  history.
- **Exa** is the approval-gated web lookup tool for direct mentions and accepted
  offers.
- **CopilotKit** should be the separate web dashboard for human review, logs,
  and manual approval. The included [`control-room`](control-room/README.md)
  is that dashboard: it reads the live local decision log and uses a CopilotKit
  runtime backed by the same OpenRouter configuration.
