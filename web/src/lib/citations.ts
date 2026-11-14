export type EvidenceItem = {
  id: string;
  excerpt: string;
  lines?: string[];
  highlightIndex?: number;
};

/** Map citation ids (ev_1 or bare ids) to evidence rows. */
export function resolveCitation(
  cite: string,
  evidence: EvidenceItem[],
): EvidenceItem | undefined {
  const normalized = cite.replace(/^ev[_-]?/i, "");
  return (
    evidence.find((e) => e.id === cite) ??
    evidence.find((e) => e.id === `ev_${normalized}`) ??
    evidence.find((e) => e.id.replace(/^ev[_-]?/i, "") === normalized)
  );
}

export function formatParseSummary(report: {
  lines_read: number;
  lines_parsed: number;
  lines_unparsed: number;
  format: string;
}): string {
  const pct =
    report.lines_read === 0
      ? 0
      : Math.round((report.lines_unparsed / report.lines_read) * 1000) / 10;
  return `Read ${report.lines_read.toLocaleString()} lines as ${report.format}. Parsed ${report.lines_parsed.toLocaleString()}; ${report.lines_unparsed.toLocaleString()} unparsed (${pct}%).`;
}
