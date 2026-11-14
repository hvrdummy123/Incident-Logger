import { describe, expect, it } from "vitest";
import { nextIndex } from "./keyboard";

describe("nextIndex", () => {
  it("moves with j/k", () => {
    expect(nextIndex(0, "j", 3)).toBe(1);
    expect(nextIndex(2, "j", 3)).toBe(2);
    expect(nextIndex(1, "k", 3)).toBe(0);
    expect(nextIndex(0, "k", 3)).toBe(0);
  });

  it("handles empty lists", () => {
    expect(nextIndex(0, "j", 0)).toBe(-1);
  });
});
