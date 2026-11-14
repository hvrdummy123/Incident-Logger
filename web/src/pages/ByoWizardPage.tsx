import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api, type DatasetPreview, type Incident } from "../lib/api";
import { formatParseSummary } from "../lib/citations";
import { problemToMessage } from "../lib/errors";

const STEPS = [
  "Files",
  "Parse report",
  "Redaction",
  "Window",
  "Start",
] as const;

export function ByoWizardPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [fileName, setFileName] = useState("");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [deterministicOnly, setDeterministicOnly] = useState(true);
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("sev3");
  const [error, setError] = useState<string | null>(null);

  const previewMut = useMutation({
    mutationFn: () =>
      api<DatasetPreview>("/v1/datasets/preview", {
        method: "POST",
        body: JSON.stringify({ text, filename: fileName || "upload.log" }),
      }),
    onSuccess: (data) => {
      setPreview(data);
      setStep(1);
      setError(null);
    },
    onError: (err) => setError(problemToMessage(err)),
  });

  const createMut = useMutation({
    mutationFn: () =>
      api<Incident>("/v1/incidents", {
        method: "POST",
        body: JSON.stringify({
          title: title || `BYO: ${fileName || "upload"}`,
          severity,
          source: "upload",
        }),
      }),
    onSuccess: (inc) => navigate(`/incidents/${inc.id}`),
    onError: (err) => setError(problemToMessage(err)),
  });

  const egressBanner = useMemo(() => {
    if (deterministicOnly) {
      return "Deterministic only is on. No model traffic will leave this machine for this run.";
    }
    return "A model may be called. Payloads are redacted before egress; secrets stay on this machine.";
  }, [deterministicOnly]);

  async function onFile(file: File | null) {
    setError(null);
    if (!file) return;
    if (file.size > 2_000_000) {
      setError("File is larger than 2 MB for preview. Split it or use the CLI ingest path.");
      return;
    }
    const buf = await file.arrayBuffer();
    const bytes = new Uint8Array(buf);
    if (bytes.slice(0, 4096).includes(0)) {
      setError("Couldn’t read that file as text (null bytes). Try a plain log, not a binary.");
      return;
    }
    const decoded = new TextDecoder("utf-8", { fatal: false }).decode(bytes);
    setFileName(file.name);
    setText(decoded);
    if (!title) setTitle(`BYO: ${file.name}`);
  }

  return (
    <div>
      <h1 className="page-title">Bring your own logs</h1>
      <div className="banner" role="status">
        {egressBanner}
      </div>
      <div className="wizard-steps" aria-label="Wizard steps">
        {STEPS.map((label, i) => (
          <span key={label} className={i === step ? "active" : undefined}>
            {i + 1}. {label}
          </span>
        ))}
      </div>
      {error && (
        <div className="error-box" role="alert" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {step === 0 && (
        <section className="pane">
          <h2>Choose files</h2>
          <div className="pane-body">
            <label className="field">
              Log file
              <input
                type="file"
                accept=".log,.txt,.jsonl,.json,text/*"
                onChange={(e) => void onFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <p className="muted">
              Drop a text log. Binary junk is rejected with a readable error. Preview stays under 2
              MB in the browser.
            </p>
            {fileName && (
              <p>
                Selected <span className="mono">{fileName}</span> ({text.length.toLocaleString()}{" "}
                chars).
              </p>
            )}
            <button
              type="button"
              className="btn btn-primary"
              disabled={!text || previewMut.isPending}
              onClick={() => previewMut.mutate()}
            >
              {previewMut.isPending ? "Parsing…" : "Continue to parse report"}
            </button>
          </div>
        </section>
      )}

      {step === 1 && preview && (
        <section className="pane">
          <h2>Parse report</h2>
          <div className="pane-body">
            <p>{formatParseSummary(preview.parse_report)}</p>
            <p className="muted">
              Detected {preview.detected_format} (confidence{" "}
              {(preview.detect_confidence * 100).toFixed(0)}%). TZ assumed{" "}
              {preview.parse_report.timezone_assumption}.
            </p>
            <p>
              Services:{" "}
              {preview.parse_report.services.length
                ? preview.parse_report.services.join(", ")
                : "none detected"}
            </p>
            {preview.parse_report.out_of_order > 0 && (
              <p style={{ color: "var(--signal)" }}>
                {preview.parse_report.out_of_order} out-of-order timestamps — check clock skew.
              </p>
            )}
            {preview.parse_report.unparsed_examples.length > 0 && (
              <>
                <p>Unparsed examples:</p>
                <pre className="mono">
                  {preview.parse_report.unparsed_examples.slice(0, 5).join("\n")}
                </pre>
              </>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button type="button" className="btn" onClick={() => setStep(0)}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setStep(2)}>
                Continue
              </button>
            </div>
          </div>
        </section>
      )}

      {step === 2 && preview && (
        <section className="pane">
          <h2>Redaction preview</h2>
          <div className="pane-body">
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
              <input
                type="checkbox"
                checked={deterministicOnly}
                onChange={(e) => setDeterministicOnly(e.target.checked)}
              />
              Deterministic only, no model
            </label>
            <p>
              Findings:{" "}
              {Object.entries(preview.redaction.stats)
                .map(([k, v]) => `${k}=${v}`)
                .join(", ") || "none"}
            </p>
            <ul>
              {preview.redaction.examples.map((ex, i) => (
                <li key={i} className="mono">
                  {ex.kind}: {ex.sample} → {ex.placeholder || "(placeholder)"}
                </li>
              ))}
            </ul>
            <p className="muted">Redacted preview (truncated):</p>
            <pre className="mono">{preview.redaction.redacted_preview}</pre>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button type="button" className="btn" onClick={() => setStep(1)}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setStep(3)}>
                Continue
              </button>
            </div>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="pane">
          <h2>Window and severity</h2>
          <div className="pane-body">
            <label className="field">
              Title
              <input value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="field">
              Severity
              <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                <option value="sev1">sev1</option>
                <option value="sev2">sev2</option>
                <option value="sev3">sev3</option>
                <option value="sev4">sev4</option>
              </select>
            </label>
            <p className="muted">
              Full window pickers land with dataset persistence. For now the incident is opened with
              the uploaded source tag; use CLI ingest for parquet materialization.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn" onClick={() => setStep(2)}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={() => setStep(4)}>
                Continue
              </button>
            </div>
          </div>
        </section>
      )}

      {step === 4 && (
        <section className="pane">
          <h2>Start</h2>
          <div className="pane-body">
            <p>
              Create incident <strong>{title || fileName}</strong> ({severity}) from{" "}
              <span className="mono">{fileName || "upload"}</span>.
            </p>
            <p className="muted">{egressBanner}</p>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn" onClick={() => setStep(3)}>
                Back
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={createMut.isPending}
                onClick={() => createMut.mutate()}
              >
                {createMut.isPending ? "Creating…" : "Create incident"}
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
