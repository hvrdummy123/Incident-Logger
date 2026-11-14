import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Incident } from "../lib/api";
import { problemToMessage } from "../lib/errors";
import { isTypingTarget, nextIndex } from "../lib/keyboard";
import { SeverityBadge } from "../components/SeverityBadge";

const DEMOS = [
  { id: "incident-1-bad-deploy", title: "Demo 1: bad deploy" },
  { id: "incident-2-db-pool", title: "Demo 2: DB pool exhaustion" },
  { id: "incident-3-cache-stampede", title: "Demo 3: cache stampede" },
];

export function IncidentsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const searchRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api<Incident[]>("/v1/incidents"),
  });

  const createDemo = useMutation({
    mutationFn: (title: string) =>
      api<Incident>("/v1/incidents", {
        method: "POST",
        body: JSON.stringify({ title, severity: "sev2", source: "demo" }),
      }),
    onSuccess: (inc) => {
      void qc.invalidateQueries({ queryKey: ["incidents"] });
      navigate(`/incidents/${inc.id}`);
    },
    onError: (err) => setError(problemToMessage(err)),
  });

  const rows = useMemo(() => {
    const all = list.data ?? [];
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (r) =>
        r.title.toLowerCase().includes(needle) ||
        r.id.toLowerCase().includes(needle) ||
        r.status.toLowerCase().includes(needle),
    );
  }, [list.data, q]);

  useEffect(() => {
    setSelected((s) => (rows.length === 0 ? -1 : Math.min(s, rows.length - 1)));
  }, [rows.length]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isTypingTarget(e.target) && e.key !== "Escape") {
        if (e.key === "/" && document.activeElement !== searchRef.current) return;
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (e.key === "j" || e.key === "k" || e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setSelected((cur) => nextIndex(cur, e.key, rows.length));
        return;
      }
      if (e.key === "Enter" && selected >= 0 && rows[selected]) {
        navigate(`/incidents/${rows[selected]!.id}`);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, rows, selected]);

  if (list.isLoading) {
    return (
      <div>
        <h1 className="page-title">Incidents</h1>
        <div className="skeleton" style={{ width: "40%", marginBottom: 8 }} />
        <div className="skeleton" style={{ width: "100%", height: 120 }} />
      </div>
    );
  }

  if (list.isError) {
    return (
      <div>
        <h1 className="page-title">Incidents</h1>
        <div className="error-box" role="alert">
          {problemToMessage(list.error)}
          <div style={{ marginTop: 8 }}>
            <button type="button" className="btn" onClick={() => void list.refetch()}>
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if ((list.data?.length ?? 0) === 0) {
    return (
      <div>
        <h1 className="page-title">Incidents</h1>
        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}
        <div className="empty">
          <p>No incidents yet.</p>
          <p className="muted">Load a demo or bring your own logs to start.</p>
          <div className="actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={createDemo.isPending}
              onClick={() => createDemo.mutate(DEMOS[0]!.title)}
            >
              Load a demo incident
            </button>
            <button type="button" className="btn" onClick={() => navigate("/incidents/new")}>
              Bring your own logs
            </button>
          </div>
          <div style={{ marginTop: 16 }} className="muted">
            {DEMOS.map((d) => (
              <button
                key={d.id}
                type="button"
                className="btn"
                style={{ margin: 4 }}
                onClick={() => createDemo.mutate(d.title)}
              >
                {d.title}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="page-title">Incidents</h1>
      <p className="muted" style={{ marginTop: -8 }}>
        Keyboard: <kbd>j</kbd>/<kbd>k</kbd> move, <kbd>/</kbd> search, <kbd>Enter</kbd> open.
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <input
          ref={searchRef}
          placeholder="Search title, id, status…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search incidents"
          style={{
            flex: 1,
            minWidth: 180,
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "8px 10px",
            background: "var(--surface)",
          }}
        />
        <button type="button" className="btn" onClick={() => navigate("/incidents/new")}>
          Bring your own
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => createDemo.mutate(DEMOS[0]!.title)}
        >
          Load demo
        </button>
      </div>
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Title</th>
              <th>Status</th>
              <th>Source</th>
              <th>Id</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.id}
                aria-selected={i === selected}
                tabIndex={0}
                onClick={() => navigate(`/incidents/${r.id}`)}
                onFocus={() => setSelected(i)}
                style={{ cursor: "pointer" }}
              >
                <td>
                  <SeverityBadge severity={r.severity} />
                </td>
                <td>{r.title}</td>
                <td>{r.status}</td>
                <td>{r.source}</td>
                <td className="mono">{r.id.slice(0, 10)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
