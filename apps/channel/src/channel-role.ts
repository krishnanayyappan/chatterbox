import { DEFAULT_CHANNEL_ROLE, type ChannelRole } from "agent-core";

/**
 * `thread.setState()`/`thread.state()` are scoped to one Channels conversation,
 * which for managed Slack is one Slack THREAD (Intelligence's per-thread
 * `conversationKey`) — not the whole channel. A fresh top-level `@mention`
 * that isn't a reply-in-thread gets a brand-new conversationKey with no state,
 * so a role set via set_channel_role would otherwise "disappear" the moment
 * someone posts a new top-level message instead of replying in the bot's
 * thread. Managed Slack never exposes a real Slack channel id to local code
 * (see project memory / the earlier channel-name investigation), so there is
 * no way to key state on "the channel" directly.
 *
 * Fallback: remember the last role a person set, keyed by (platform, actor).
 * `resolveRole` prefers the thread's own state (correctly scoped) and only
 * falls back to this when the thread has never had a role set. This is an
 * in-memory, best-effort approximation — lost on restart, and scoped to the
 * person rather than the channel — good enough for a single active demo
 * conversation, not a substitute for real per-channel storage.
 */
const recentRoleByActor = new Map<string, ChannelRole>();

function actorKey(platform: string, actorId: string): string {
  return `${platform}:${actorId}`;
}

type ReadableThread = { state(): Promise<unknown> };
type WritableThread = { setState(value: unknown): Promise<void> };

export async function resolveRole(
  thread: ReadableThread,
  platform: string,
  actorId: string,
): Promise<ChannelRole> {
  const state = (await thread.state()) as { role?: ChannelRole } | undefined;
  if (state?.role) return state.role;
  return recentRoleByActor.get(actorKey(platform, actorId)) ?? DEFAULT_CHANNEL_ROLE;
}

export async function persistRole(
  thread: WritableThread,
  platform: string,
  actorId: string,
  role: ChannelRole,
): Promise<void> {
  await thread.setState({ role });
  recentRoleByActor.set(actorKey(platform, actorId), role);
}
