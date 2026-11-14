import { describe, expect, it } from "vitest";
import { formatParseSummary, resolveCitation } from "./citations";

describe("resolveCitation", () => {
  const evidence = [
    { id: "ev_1", excerpt: "line a" },
    { id: "ev_2", excerpt: "line b" },
  ];

  it("maps chips to evidence", () => {
    expect(resolveCitation("ev_1", evidence)?.excerpt).toBe("line a");
    expect(resolveCitation("1", evidence)?.id).toBe("ev_1");
    expect(resolveCitation("ev_9", evidence)).toBeUndefined();
  });
});

describe("formatParseSummary", () => {
  it("states unparsed counts plainly", () => {
    const msg = formatParseSummary({
      lines_read: 1000,
      lines_parsed: 950,
      lines_unparsed: 50,
      format: "jsonl",
    });
    expect(msg).toContain("1,000");
    expect(msg).toContain("50 unparsed");
    expect(msg).toContain("jsonl");
  });
});
