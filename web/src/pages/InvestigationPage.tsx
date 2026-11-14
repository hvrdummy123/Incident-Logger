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
  const [narrowTab, setNarrowTab] = useState<"steps" | "center" | "hypotheses">("center");
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

  const reportLink =
    (inv.data as Investigation & { report_id?: string }).report_id ??
    null;

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
        {steps.length === 0 && <p className="muted">Waiting for steps…</p>}
        {steps.map((s) => (
          <div key={`${s.seq}-${s.name}`} className="step-item">
            <div>
              #{s.seq} · {s.kind} · {s.name}
            </div>
            {s.args && (
              <div className="muted">{JSON.stringify(s.args).slice(0, 120)}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );

  const centerPane = (
    <section className="pane">
      <div className="tabs" role="tablist">
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
          Evidence drawer opens from report citations. Status: {inv.data.status}
          {inv.data.outcome ? ` · ${inv.data.outcome}` : ""}
        </p>
        {reportLink ? (
          <p>
            <Link to={`/reports/${reportLink}`}>Open report</Link>
          </p>
        ) : (
          <p className="muted">
            If a report was produced, open it from the investigation response after refresh, or check
            API <span className="mono">report_id</span>.
          </p>
        )}
        <Link to={`/incidents/${inv.data.incident_id}`}>Back to incident</Link>
      </div>
    </section>
  );

  return (
    <div>
      <h1 className="page-title">Investigation</h1>
      <p className="muted mono">{investigationId}</p>

      <div className="tabs" style={{ marginBottom: 8 }} aria-label="Narrow layout tabs">
        {(["steps", "center", "hypotheses"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className="btn"
            aria-selected={narrowTab === t}
            onClick={() => setNarrowTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="investigation">
        <div className="desktop-only">{stepsPane}</div>
        <div className="desktop-only">{centerPane}</div>
        <div className="desktop-only">{rightPane}</div>
      </div>

      <div className="mobile-panes">
        {narrowTab === "steps" && stepsPane}
        {narrowTab === "center" && centerPane}
        {narrowTab === "hypotheses" && rightPane}
      </div>

      <style>{`
        .mobile-panes { display: none; }
        @media (max-width: 960px) {
          .investigation .desktop-only { display: none; }
          .mobile-panes { display: block; }
        }
        @media (min-width: 961px) {
          .tabs[aria-label="Narrow layout tabs"] { display: none; }
        }
      `}</style>
    </div>
  );
}
