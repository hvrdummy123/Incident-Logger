"""SQLAlchemy models for TraceIQ metadata (Postgres)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # viewer|investigator|admin


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[str] = mapped_column(String(200), default="webhook")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("workspace_id", "content_hash"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), default="sev3")
    status: Mapped[str] = mapped_column(String(32), default="open")
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dataset_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(String(32), default="upload")  # upload|webhook|demo
    created_by: Mapped[str | None] = mapped_column(String(26))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    incident_id: Mapped[str] = mapped_column(String(26), ForeignKey("incidents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    agent_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(String(120), default="mock:mock-v1")
    budget_usd: Mapped[float] = mapped_column(Float, default=0.5)
    spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(64))


class InvestigationStep(Base):
    __tablename__ = "investigation_steps"
    __table_args__ = (UniqueConstraint("investigation_id", "seq"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("investigations.id"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # llm|tool|state
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    args_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result_ref: Mapped[str | None] = mapped_column(String(200))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # ev_<ulid>
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    investigation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("investigations.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(String(26))
    ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("investigations.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    investigation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("investigations.id"), nullable=False
    )
    json_body: Mapped[dict[str, Any]] = mapped_column("json", JSONB, default=dict)
    markdown: Mapped[str] = mapped_column(Text, default="")
    verification_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    report_id: Mapped[str] = mapped_column(String(26), ForeignKey("reports.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    true_root_cause: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[str | None] = mapped_column(String(26))


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_run_at_status", "run_at", "status"),
        Index("ix_jobs_locked_until", "locked_until"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(String(26))
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|running|done|dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_by: Mapped[str | None] = mapped_column(String(64))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (UniqueConstraint("workspace_id", "seq"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target: Mapped[str] = mapped_column(String(200), default="")
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ModelCall(Base):
    """Egress ledger — every outbound model call."""

    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), nullable=False
    )
    investigation_id: Mapped[str | None] = mapped_column(String(26))
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    redaction_stats_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RedactionMap(Base):
    __tablename__ = "redaction_maps"
    __table_args__ = (UniqueConstraint("investigation_id", "placeholder"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("investigations.id"), nullable=False
    )
    placeholder: Mapped[str] = mapped_column(String(64), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
