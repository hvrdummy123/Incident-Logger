import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Incident, type Investigation } from "../lib/api";
import { problemToMessage } from "../lib/errors";
import { SeverityBadge } from "../components/SeverityBadge";

export function IncidentDetailPage() {
  const { incidentId = "" } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const incident = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => api<Incident>(`/v1/incidents/${incidentId}`),
    enabled: Boolean(incidentId),
  });

  const start = useMutation({
    mutationFn: () =>
      api<Investigation>(`/v1/incidents/${incidentId}/investigations`, {
        method: "POST",
      }),
    onSuccess: (inv) => navigate(`/investigations/${inv.id}`),
    onError: (err) => setError(problemToMessage(err)),
  });

  if (incident.isLoading) {
    return <div className="skeleton" style={{ height: 80 }} />;
  }
  if (incident.isError || !incident.data) {
    return (
      <div className="error-box" role="alert">
        {problemToMessage(incident.error ?? "Incident not found")}
        <div style={{ marginTop: 8 }}>
          <Link to="/incidents">Back to incidents</Link>
        </div>
      </div>
    );
  }

  const inc = incident.data;
  return (
    <div>
      <p className="muted">
        <Link to="/incidents">Incidents</Link> / {inc.id.slice(0, 10)}…
      </p>
      <h1 className="page-title">{inc.title}</h1>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
        <SeverityBadge severity={inc.severity} />
        <span className="badge">{inc.status}</span>
        <span className="badge">{inc.source}</span>
      </div>
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
      <button
        type="button"
        className="btn btn-primary"
        disabled={start.isPending}
        onClick={() => start.mutate()}
      >
        {start.isPending ? "Starting…" : "Run investigation (mock)"}
      </button>
    </div>
  );
}
