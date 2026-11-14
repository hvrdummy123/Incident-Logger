import { describe, expect, it } from "vitest";
import { layoutServiceGraph } from "./graphLayout";

describe("layoutServiceGraph", () => {
  it("layers a small DAG deterministically", () => {
    const a = layoutServiceGraph(
      [
        { id: "a", score: 0.1 },
        { id: "b", score: 0.9 },
        { id: "c", score: 0.2 },
      ],
      [
        { from: "a", to: "b" },
        { from: "b", to: "c" },
      ],
      300,
      150,
    );
    const b = layoutServiceGraph(
      [
        { id: "c", score: 0.2 },
        { id: "a", score: 0.1 },
        { id: "b", score: 0.9 },
      ],
      [
        { from: "b", to: "c" },
        { from: "a", to: "b" },
      ],
      300,
      150,
    );
    expect(a.nodes.map((n) => [n.id, n.layer, n.x, n.y])).toEqual(
      b.nodes.map((n) => [n.id, n.layer, n.x, n.y]),
    );
    expect(a.nodes.find((n) => n.id === "a")!.layer).toBe(0);
    expect(a.nodes.find((n) => n.id === "c")!.layer).toBe(2);
  });
});
