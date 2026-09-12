import { createChannel } from "@copilotkit/channels";
import type { ChannelMessage } from "@copilotkit/channels";
import { isSearchConfigured, isWorkplaceConfigured, WORKPLACE_CONTEXT, ROLE_CONTEXT } from "agent-core";
import { makeChannelAgent } from "./agent";
import { required } from "./env";
import { IncidentCard, Timeline, welcomeMessage } from "./components";
import { proposeAction, readThread, searchTheWeb, setChannelRole } from "./tools";
import { resolveRole } from "./channel-role";

// Tools are registered only when their credential is present, so the agent is
// never handed a tool that will fail when it calls it.
const tools = [
  readThread,
  proposeAction,
  setChannelRole,
  ...(isSearchConfigured() ? [searchTheWeb] : []),
];

/** `message.user?.id` (canonical identity) when resolved, else the raw provider actor id. */
function actorIdOf(message: Pick<ChannelMessage, "user" | "actor">): string {
  return message.user?.id ?? message.actor.id;
}

export const channel = createChannel({
  // Must equal the Channel Code in Intelligence, character for character. A
  // mismatch leaves the Channel at "Waiting for runtime" and is validated at
  // startup, not here.
  name: required("CHANNEL_CODE"),

  // Required. "platform" derives the canonical user from provider + workspace +
  // platform user id. Do NOT move this onto CopilotRuntime — that one is for
  // web requests and must be absent on a Channels-only runtime.
  identifyUser: "platform",

  agent: makeChannelAgent,
  tools,
  components: [IncidentCard, Timeline],

  // Injected into the agent's prompt on every run. Rendering guidance for
  // incident_card/timeline lives in ROLE_CONTEXT.incidents instead of here —
  // it would contradict the general role's "don't call these" instruction.
  context: [
    ...(isWorkplaceConfigured()
      ? [{ description: "Workplace", value: WORKPLACE_CONTEXT }]
      : []),
    {
      description: "Surface",
      value:
        "This is a chat thread in a channel people are actively working in. Assume others are reading and that some joined late.",
    },
  ],

});

// A mention subscribes the conversation, so the agent then follows along instead
// of needing to be @-mentioned every single turn.
channel.onMention(async ({ thread, message }) => {
  await thread.subscribe();
  const role = await resolveRole(thread, message.platform, actorIdOf(message));
  await thread.runAgent({ context: [ROLE_CONTEXT[role]] });
});

// Non-mentioned turns only ever reach onMessage — gate them on the flag or the
// agent will answer every message in every channel it has been invited to.
channel.onMessage(async ({ thread, message }) => {
  if (await thread.isSubscribed()) {
    const role = await resolveRole(thread, message.platform, actorIdOf(message));
    await thread.runAgent({ context: [ROLE_CONTEXT[role]] });
  }
});

channel.onWelcome(async ({ thread, platform }) => {
  await thread.post(welcomeMessage(platform));
});
