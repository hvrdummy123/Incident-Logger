export type GraphNode = { id: string; score?: number };
export type GraphEdge = { from: string; to: string; weight?: number };

export type LaidOutNode = GraphNode & { x: number; y: number; layer: number };
export type LaidOutEdge = GraphEdge & {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

/** Deterministic layered layout from a DAG (Kahn layers; stable id sort). */
export function layoutServiceGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width = 400,
  height = 240,
): { nodes: LaidOutNode[]; edges: LaidOutEdge[] } {
  const ids = [...nodes.map((n) => n.id)].sort();
  const idSet = new Set(ids);
  const indeg = new Map(ids.map((id) => [id, 0]));
  const outs = new Map(ids.map((id) => [id, [] as string[]]));

  for (const e of edges) {
    if (!idSet.has(e.from) || !idSet.has(e.to)) continue;
    outs.get(e.from)!.push(e.to);
    indeg.set(e.to, (indeg.get(e.to) ?? 0) + 1);
  }
  for (const id of ids) outs.get(id)!.sort();

  const layer = new Map<string, number>();
  const queue = ids.filter((id) => (indeg.get(id) ?? 0) === 0).sort();
  let head = 0;
  while (head < queue.length) {
    const id = queue[head++]!;
    const L = layer.get(id) ?? 0;
    for (const nxt of outs.get(id) ?? []) {
      layer.set(nxt, Math.max(layer.get(nxt) ?? 0, L + 1));
      const d = (indeg.get(nxt) ?? 1) - 1;
      indeg.set(nxt, d);
      if (d === 0) queue.push(nxt);
    }
    if (!layer.has(id)) layer.set(id, 0);
  }
  for (const id of ids) if (!layer.has(id)) layer.set(id, 0);

  const byLayer = new Map<number, string[]>();
  for (const id of ids) {
    const L = layer.get(id)!;
    const list = byLayer.get(L) ?? [];
    list.push(id);
    byLayer.set(L, list);
  }
  const maxLayer = Math.max(0, ...byLayer.keys());
  const pos = new Map<string, { x: number; y: number }>();
  for (let L = 0; L <= maxLayer; L++) {
    const row = (byLayer.get(L) ?? []).sort();
    row.forEach((id, i) => {
      const x = ((L + 0.5) / (maxLayer + 1)) * width;
      const y = ((i + 0.5) / Math.max(1, row.length)) * height;
      pos.set(id, { x, y });
    });
  }

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  const laidNodes: LaidOutNode[] = ids.map((id) => ({
    ...nodeById.get(id)!,
    id,
    layer: layer.get(id)!,
    x: pos.get(id)!.x,
    y: pos.get(id)!.y,
  }));

  const laidEdges: LaidOutEdge[] = edges
    .filter((e) => pos.has(e.from) && pos.has(e.to))
    .map((e) => ({
      ...e,
      x1: pos.get(e.from)!.x,
      y1: pos.get(e.from)!.y,
      x2: pos.get(e.to)!.x,
      y2: pos.get(e.to)!.y,
    }));

  return { nodes: laidNodes, edges: laidEdges };
}
