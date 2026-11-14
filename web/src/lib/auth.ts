const ACCESS = "traceiq.access";
const REFRESH = "traceiq.refresh";
const WORKSPACE = "traceiq.workspace";

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(ACCESS);
  } catch {
    return null;
  }
}

export function getWorkspaceId(): string | null {
  try {
    return localStorage.getItem(WORKSPACE);
  } catch {
    return null;
  }
}

export function setWorkspaceId(workspaceId: string): void {
  try {
    localStorage.setItem(WORKSPACE, workspaceId);
  } catch {
    /* ignore */
  }
}

export function setTokens(access: string, refresh?: string): void {
  try {
    localStorage.setItem(ACCESS, access);
    if (refresh) localStorage.setItem(REFRESH, refresh);
  } catch {
    /* ignore */
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
    localStorage.removeItem(WORKSPACE);
  } catch {
    /* ignore */
  }
}

export function isLoggedIn(): boolean {
  return Boolean(getAccessToken());
}
