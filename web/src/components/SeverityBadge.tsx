const COLORS: Record<string, string> = {
  sev1: "var(--sev1)",
  sev2: "var(--sev2)",
  sev3: "var(--sev3)",
  sev4: "var(--sev4)",
};

export function SeverityBadge({ severity }: { severity: string }) {
  const key = severity.toLowerCase();
  const color = COLORS[key] ?? "var(--muted)";
  return (
    <span className="badge" style={{ color }} title={severity}>
      <span className="dot" aria-hidden />
      <span>{severity}</span>
    </span>
  );
}
