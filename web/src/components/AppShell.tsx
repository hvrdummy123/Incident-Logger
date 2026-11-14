import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { clearTokens } from "../lib/auth";
import { applyTheme, cycleTheme, readTheme, type Theme } from "../lib/theme";
import { EgressIndicator } from "./EgressIndicator";

export function AppShell({ meEmail, role }: { meEmail?: string; role?: string }) {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<Theme>(() => readTheme());
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <div className="shell">
      <aside className={`rail${collapsed ? " collapsed" : ""}`}>
        <div className="brand">
          <Link to="/incidents">TraceIQ</Link>
        </div>
        {!collapsed && (
          <nav className="nav" aria-label="Primary">
            <NavLink to="/incidents" end>
              Incidents
            </NavLink>
            <NavLink to="/incidents/new">Bring your own</NavLink>
          </nav>
        )}
        <button
          type="button"
          className="btn"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
        >
          {collapsed ? "»" : "Collapse"}
        </button>
      </aside>
      <div className="main">
        <header className="topbar">
          <span className="muted mono" title="Workspace">
            {meEmail ?? "signed in"}
            {role ? ` · ${role}` : ""}
          </span>
          <span className="badge">local</span>
          <EgressIndicator mode="none" />
          <div className="topbar-spacer" />
          <button
            type="button"
            className="btn"
            onClick={() => setTheme(cycleTheme(theme))}
            aria-label="Toggle theme"
          >
            Theme: {theme}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              clearTokens();
              navigate("/login");
            }}
          >
            Sign out
          </button>
        </header>
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
