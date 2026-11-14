export function EgressIndicator({
  mode = "none",
}: {
  mode?: "none" | "redacted" | "unknown";
}) {
  if (mode === "none") {
    return (
      <span className="badge" style={{ color: "var(--ok)" }} title="No model traffic leaves this machine">
        <span className="dot" aria-hidden />
        No external LLM
      </span>
    );
  }
  if (mode === "redacted") {
    return (
      <span className="badge" style={{ color: "var(--signal)" }} title="Outbound model calls are redacted">
        <span className="dot" aria-hidden />
        External model: redacted
      </span>
    );
  }
  return (
    <span className="badge" title="Egress mode unknown">
      <span className="dot" aria-hidden />
      Egress unknown
    </span>
  );
}
