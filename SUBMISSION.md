# Submission checklist

Choose your city on the [global event page](https://aitinkerers.org/hackathons/global/agents-everywhere). Use that city's participant portal for the submission deadline and published judging criteria, and its handbook for eligibility and required deliverables. See [hackathon-rules.md](hackathon-rules.md) for the agent-readable summary.

## Build eligibility

- [x] Our submitted project is a net-new build created during the official hackathon period
- [x] Its core functionality was built during the event; we are not resubmitting or extending a pre-existing project and entering it as new
- [x] We identify inherited templates, libraries, prompts, components, and starter code separately from our event work

**What we inherited**

The [CopilotKit `agents-everywhere-starter-kit`](https://github.com/CopilotKit/agents-everywhere-starter-kit) in full, used as the building block the rules permit:

- The Slack Channels wiring (`createChannel`, the managed CopilotKit Intelligence adapter, `apps/channel/src/channel.tsx`'s original `onMention`/`onMessage`/`onWelcome` skeleton).
- The on-call incident-response demo persona: `ONCALL_ROLE`, and the `IncidentCard`, `Timeline`, `propose_action`, and `read_thread` tools/components (`apps/channel/src/components.tsx`, `apps/channel/src/tools.tsx`, `packages/agent-core/src/prompt.ts`).
- The Exa web-search tool (`search_web`) and the OpenRouter/OpenAI model-provider abstraction (`resolveModel`).
- CopilotKit CLI-generated Channel/project configuration (`.copilotkit/`, `agent/skills/channels-setup/`, `skills-lock.json`).

**What we built during the hackathon**

The core interaction: **the same Slack bot behaves differently depending on which channel you talk to it in**, and it reconfigures itself when asked in plain English — not a fixed persona, and not a slash command someone has to look up.

- A `ChannelRole` type (`incidents` | `general`) and a `ROLE_CONTEXT` map ([prompt.ts](packages/agent-core/src/prompt.ts)) splitting what used to be one fixed `ONCALL_ROLE` system prompt into two swappable personas, injected per-turn through Channels' `context` mechanism instead of baked into one static prompt.
- A `set_channel_role` tool ([tools.tsx](apps/channel/src/tools.tsx)) the agent calls itself when a human says something like *"set this channel to incidents mode"* — no Slack slash-command registration or app-manifest change required.
- Per-conversation role persistence with a cross-thread fallback ([channel-role.ts](apps/channel/src/channel-role.ts)). We found and fixed a real scoping bug: Channels' `thread.setState()` is scoped to one Slack *thread*, not the whole channel, so a role set via `set_channel_role` would silently reset the moment someone posted a new top-level message instead of replying in-thread. Verified live before and after the fix.
- A Slack-specific rendering fix: by reading `@copilotkit/channels-slack`'s render source directly, we found the `IncidentCard`'s severity-color `accent` prop is a documented API the Slack renderer never implements — so severity was visually invisible. Added an emoji severity marker (🔴/🟠/⚪/🟢) as a working substitute.
- The environment work to get the whole pipeline live end-to-end: correcting `.env` (`INTELLIGENCE_API_KEY` naming, a valid non-`:free` OpenRouter model slug, a `maxOutputTokens` cap sized to the account's actual credit balance), and resolving a stale-process port conflict.

Running the supplied incident demo unmodified would not establish a new project — the routing layer above is the original interaction this submission demonstrates.

## Title and description

**Project title:** Chatterbox

**What you built**

Chatterbox is a Slack bot where every channel starts as a plain, general-purpose assistant with live web search. Say *"set this channel to incidents mode"* in any channel, and from that point on **that specific channel's** bot switches persona: terser tone, proactively draws a structured `incident_card`/`timeline` instead of prose, and gates any production-sounding action behind an explicit approve/hold card rather than acting. A second, untouched channel keeps behaving like a plain assistant throughout — same Slack app, same running process, two different agents in practice, selected by conversation rather than by config file.

**Who it is for**

A team with one shared Slack workspace that has both incident-response channels and everyday team channels, and doesn't want to run two separate bots — or manually reconfigure one bot's behavior through an admin panel — to get the right persona in the right room.

**Why the context matters**

Remove the surrounding context and this becomes a chatbot that either always draws incident cards whether the room wants them or not, or always talks like a generalist even mid-outage. With context-aware routing, the agent's understanding of *where it is* — this specific channel's configured role — changes which tools it reaches for and how it talks, and it learns that role from being told once in plain language rather than from a config file or a slash command someone has to remember.

**Sponsor technologies used**

- **CopilotKit** (Channels + managed Intelligence) — the Slack transport, agent run loop, per-thread state (`thread.setState`/`thread.state`), and native Slack Block Kit rendering that the whole routing mechanism is built on.
- **OpenRouter** — model routing for the chat model.
- **Exa** — live grounding for the `search_web` tool.

## Evidence for the judging criteria

Judges score each of the four official criteria from 1–5. This checklist helps you gather evidence; it does not guarantee a score. A working starter is a foundation for your own project.

| Official criterion | Show in your project and demo |
|---|---|
| Core Requirements & Functionality | Live in Slack: default general-assistant reply → "set this channel to incidents mode" → confirmation → an incident-shaped message drawing a real `incident_card`/`timeline`. All four steps were run live against the deployed Slack app, not offline tests. |
| Innovation & Theme Alignment | Show the same bot in two channels side by side: one still general, one switched to incidents. Removing the channel context collapses this to a single fixed persona — the comparison is the point. |
| Technical Execution & Integration | Show a follow-up incident question as a **new top-level message**, not a thread reply, still landing in incidents mode — this exercises the cross-thread persistence fallback, a real integration limit we found and worked around (see [channel-role.ts](apps/channel/src/channel-role.ts)). Also show a general-channel message where the bot explicitly declines to track an incident and offers to switch, rather than guessing. |
| Usefulness & Agentic Experience | Ask it to do something production-sounding ("restart the checkout service") while in incidents mode — it posts an Approve/Hold card and takes no action either way, distinguishing a decision from execution. |

- [x] We can point to visible evidence for every criterion (see demo script below)
- [x] We distinguish live services, sample data, session-only state, and standalone recipes (see "What the incident data is" below)
- [x] Sponsor technologies contribute to the workflow; their count is not a judging criterion

### What the incident data actually is — read before demoing

`incident_card`/`timeline` are **not** connected to any real monitoring, paging, or logging system — there is no PagerDuty/Datadog/Grafana/log-reader integration in this project. The only tools that can put facts into a card are `read_thread` (the Slack conversation itself) and `search_web` (public web via Exa). When the agent draws a card, it is reformatting what a human already typed into the thread into a structured, glanceable summary — not querying live telemetry. It does this honestly (citing "unknown"/"not recorded yet" for gaps rather than inventing specifics), but the underlying facts are exactly as real as what you type. Say this plainly in the demo video and to judges; don't imply a live monitoring integration that isn't there.

## Public repository

- [x] A new participant can run the quickstart from a clean clone ([apps/channel/README.md](apps/channel/README.md) now points at this project's own repo and lists this project's actual working `.env` values, not the generic OpenAI-default example)
- [x] The README lists the credentials and separate processes required (OpenRouter, CopilotKit Intelligence, Exa, and the optional Ambiguous AI key — see [apps/channel/README.md#get-started](apps/channel/README.md#get-started))
- [x] `npm run verify` passes (typecheck across all workspaces + tests; confirmed 2026-09-12 — note: the aggregate `npm test --workspaces` script reports 0 tests for `agent-core` and `channel` due to a pre-existing glob-quoting quirk in this environment, unrelated to work done here; running `node --import tsx --test src/**/*.test.tsx` directly in `apps/channel` shows all 5 tests passing)
- [x] `.env`, tokens, generated traces with sensitive data, and account secrets are excluded (verified file-by-file before the first push; `.env*` is gitignored)
- [x] Sample data, session-only state, and unimplemented integrations are clearly labeled (see "What the incident data actually is" above, now also linked from [apps/channel/README.md](apps/channel/README.md#try-the-flow))

## Two-minute demo video

- [ ] Show the surface and existing context before the prompt
- [ ] Demonstrate one complete interaction
- [ ] Show a visible result: an actual record, local state change, or research source links
- [ ] If showing an approval, distinguish the decision from execution and demonstrate the resulting behavior
- [ ] State which sponsor technologies made the interaction possible
- [ ] Keep the video within the event's limit and check audio

See [demo prompts](dev-docs/demo-prompts.md) for a reproducible incident workflow, and the criteria table above for the specific sequence this project's video should follow: general reply → role switch → incident card → cross-thread persistence → propose_action approval gate.

## Social post and final submission

- [ ] Follow the organizer's posting and sponsor-tagging instructions
- [ ] Link the public repository and video
- [ ] Credit the sponsors you used and applicable local partners
- [ ] Check the live integration once more before recording or submitting
- [ ] Inspect the repository, video and screenshots for secrets

Prepare the post and submission for a human to publish; running the starter kit
does not publish either automatically.
