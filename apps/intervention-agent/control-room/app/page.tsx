"use client";

import { CopilotSidebar } from "@copilotkit/react-core/v2";
import { useEffect, useMemo, useState } from "react";

type Evaluation = {
  eval_id: string; ts: string; trigger: string; arm_selected: string; confidence: number;
  reason: string; suppressed_by: string | null; posted: boolean;
  outcome: { button?: string; human_replies_within_120s?: number };
};

const API = process.env.NEXT_PUBLIC_CONTROL_API_URL ?? "http://127.0.0.1:8765";
const ARM_COLOR: Record<string, string> = { silence: "slate", react: "blue", ephemeral: "amber", thread_offer: "coral", channel_offer: "orange", act: "lime" };

export default function ControlRoom() {
  const [items, setItems] = useState<Evaluation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState("waiting for agent");

  useEffect(() => {
    const refresh = async () => {
      try {
        const response = await fetch(`${API}/evaluations`, { cache: "no-store" });
        if (!response.ok) throw new Error(`API ${response.status}`);
        setItems(await response.json());
        setNow(new Date().toLocaleTimeString());
        setError(null);
      } catch { setError("Control API offline — start the Python Slack agent first."); }
    };
    refresh();
    const interval = window.setInterval(refresh, 3500);
    return () => window.clearInterval(interval);
  }, []);

  const metrics = useMemo(() => ({
    evaluations: items.length,
    spoke: items.filter((item) => item.posted).length,
    held: items.filter((item) => item.arm_selected === "silence").length,
  }), [items]);

  return (
    <main>
      <header>
        <div className="eyebrow"><span className="pulse" /> LIVE INTERVENTION TELEMETRY</div>
        <h1>QUIET<br /><em>IS A FEATURE.</em></h1>
        <p className="lede">A control room for the Slack agent that earns attention instead of taking it.</p>
        <div className="status">{error ?? `SYNCED ${now}`}</div>
      </header>

      <section className="metrics" aria-label="Intervention metrics">
        <Metric value={metrics.evaluations} label="moments considered" />
        <Metric value={metrics.held} label="times it held back" emphasize />
        <Metric value={metrics.spoke} label="deliberate interventions" />
      </section>

      <section className="ledger">
        <div className="ledger-top"><h2>Decision ledger</h2><span>newest first · refreshes every 3.5s</span></div>
        {items.length === 0 ? <div className="empty">No decisions yet. Let the channel breathe, then watch the evidence arrive.</div> : items.map((item) => (
          <article className="row" key={item.eval_id}>
            <div className={`arm ${ARM_COLOR[item.arm_selected] ?? "slate"}`}>{item.arm_selected.replace("_", " ")}</div>
            <div className="signal"><strong>{item.trigger.replace("_", " ")}</strong><p>{item.reason}</p></div>
            <div className="confidence">{Math.round(item.confidence * 100)}<small>%</small></div>
            <div className="outcome">{item.suppressed_by ? "SUPPRESSED" : item.outcome.button ? `HUMAN: ${item.outcome.button}` : item.posted ? "POSTED" : "HELD"}</div>
          </article>
        ))}
      </section>

      <CopilotSidebar labels={{ modalHeaderTitle: "Ask the control room", welcomeMessageText: "Ask about intervention policy, suppressors, or what to test next." }} />
    </main>
  );
}

function Metric({ value, label, emphasize = false }: { value: number; label: string; emphasize?: boolean }) {
  return <div className={`metric ${emphasize ? "emphasize" : ""}`}><strong>{value}</strong><span>{label}</span></div>;
}
