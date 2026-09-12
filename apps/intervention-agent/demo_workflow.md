# Demo workflow: helping a group plan dinner

## The goal

Demonstrate an agent that is a restrained participant in a Slack planning
channel. It does not answer every message. It watches for a real decision
blocker, offers the cheapest helpful intervention, researches only when someone
approves, and records a decision only when the group has clearly made one.

## The human-life scenario

Channel: `#weekend-plans`

Maya, Jordan, and Priya are trying to choose a restaurant for Saturday.
Jordan needs vegetarian options. The group likes Nopa, but no one knows its
Saturday hours or menu. That missing information blocks the choice.

## Demo transcript

| Speaker | Slack message | Agent behavior |
| --- | --- | --- |
| Maya | “Saturday?” | Silence. This is only a proposal. |
| Jordan | “I can do Saturday, but I need somewhere with vegetarian options.” | Silence. This is a stated constraint, not a reason to interrupt. |
| Priya | “What about Nopa?” | Silence. The group is still progressing. |
| Maya | “Is it open late enough?” | Silence. One unanswered question is not necessarily a blocker yet. |
| Jordan | “I think so?” | Silence. The group has not asked for the agent. |
| Priya | “Not sure.” | The agent identifies a `missing_fact`: the choice depends on hours and vegetarian options. |

The conversation is already in a restaurant-planning thread, so the agent makes
a **thread offer**, not a channel post:

> Nopa’s hours and vegetarian options are the open questions. Want me to check?

The offer has Block Kit buttons: **Yes**, **No**, and **Not now**.

If Priya taps **Yes**, the agent uses Exa to search for current official hours
and menu information, then responds in the same thread:

> Nopa is open until 10pm Saturday and has several vegetarian mains.
> Sources: <hours link> · <menu link>

The group then reaches a decision:

| Speaker | Slack message | Agent behavior |
| --- | --- | --- |
| Maya | “Great, Saturday at 7?” | Silence. A proposed decision is not a settled one. |
| Jordan | “Works.” | Silence. Wait for confirmation. |
| Priya | “Done.” | Detect `convergence`: multiple people endorse one option and no objection follows. |

The agent uses the `act` arm to record, without interpretation:

> Recording: Nopa, Saturday at 7pm. Say so if that’s wrong.

## How it knows when to respond

The agent evaluates the latest 15 messages after each new Slack message. Every
evaluation returns and logs a decision, including `silence`.

### Suppressors: reasons to stay quiet

These run before any language-model classification:

- **Refractory:** it posted in the last 90 seconds.
- **Rally:** three or more messages arrived in 30 seconds. A fast conversation
  is often productive, so it waits for a 20-second gap.
- **Claimed:** someone said “I’ll check,” “let me look,” or “on it” in the last
  five messages.
- **Declined:** after two declined offers in one session, the agent raises its
  threshold and never escalates above an ephemeral message.

An explicit `@agent` mention bypasses all suppressors and goes directly to the
`act` arm.

### Triggers: reasons to consider speaking

| Trigger | What it means | Usual response |
| --- | --- | --- |
| `direct_request` | Someone mentions the agent or explicitly asks for research. | Act. |
| `missing_fact` | A pending choice depends on a fact nobody has. | Offer research in a thread. |
| `checkable_dispute` | People make contradictory factual claims that can be looked up. | Offer research in a thread. |
| `circling` | Four messages contain no new option, constraint, or fact while two positions persist. | Offer help to the channel. |
| `convergence` | Two or more people endorse an option, no objection follows, and it is not already recorded. | Record the decision. |
| `none` | The conversation is progressing, social, or irrelevant. | Silence. |

Heat is not a trigger. A disagreement that adds new information is productive
work, not a reason for the agent to interrupt.

### Cheapest helpful surface

The agent escalates rather than jumping to a channel-wide message:

1. `react` — one emoji; acknowledge a settled trivial point.
2. `ephemeral` — private note for one person’s stated constraint.
3. `thread_offer` — ask thread participants before researching.
4. `channel_offer` — only for a group-wide blocker or true circling.
5. `act` — direct request or recording a clear group decision.

Thread messages never turn into channel-wide offers. Confidence from 0.60 to
0.70 downgrades one rung. Two declined offers cap future suggestions at
`ephemeral`.

## What Exa does

Exa is a research tool, not the decision-maker. The intervention policy decides
whether to speak before Exa is called.

- A direct mention such as `@DinnerAgent find Nopa Saturday hours` runs an Exa
  search and posts up to three concise linked results.
- An unsolicited `missing_fact` or `checkable_dispute` first receives an offer
  with Yes / No / Not now buttons.
- Exa runs only after **Yes**. Results remain in the relevant thread.

## What the audience should see

Split the demo screen between `#weekend-plans` and `#agent-log`.

The log channel displays every evaluation, including silence, in this form:

```text
missing_fact → thread_offer (0.78) — Nopa hours and vegetarian options are unknown
```

This makes the important behavior visible: the agent deliberately chose not to
speak several times before it made one useful, low-attention offer.

## Success criteria

- The agent remains silent while the group is making progress.
- It offers Exa research only when a missing fact or factual dispute blocks a
  decision.
- One button click is enough to approve or decline the help.
- Research results appear in the thread, not as a channel interruption.
- The final post records a decision only after clear human agreement.
