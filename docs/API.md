# API narrative

Base path: `/v1`. Errors use `application/problem+json` (`AppError`).

Auth: `Authorization: Bearer <jwt>` and usually `X-Workspace-Id`. If the user has exactly one membership, the workspace header may be omitted (resolved server-side). Login returns `workspace_id` when unambiguous.

## Routes (implemented)

| Method | Path | Min role |
| --- | --- | --- |
| GET | `/healthz`, `/readyz` | public / health |
| POST | `/auth/login` | public |
| GET | `/me` | viewer |
| GET/POST | `/incidents`, `/incidents/{id}` | viewer / investigator |
| POST | `/datasets/preview` | investigator |
| POST | `/incidents/{id}/investigations` | investigator |
| GET | `/investigations/{id}` | viewer |
| GET | `/investigations/{id}/events` | viewer (SSE) |
| POST | `/investigations/{id}/cancel` | investigator |
| GET | `/reports/{id}` | viewer (`Accept` json or markdown) |
| POST | `/reports/{id}/feedback` | investigator |
| GET | `/audit`, `/egress-ledger` | admin |
| POST | `/webhooks/alerts` | API key + workspace |

OpenAPI: `GET /openapi.json` from a running API.
