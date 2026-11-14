import { clearTokens, getAccessToken, getWorkspaceId, setWorkspaceId } from "./auth";
import type { Problem } from "./errors";

const BASE = "";

async function parseBody(res: Response): Promise<unknown> {
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json") || ct.includes("application/problem+json")) {
    return res.json();
  }
  return res.text();
}

export class ApiError extends Error {
  status: number;
  problem: Problem;

  constructor(status: number, problem: Problem) {
    super(problem.detail ?? problem.title);
    this.status = status;
    this.problem = problem;
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const wid = getWorkspaceId();
  if (wid && !headers.has("X-Workspace-Id")) {
    headers.set("X-Workspace-Id", wid);
  }

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  const body = await parseBody(res);

  if (res.status === 401) {
    clearTokens();
  }

  if (!res.ok) {
    const problem =
      body && typeof body === "object"
        ? (body as Problem)
        : { title: "Request failed", detail: String(body) };
    throw new ApiError(res.status, {
      title: problem.title ?? "Request failed",
      detail: problem.detail,
      status: res.status,
    });
  }

  // Persist workspace from /me when present
  if (
    path === "/v1/me" &&
    body &&
    typeof body === "object" &&
    "workspace_id" in body &&
    typeof (body as { workspace_id: unknown }).workspace_id === "string"
  ) {
    setWorkspaceId((body as { workspace_id: string }).workspace_id);
  }

  return body as T;
}

export type Incident = {
  id: string;
  title: string;
  severity: string;
  status: string;
  source: string;
};

export type Me = {
  user_id: string;
  email: string;
  workspace_id: string;
  role: string;
};

export type ParseReport = {
  lines_read: number;
  lines_parsed: number;
  lines_unparsed: number;
  format: string;
  detect_confidence: number;
  unparsed_examples: string[];
  services: string[];
  level_counts: Record<string, number>;
  ts_min_ms: number | null;
  ts_max_ms: number | null;
  timezone_assumption: string;
  out_of_order: number;
};

export type RedactionPreview = {
  stats: Record<string, number>;
  examples: Array<{ kind: string; placeholder: string; sample: string }>;
  redacted_preview: string;
};

export type DatasetPreview = {
  filename: string;
  detected_format: string;
  detect_confidence: number;
  parse_report: ParseReport;
  redaction: RedactionPreview;
};

export type Investigation = {
  id: string;
  incident_id: string;
  status: string;
  model: string;
  outcome: string | null;
  spent_usd: number | null;
  report_id: string | null;
  steps?: number;
};

export type ReportPayload = {
  id: string;
  investigation_id: string;
  json: Record<string, unknown>;
  verification: { passed?: boolean; issues?: Array<{ code: string; detail: string }> } | null;
};
