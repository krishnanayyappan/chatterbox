# Chatterbox — a context-aware Slack agent

**OpenRouter + CopilotKit Channels + Exa**

Chatterbox reads an existing conversation, researches what matters, and replies in the same Slack thread with native cards and source links — and it behaves differently depending on which channel you talk to it in. Every channel starts as a plain general-purpose assistant. Say "set this channel to incidents mode" and *that specific channel* switches to an on-call persona: terser tone, structured incident cards and timelines instead of prose, and any production-sounding action gated behind an explicit approve/hold card. A different, untouched channel keeps behaving like a plain assistant the whole time. See [../../SUBMISSION.md](../../SUBMISSION.md) for what was inherited from the starter kit versus built for this project.

[![Slack thread agent demo](../../assets/demos/slack.gif)](../../assets/demos/slack.mp4)

_Scroll through a completed Slack thread: incident context, Exa source cards, and the final answer. The preview is sped up; click it for the full MP4._

## Get started

Use Node.js 22+, then clone and install the kit:

```bash
git clone https://github.com/krishnanayyappan/chatterbox.git
cd chatterbox
npm ci
cp .env.example .env
```

Run the commands below from the repository root. Configure root `.env` with your own credentials — [OpenRouter](../../using-sponsor-tools.md#openrouter), [CopilotKit Intelligence](../../using-sponsor-tools.md#copilotkit), and [Exa](../../using-sponsor-tools.md#exa) — using this project's actual working configuration as a reference:

```dotenv
# Chat model — OpenRouter (see dev-docs/model-switching.md for other providers)
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-key
MODEL=openai/gpt-5.6-luna       # cheap tier; see packages/agent-core/src/model-meta.ts for alternates

# CopilotKit Intelligence — the managed Slack Channel. INTELLIGENCE_API_KEY must
# be named exactly this — `copilotkit project select` sometimes writes it as
# CPK_INTELLIGENCE_API_KEY instead, which the runtime will NOT read.
CHANNEL_CODE=your-channel-code
INTELLIGENCE_API_KEY=your-project-key       # looks like cpk-{projectId}_...
INTELLIGENCE_GATEWAY_WS_URL=wss://realtime.intelligence.copilotkit.ai

# Exa — powers the search_web tool
EXA_API_KEY=your-exa-key
EXA_SEARCH_TYPE=fast

# HTTP health-check port. Slack delivery arrives over the Channel's own
# outbound websocket, not this port — override it if 3000 is already in use
# locally, no functional effect either way.
PORT=3000

# Optional — Ambiguous AI workplace tools (mail/tasks/CRM/docs/calendar over MCP).
# Unset by default: the agent is never offered these tools unless this is set.
# AMBIGUOUS_API_KEY=your-ambiguous-key
```

Choose a model your account can actually afford at the default `maxOutputTokens` (2048, set in [packages/agent-core/src/agent.ts](../../packages/agent-core/src/agent.ts)) — an expensive model with a thin balance will fail with an OpenRouter "insufficient credits" error rather than a clear config error. Start the official onboarding handoff:

```bash
npm run channel:setup -- --no-clipboard
```

This installs the maintained `channels-setup` skill and prints a prompt. Give that prompt to your coding agent in this checkout and specify **Slack**, using the existing `apps/channel` app. Have the agent follow the skill through sign-in, project/Channel configuration, Slack installation, and a real reply. The command alone does not create the Channel. Keep existing `.env` values; the listener reads `CHANNEL_CODE` and `INTELLIGENCE_API_KEY`. The [setup guide](../../dev-docs/setup.md) and [screenshot walkthrough](../../dev-docs/channels-sdk-walkthrough/README.md) provide manual reference.

```bash
npm run dev:slack
```

Invite the bot to a Slack channel and mention it in a populated thread. CopilotKit Intelligence manages the Slack connection; this listener needs no public tunnel or Slack app token on the managed path.

## Try the flow

**Context-aware routing (new for this project):**

1. In a fresh channel, `@mention` the bot with something ordinary (e.g. "what's 2+2"). It answers as a plain assistant — this is the default `general` role, and it will not draw an incident card unprompted.
2. Say `@mention set this channel to incidents mode`. The agent calls its own `set_channel_role` tool and confirms — no slash command, no config file.
3. Send an incident-shaped message in that same channel. It draws an `incident_card` and, once there are 3+ events, a `timeline`.
4. Post a **new top-level message** (not a thread reply) describing a follow-up. It should still be in incidents mode — this exercises the cross-thread persistence fallback in [src/channel-role.ts](src/channel-role.ts).
5. In a *different*, untouched channel, ask something ordinary again — confirm it's still the plain assistant there.

**Inherited incident flow (from the starter kit):**

1. Add two or three facts to a Slack thread before mentioning the agent.
2. Ask it to catch up using the thread and render a card. Verify facts came from earlier messages rather than your last prompt.
3. Ask it to research a related question with Exa. `search_web` posts native **Search sources** cards when sources are returned; open the links and separate published evidence from facts in your thread.
4. Ask a follow-up that relies on the discussion. Check the answer and card remain in the same thread.

Use [demo prompts](../../dev-docs/demo-prompts.md#slack-context-sources-card-follow-up) for exact incident inputs. If you add an external write, enforce approval in code before that write. The included proposal card records a decision without executing a production action.

**What the incident data actually is:** `incident_card`/`timeline` are populated entirely from `read_thread` (what people typed in Slack) and, when asked, `search_web` (public web via Exa) — there is no monitoring/paging/log integration behind them. See [../../SUBMISSION.md](../../SUBMISSION.md#what-the-incident-data-actually-is--read-before-demoing) before presenting this as a live-data demo.

## Customize these files

| Piece | File |
|---|---|
| Agent and model | [Shared agent factory](../../packages/agent-core/src/agent.ts), using CopilotKit's built-in agent |
| Channel lifecycle and role resolution | [src/channel.tsx](src/channel.tsx): mention, subscribe, respond to subscribed messages, resolve this conversation's role before each run |
| Channel-only run adapter | [src/agent.ts](src/agent.ts): keeps outer transcript/state while using fresh inner agent runs; base prompt is domain-neutral (`SURFACE_RULES`) since role content is injected per-run instead |
| Per-channel role persistence | [src/channel-role.ts](src/channel-role.ts): `thread.setState`/`state` (per-Slack-thread) plus a per-actor in-memory fallback for cross-thread persistence |
| Thread context and research | [src/tools.tsx](src/tools.tsx) and [src/search.tsx](src/search.tsx): `read_thread`, `set_channel_role`, and Exa-backed `search_web` |
| Native cards | [src/components.tsx](src/components.tsx): incident card and timeline via Channels JSX (severity shown as an emoji marker — Slack's renderer doesn't implement the `accent` color prop) |
| Prompt and roles | [Shared prompt](../../packages/agent-core/src/prompt.ts): `SURFACE_RULES` (domain-free) plus `ROLE_CONTEXT` (`incidents` → `ONCALL_ROLE`, `general` → `GENERAL_ROLE`) |

OpenRouter can be used as the model gateway through the shared provider settings in [using-sponsor-tools.md](../../using-sponsor-tools.md#openrouter). Teams or another messaging platform can reuse the Channels pattern, but this starter app is wired for managed Slack.

## Give this to your coding agent

```text
Read the root hackathon overview, rules, sponsor guide, and AGENTS.md.
Read .agents/skills/build-channels-agent/SKILL.md before changing Slack code.
If Slack is not connected, run npm run channel:setup -- --no-clipboard
from the repository root and follow its prompt using the channels-setup
skill. Select Slack and connect the existing apps/channel app.
Adapt apps/channel to our project's user and conversation. Preserve
read_thread, use Exa when research helps, and render results with Channels JSX.
Replace incident-specific schemas, tools, and prompts with our own workflow.
Demonstrate that earlier messages change the answer and return source links.
Run npm run verify and document the live Slack checks separately.
```

## Verify and limits

Run `npm run verify` for root/channel typechecks and offline tests. Live Slack delivery, Exa search, and model responses require your own accounts and should be documented separately from local tests.

Keep the pinned Channels/runtime pair and the `@ag-ui/client` override. The [Channels skill](../../.agents/skills/build-channels-agent/SKILL.md) supplies the verified API vocabulary. [Channels guide](https://copilotkit.ai/channels-guide.md) · [OpenTag reference app](https://github.com/CopilotKit/OpenTag)
