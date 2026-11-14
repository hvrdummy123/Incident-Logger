import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Investigation } from "../lib/api";
import { problemToMessage } from "../lib/errors";
import { layoutServiceGraph } from "../lib/graphLayout";

type StepEvent = { seq: number; kind: string; name: string; args?: Record<string, unknown> };

export function InvestigationPage() {
  const { investigationId = "" } = useParams();
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [follow, setFollow] = useState(true);
  const [tab, setTab] = useState<"timeline" | "graph">("timeline");
  const [activePane, setActivePane] = useState<"steps" | "timeline" | "hypotheses">("steps");
  const streamRef = useRef<HTMLDivElement>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  const inv = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => api<Investigation>(`/v1/investigations/${investigationId}`),
    enabled: Boolean(investigationId),
  });

  useEffect(() => {
    if (!investigationId) return;
    const token = localStorage.getItem("traceiq.access");
    const wid = localStorage.getItem("traceiq.workspace");
    const ctrl = new AbortController();
    setStreamError(null);
    setSteps([]);
    void (async () => {
      try {
        const headers: Record<string, string> = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        if (wid) headers["X-Workspace-Id"] = wid;
        const res = await fetch(`/v1/investigations/${investigationId}/events`, {
          headers,
          signal: ctrl.signal,
        });
        if (!res.ok || !res.body) {
          setStreamError(`Couldn’t open event stream (${res.status}).`);
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop() ?? "";
          for (const chunk of parts) {
            const dataLine = chunk.split("\n").find((l) => l.startsWith("data:"));
            if (!dataLine) continue;
            try {
              const payload = JSON.parse(dataLine.slice(5).trim()) as StepEvent;
              setSteps((prev) => [...prev, payload]);
            } catch {
              /* ignore malformed */
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setStreamError(problemToMessage(err));
        }
      }
    })();
    return () => ctrl.abort();
  }, [investigationId]);

  useEffect(() => {
    if (follow && streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight;
    }
  }, [steps, follow]);

  const graph = useMemo(() => {
    const nodes = [
      { id: "gateway", score: 0.2 },
      { id: "checkout", score: 0.8 },
      { id: "payments", score: 0.4 },
    ];
    const edges = [
      { from: "gateway", to: "checkout", weight: 12 },
      { from: "checkout", to: "payments", weight: 9 },
    ];
    return layoutServiceGraph(nodes, edges, 360, 200);
  }, []);

  if (inv.isLoading) return <div className="skeleton" style={{ height: 160 }} />;
  if (inv.isError || !inv.data) {
    return (
      <div className="error-box" role="alert">
        {problemToMessage(inv.error ?? "Not found")}
      </div>
    );
  }

  const reportId = inv.data.report_id ?? null;

  const stepsPane = (
    <section className="pane">
      <h2>
        Steps{" "}
        <button type="button" className="btn" style={{ float: "right" }} onClick={() => setFollow((f) => !f)}>
          {follow ? "Pause follow" : "Follow"}
        </button>
      </h2>
      <div className="pane-body" ref={streamRef} aria-live="polite">
        {streamError && <div className="error-box">{streamError}</div>}
        {steps.length === 0 && !streamError && (
          <p className="muted">No live steps in the stream (run may have finished before open).</p>
        )}
        {steps.map((s) => (
          <div key={`${s.seq}-${s.name}`} className="step-item">
            <div>
              #{s.seq} · {s.kind} · {s.name}
            </div>
            {s.args && <div className="muted">{JSON.stringify(s.args).slice(0, 120)}</div>}
          </div>
        ))}
      </div>
    </section>
  );

  const centerPane = (
    <section className="pane">
      <div className="tabs" role="tablist" aria-label="Timeline or graph">
        <button
          type="button"
          className="btn"
          role="tab"
          aria-selected={tab === "timeline"}
          onClick={() => setTab("timeline")}
        >
          Timeline
        </button>
        <button
          type="button"
          className="btn"
          role="tab"
          aria-selected={tab === "graph"}
          onClick={() => setTab("graph")}
        >
          Service graph
        </button>
      </div>
      <div className="pane-body">
        {tab === "timeline" ? (
          <svg width="100%" height="200" role="img" aria-label="Service timeline swimlanes">
            <title>Timeline swimlanes (placeholder until briefing is attached)</title>
            {["gateway", "checkout", "payments"].map((svc, i) => (
              <g key={svc}>
                <text x="4" y={28 + i * 56} fill="currentColor" fontSize="12">
                  {svc}
                </text>
                <line
                  x1="80"
                  y1={24 + i * 56}
                  x2="95%"
                  y2={24 + i * 56}
                  stroke="var(--border)"
                />
                <rect
                  x="120"
                  y={14 + i * 56}
                  width="40"
                  height="20"
                  fill="color-mix(in srgb, var(--bad) 35%, transparent)"
                />
              </g>
            ))}
          </svg>
        ) : (
          <svg width="100%" height="220" role="img" aria-label="Service dependency graph">
            <title>Service graph layout</title>
            {graph.edges.map((e, i) => (
              <line
                key={i}
                x1={e.x1}
                y1={e.y1}
                x2={e.x2}
                y2={e.y2}
                stroke="var(--muted)"
                strokeWidth={Math.max(1, (e.weight ?? 1) / 4)}
              />
            ))}
            {graph.nodes.map((n) => (
              <g key={n.id}>
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={14}
                  fill={`color-mix(in srgb, var(--bad) ${(n.score ?? 0) * 80}%, var(--surface))`}
                  stroke="var(--border)"
                />
                <text x={n.x} y={n.y + 28} textAnchor="middle" fontSize="11" fill="currentColor">
                  {n.id}
                </text>
              </g>
            ))}
          </svg>
        )}
        <table className="data" style={{ marginTop: 12 }}>
          <caption className="muted">Graph data table</caption>
          <thead>
            <tr>
              <th>Service</th>
              <th>Score</th>
              <th>Layer</th>
            </tr>
          </thead>
          <tbody>
            {graph.nodes.map((n) => (
              <tr key={n.id}>
                <td>{n.id}</td>
                <td>{(n.score ?? 0).toFixed(2)}</td>
                <td>{n.layer}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );

  const rightPane = (
    <section className="pane">
      <h2>Hypotheses</h2>
      <div className="pane-body">
        <span className="chip open">open · deploy regression</span>
        <span className="chip supported">supported · error spike</span>
        <span className="chip refuted">refuted · DNS</span>
        <p className="muted" style={{ marginTop: 12 }}>
          Status: {inv.data.status}
          {inv.data.outcome ? ` · ${inv.data.outcome}` : ""}
          {inv.data.spent_usd != null ? ` · $${inv.data.spent_usd}` : ""}
        </p>
        <Link to={`/incidents/${inv.data.incident_id}`}>Back to incident</Link>
      </div>
    </section>
  );

  return (
    <div>
      <h1 className="page-title">Investigation</h1>
      <p className="muted mono">{investigationId}</p>

      <div className="banner" role="status" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <span>
          Outcome: <strong>{inv.data.outcome ?? inv.data.status}</strong>
          {steps.length > 0 ? ` · ${steps.length} steps streamed` : ""}
        </span>
        {reportId ? (
          <Link className="btn btn-primary" to={`/reports/${reportId}`}>
            Open report
          </Link>
        ) : (
          <span className="muted">No report id yet — try Refresh if the run just finished.</span>
        )}
        <button type="button" className="btn" onClick={() => void inv.refetch()}>
          Refresh
        </button>
      </div>

      <div className="inv-pane-switch tabs" aria-label="Investigation panes">
        {(
          [
            ["steps", "Steps"],
            ["timeline", "Timeline"],
            ["hypotheses", "Hypotheses"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className="btn"
            aria-selected={activePane === id}
            onClick={() => setActivePane(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="investigation investigation-responsive">
        <div className={activePane === "steps" ? "inv-show" : "inv-hide-narrow"}>{stepsPane}</div>
        <div className={activePane === "timeline" ? "inv-show" : "inv-hide-narrow"}>{centerPane}</div>
        <div className={activePane === "hypotheses" ? "inv-show" : "inv-hide-narrow"}>{rightPane}</div>
      </div>
    </div>
  );
}
