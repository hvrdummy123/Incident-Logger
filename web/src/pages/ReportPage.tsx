import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type ReportPayload } from "../lib/api";
import { resolveCitation, type EvidenceItem } from "../lib/citations";
import { problemToMessage } from "../lib/errors";
import { EvidenceDrawer } from "../components/EvidenceDrawer";

type ReportJson = {
  summary?: string;
  outcome?: string;
  confidence?: number;
  impact?: { services?: string[]; symptoms?: Array<{ text: string; evidence?: string[] }> };
  timeline?: Array<{ ts: string; text: string; evidence?: string[] }>;
  root_cause?: {
    service?: string;
    category?: string;
    explanation?: string;
    evidence?: string[];
  };
  contributing_factors?: Array<{ text: string; evidence?: string[] }>;
  ruled_out?: Array<{ hypothesis: string; why: string; evidence?: string[] }>;
  suggested_actions?: Array<{ text: string; type?: string; risk?: string }>;
  data_gaps?: string[];
  open_questions?: string[];
  contributing_factors?: Array<{ text: string; evidence?: string[] }>;
  run?: { model?: string; cost_usd?: number; deterministic_only?: boolean; steps?: number };
};

function Citations({
  ids,
  onOpen,
}: {
  ids?: string[];
  onOpen: (id: string) => void;
}) {
  if (!ids?.length) return null;
  return (
    <>
      {ids.map((id) => (
        <button key={id} type="button" className="cite" onClick={() => onOpen(id)} title={id}>
          {id.replace(/^ev[_-]?/i, "") || id}
        </button>
      ))}
    </>
  );
}

