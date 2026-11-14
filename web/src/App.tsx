import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "./components/AppShell";
import { api, type Me } from "./lib/api";
import { isLoggedIn } from "./lib/auth";
import { ByoWizardPage } from "./pages/ByoWizardPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { InvestigationPage } from "./pages/InvestigationPage";
import { LoginPage } from "./pages/LoginPage";
import { ReportPage } from "./pages/ReportPage";

function RequireAuth({ children }: { children: ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return children;
}

function AuthedShell() {
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/v1/me"),
    retry: false,
  });
  return <AppShell meEmail={me.data?.email} role={me.data?.role} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AuthedShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/incidents" replace />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/incidents/new" element={<ByoWizardPage />} />
        <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
        <Route path="/investigations/:investigationId" element={<InvestigationPage />} />
        <Route path="/reports/:reportId" element={<ReportPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/incidents" replace />} />
    </Routes>
  );
}
