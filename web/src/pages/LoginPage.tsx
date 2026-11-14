import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { setTokens, setWorkspaceId } from "../lib/auth";
import { problemToMessage } from "../lib/errors";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const tokens = await api<{
        access_token: string;
        refresh_token?: string;
        workspace_id?: string;
      }>("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      if (tokens.workspace_id) setWorkspaceId(tokens.workspace_id);
      navigate("/incidents");
    } catch (err) {
      setError(problemToMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="brand" style={{ marginBottom: 8 }}>
          TraceIQ
        </div>
        <p className="muted" style={{ marginTop: 0 }}>
          Sign in to investigate incidents in your workspace.
        </p>
        <label className="field">
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}
        <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