export function ReportPage() {
  const { reportId = "" } = useParams();
  const [drawer, setDrawer] = useState<EvidenceItem | null>(null);
  const [verdict, setVerdict] = useState<"correct" | "partially" | "wrong">("correct");
  const [trueCause, setTrueCause] = useState("");
  const [notes, setNotes] = useState("");
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const report = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => api<ReportPayload>(`/v1/reports/${reportId}`),
    enabled: Boolean(reportId),
  });

  const evidenceIndex = useMemo(() => {
    const body = (report.data?.json ?? {}) as ReportJson;
    const ids = new Set<string>();
    const collect = (list?: string[]) => list?.forEach((id) => ids.add(id));
    collect(body.root_cause?.evidence);
    body.timeline?.forEach((t) => collect(t.evidence));
    body.ruled_out?.forEach((r) => collect(r.evidence));
    body.contributing_factors?.forEach((f) => collect(f.evidence));
    return [...ids].map(
      (id): EvidenceItem => ({
        id,
        excerpt: `Evidence ${id}\n(line excerpt unavailable until evidence API is wired)`,
        lines: [
          `Evidence ${id}`,
          "(line excerpt unavailable until evidence API is wired)",
          "Cited region would highlight here.",
        ],
        highlightIndex: 2,
      }),
    );
  }, [report.data]);

  const feedback = useMutation({
    mutationFn: () =>
      api(`/v1/reports/${reportId}/feedback`, {
        method: "POST",
        body: JSON.stringify({
          verdict,
          true_root_cause: trueCause || null,
          notes,
        }),
      }),
    onSuccess: () => setFeedbackMsg("Feedback recorded."),
    onError: (err) => setFeedbackMsg(problemToMessage(err)),
  });

  function openCite(id: string) {
    setDrawer(resolveCitation(id, evidenceIndex) ?? {
      id,
      excerpt: id,
      lines: [id],
      highlightIndex: 0,
    });
  }

  async function exportMarkdown() {
    const token = localStorage.getItem("traceiq.access");
    const wid = localStorage.getItem("traceiq.workspace");
    const res = await fetch(`/v1/reports/${reportId}`, {
      headers: {
        Accept: "text/markdown",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(wid ? { "X-Workspace-Id": wid } : {}),
      },
    });
    const text = await res.text();
    const blob = new Blob([text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `traceiq-report-${reportId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (report.isLoading) return <div className="skeleton" style={{ height: 200 }} />;
  if (report.isError || !report.data) {
    return (
      <div className="error-box" role="alert">
        {problemToMessage(report.error ?? "Report not found")}
      </div>
    );
  }

  const body = report.data.json as ReportJson;
  const unverified =
    report.data.verification && report.data.verification.passed === false
      ? report.data.verification.issues ?? []
      : [];

  return (
    <article className="report">
      <p className="muted">
        <Link to={`/investigations/${report.data.investigation_id}`}>Investigation</Link>
      </p>
      <h1>Investigation report</h1>
      <p>{body.summary}</p>
      <p className="muted">
        Outcome: {body.outcome ?? "—"} · confidence{" "}
        {body.confidence != null ? body.confidence.toFixed(2) : "—"}
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <button type="button" className="btn" onClick={() => void exportMarkdown()}>
          Export Markdown
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => window.print()}
        >
          Print
        </button>
      </div>

      {unverified.length > 0 && (
        <section className="unverified">
          <h2>Unverified claims</h2>
          <ul>
            {unverified.map((i, idx) => (
              <li key={idx}>
                {i.code}: {i.detail}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2>Impact</h2>
        <p>Services: {(body.impact?.services ?? []).join(", ") || "—"}</p>
        <ul>
          {(body.impact?.symptoms ?? []).map((s, i) => (
            <li key={i}>
              {s.text}
              <Citations ids={s.evidence} onOpen={openCite} />
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Timeline</h2>
        <ul>
          {(body.timeline ?? []).map((t, i) => (
            <li key={i}>
              <span className="mono">{t.ts}</span> — {t.text}
              <Citations ids={t.evidence} onOpen={openCite} />
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Root cause</h2>
        <p>
          <strong>{body.root_cause?.service || "—"}</strong>
          {body.root_cause?.category ? ` · ${body.root_cause.category}` : ""}
        </p>
        <p>
          {body.root_cause?.explanation}
          <Citations ids={body.root_cause?.evidence} onOpen={openCite} />
        </p>
      </section>

      <section>
        <h2>Contributing factors</h2>
        <ul>
          {(body.contributing_factors ?? []).map((f, i) => (
            <li key={i}>
              {f.text}
              <Citations ids={f.evidence} onOpen={openCite} />
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Ruled out</h2>
        <ul>
          {(body.ruled_out ?? []).map((r, i) => (
            <li key={i}>
              <strong>{r.hypothesis}</strong> — {r.why}
              <Citations ids={r.evidence} onOpen={openCite} />
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Suggested actions</h2>
        <p className="muted">Suggestions only — validate before acting.</p>
        <ul>
          {(body.suggested_actions ?? []).map((a, i) => (
            <li key={i}>
              [{a.type ?? "follow_up"} · {a.risk ?? "low"}] {a.text}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Data gaps</h2>
        <ul>
          {(body.data_gaps ?? []).map((g, i) => (
            <li key={i}>{g}</li>
          ))}
        </ul>
      </section>

      <section>
        <h2>What would sharpen this</h2>
        <p className="muted">
          Real outages are messy. TraceIQ will still summarize from partial logs — send more of
          this if you have it.
        </p>
        <ul>
          {(body.open_questions ?? []).map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Run details</h2>
        <p className="mono">
          model={body.run?.model ?? "—"} steps={body.run?.steps ?? "—"} cost_usd=
          {body.run?.cost_usd ?? "—"} deterministic_only=
          {String(body.run?.deterministic_only ?? false)}
        </p>
      </section>

      <section>
        <h2>Feedback</h2>
        <label className="field">
          Verdict
          <select
            value={verdict}
            onChange={(e) => setVerdict(e.target.value as typeof verdict)}
          >
            <option value="correct">correct</option>
            <option value="partially">partially</option>
            <option value="wrong">wrong</option>
          </select>
        </label>
        <label className="field">
          True root cause
          <input value={trueCause} onChange={(e) => setTrueCause(e.target.value)} />
        </label>
        <label className="field">
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
        </label>
        <button
          type="button"
          className="btn btn-primary"
          disabled={feedback.isPending}
          onClick={() => feedback.mutate()}
        >
          Submit feedback
        </button>
        {feedbackMsg && <p role="status">{feedbackMsg}</p>}
      </section>

      <EvidenceDrawer open={Boolean(drawer)} evidence={drawer} onClose={() => setDrawer(null)} />
    </article>
  );
}
