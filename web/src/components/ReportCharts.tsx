import { useMemo, useState } from "react";

export type SuspectScore = { service: string; score: number };
export type SeriesPoint = { ts_ms: number; value: number };
export type ErrorSeries = { service: string; points: SeriesPoint[] };
export type TimelineMark = {
  ts_ms: number;
  label: string;
  kind: "onset" | "change" | "error";
};

export type ReportViz = {
  suspect_scores?: SuspectScore[];
  error_series?: ErrorSeries[];
  timeline_marks?: TimelineMark[];
  confidence?: number;
};

const PALETTE = ["#1f4fd8", "#c2670a", "#2e7d32", "#7b1fa2", "#00838f", "#c62828"];

function fmtTime(ts: number): string {
  try {
    return new Date(ts).toISOString().slice(11, 19);
  } catch {
    return String(ts);
  }
}

export function ReportCharts({ viz }: { viz?: ReportViz | null }) {
  const scores = viz?.suspect_scores ?? [];
  const series = viz?.error_series ?? [];
  const marks = viz?.timeline_marks ?? [];
  const confidence = viz?.confidence ?? 0;

  const [focus, setFocus] = useState<string | null>(null);
  const [hover, setHover] = useState<{
    service: string;
    ts: number;
    value: number;
    x: number;
    y: number;
  } | null>(null);

  const maxScore = Math.max(1, ...scores.map((s) => s.score));

  const lineGeom = useMemo(() => {
    const allPts = series.flatMap((s) => s.points);
    if (!allPts.length) return null;
    const minT = Math.min(...allPts.map((p) => p.ts_ms));
    const maxT = Math.max(...allPts.map((p) => p.ts_ms));
    const maxV = Math.max(0.05, ...allPts.map((p) => p.value));
    const w = 560;
    const h = 180;
    const pad = { l: 40, r: 12, t: 12, b: 28 };
    const iw = w - pad.l - pad.r;
    const ih = h - pad.t - pad.b;
    const x = (ts: number) => pad.l + ((ts - minT) / Math.max(1, maxT - minT)) * iw;
    const y = (v: number) => pad.t + ih - (v / maxV) * ih;
    return { w, h, pad, minT, maxT, maxV, x, y, iw, ih };
  }, [series]);

  if (!scores.length && !series.length && !marks.length) {
    return null;
  }

  return (
    <section className="report-viz" aria-label="Investigation charts">
      <h2>Signals</h2>
      <p className="muted">
        Interactive views from the same briefing the agent used. Click a service to focus.
      </p>

      <div className="viz-grid">
        <div className="viz-panel">
          <h3>Suspect scores</h3>
          <svg
            viewBox={`0 0 360 ${Math.max(80, 28 + scores.length * 28)}`}
            width="100%"
            role="img"
            aria-label="Horizontal bar chart of suspect scores"
          >
            {scores.map((s, i) => {
              const barW = (s.score / maxScore) * 220;
              const y = 8 + i * 28;
              const active = !focus || focus === s.service;
              return (
                <g
                  key={s.service}
                  opacity={active ? 1 : 0.35}
                  style={{ cursor: "pointer" }}
                  onClick={() => setFocus(focus === s.service ? null : s.service)}
                >
                  <text x="0" y={y + 12} fontSize="11" fill="currentColor">
                    {s.service}
                  </text>
                  <rect
                    x="110"
                    y={y}
                    width={barW}
                    height="16"
                    rx="3"
                    fill={PALETTE[i % PALETTE.length]}
                  />
                  <text x={118 + barW} y={y + 12} fontSize="11" fill="var(--muted)">
                    {s.score.toFixed(2)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="viz-panel">
          <h3>Confidence</h3>
          <svg viewBox="0 0 120 120" width="140" height="140" role="img" aria-label="Confidence gauge">
            <circle cx="60" cy="60" r="44" fill="none" stroke="var(--border)" strokeWidth="10" />
            <circle
              cx="60"
              cy="60"
              r="44"
              fill="none"
              stroke="var(--primary)"
              strokeWidth="10"
              strokeDasharray={`${Math.max(0, Math.min(1, confidence)) * 276} 276`}
              strokeLinecap="round"
              transform="rotate(-90 60 60)"
            />
            <text x="60" y="64" textAnchor="middle" fontSize="18" fontWeight="600" fill="currentColor">
              {(confidence * 100).toFixed(0)}%
            </text>
          </svg>
          {focus && (
            <p className="muted">
              Focused: <strong>{focus}</strong>{" "}
              <button type="button" className="btn" onClick={() => setFocus(null)}>
                Clear
              </button>
            </p>
          )}
        </div>
      </div>

      {lineGeom && series.length > 0 && (
        <div className="viz-panel viz-wide">
          <h3>Error rate (from logs)</h3>
          <div style={{ position: "relative" }}>
            <svg
              viewBox={`0 0 ${lineGeom.w} ${lineGeom.h}`}
              width="100%"
              role="img"
              aria-label="Error rate over time by service"
              onMouseLeave={() => setHover(null)}
            >
              {[0, 0.25, 0.5, 0.75, 1].map((f) => {
                const yy = lineGeom.pad.t + lineGeom.ih * (1 - f);
                return (
                  <g key={f}>
                    <line
                      x1={lineGeom.pad.l}
                      x2={lineGeom.w - lineGeom.pad.r}
                      y1={yy}
                      y2={yy}
                      stroke="var(--border)"
                      strokeDasharray="3 3"
                    />
                    <text x={4} y={yy + 4} fontSize="10" fill="var(--muted)">
                      {(f * lineGeom.maxV * 100).toFixed(0)}%
                    </text>
                  </g>
                );
              })}
              {series.map((s, i) => {
                if (!s.points.length) return null;
                const active = !focus || focus === s.service;
                const d = s.points
                  .map((p, idx) => `${idx === 0 ? "M" : "L"} ${lineGeom.x(p.ts_ms)} ${lineGeom.y(p.value)}`)
                  .join(" ");
                return (
                  <g key={s.service} opacity={active ? 1 : 0.2}>
                    <path
                      d={d}
                      fill="none"
                      stroke={PALETTE[i % PALETTE.length]}
                      strokeWidth={active ? 2.5 : 1.5}
                      style={{ cursor: "pointer" }}
                      onClick={() => setFocus(focus === s.service ? null : s.service)}
                    />
                    {s.points.map((p, j) => (
                      <circle
                        key={j}
                        cx={lineGeom.x(p.ts_ms)}
                        cy={lineGeom.y(p.value)}
                        r={3}
                        fill={PALETTE[i % PALETTE.length]}
                        style={{ cursor: "pointer" }}
                        onMouseEnter={() =>
                          setHover({
                            service: s.service,
                            ts: p.ts_ms,
                            value: p.value,
                            x: lineGeom.x(p.ts_ms),
                            y: lineGeom.y(p.value),
                          })
                        }
                        onClick={() => setFocus(focus === s.service ? null : s.service)}
                      />
                    ))}
                  </g>
                );
              })}
              {marks.map((m, i) => {
                const x = lineGeom.x(m.ts_ms);
                const color =
                  m.kind === "onset" ? "var(--bad)" : m.kind === "error" ? "var(--signal)" : "var(--primary)";
                return (
                  <g key={`${m.ts_ms}-${i}`}>
                    <line
                      x1={x}
                      x2={x}
                      y1={lineGeom.pad.t}
                      y2={lineGeom.h - lineGeom.pad.b}
                      stroke={color}
                      strokeDasharray="4 3"
                      opacity={0.7}
                    />
                    <title>{`${m.label} @ ${fmtTime(m.ts_ms)}`}</title>
                  </g>
                );
              })}
              <text
                x={lineGeom.pad.l}
                y={lineGeom.h - 6}
                fontSize="10"
                fill="var(--muted)"
              >
                {fmtTime(lineGeom.minT)}
              </text>
              <text
                x={lineGeom.w - lineGeom.pad.r}
                y={lineGeom.h - 6}
                fontSize="10"
                fill="var(--muted)"
                textAnchor="end"
              >
                {fmtTime(lineGeom.maxT)}
              </text>
            </svg>
            {hover && (
              <div
                className="viz-tooltip"
                style={{
                  left: `min(calc(${(hover.x / lineGeom.w) * 100}% + 8px), calc(100% - 160px))`,
                  top: Math.max(0, hover.y - 8),
                }}
              >
                <strong>{hover.service}</strong>
                <br />
                {fmtTime(hover.ts)} · {(hover.value * 100).toFixed(1)}% errors
              </div>
            )}
          </div>
          <div className="viz-legend">
            {series.map((s, i) => (
              <button
                key={s.service}
                type="button"
                className={`viz-legend-item${focus === s.service ? " active" : ""}`}
                onClick={() => setFocus(focus === s.service ? null : s.service)}
              >
                <span className="swatch" style={{ background: PALETTE[i % PALETTE.length] }} />
                {s.service}
              </button>
            ))}
          </div>
        </div>
      )}

      {marks.length > 0 && (
        <div className="viz-panel viz-wide">
          <h3>Event marks</h3>
          <ul className="viz-marks">
            {marks.map((m, i) => (
              <li key={`${m.ts_ms}-${i}`}>
                <span className={`mark-kind ${m.kind}`}>{m.kind}</span>
                <span className="mono">{fmtTime(m.ts_ms)}</span> {m.label}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
