import type { EvidenceItem } from "../lib/citations";

export function EvidenceDrawer({
  open,
  evidence,
  onClose,
}: {
  open: boolean;
  evidence: EvidenceItem | null;
  onClose: () => void;
}) {
  if (!open || !evidence) return null;
  const lines = evidence.lines ?? evidence.excerpt.split("\n");
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden />
      <aside className="drawer" role="dialog" aria-label="Evidence">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
          <strong className="mono">{evidence.id}</strong>
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          Cited region is highlighted. Log text is rendered inertly.
        </p>
        <pre className="mono" style={{ marginTop: 12 }}>
          {lines.map((line, i) => (
            <div
              key={i}
              className={i === (evidence.highlightIndex ?? 0) ? "highlight-line" : undefined}
            >
              {line || " "}
            </div>
          ))}
        </pre>
      </aside>
    </>
  );
}
