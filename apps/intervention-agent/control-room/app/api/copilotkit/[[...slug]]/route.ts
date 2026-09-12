import { BuiltInAgent, CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";
import { createOpenAI } from "@ai-sdk/openai";

const openrouter = createOpenAI({
  apiKey: process.env.OPENROUTER_API_KEY,
  baseURL: "https://openrouter.ai/api/v1",
});

const agent = new BuiltInAgent({
  model: openrouter(process.env.OPENROUTER_MODEL ?? "openrouter/free"),
  instructions: "You are the Quiet Agent control-room copilot. Help the operator interpret intervention decisions, suppression reasons, and outcomes. Be concise and evidence-led.",
});

const runtime = new CopilotRuntime({ agents: { default: agent } });
const handler = createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit" });

export const GET = handler;
export const POST = handler;
