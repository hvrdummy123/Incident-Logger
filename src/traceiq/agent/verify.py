"""Machine-check report citations and basic claim support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from traceiq.agent.schema import Report


@dataclass
class VerifyIssue:
    code: str
    detail: str


@dataclass
class VerifyResult:
    passed: bool
    issues: list[VerifyIssue] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)


def verify_report(
    report: Report,
    *,
    evidence_ids: set[str],
    known_services: set[str] | None = None,
) -> VerifyResult:
    issues: list[VerifyIssue] = []
    unverified: list[str] = []
    known_services = known_services or set()

    def check_ids(ids: list[str], ctx: str) -> None:
        for eid in ids:
            if eid not in evidence_ids:
                issues.append(VerifyIssue("missing_evidence", f"{ctx}: {eid}"))

    for s in report.impact.symptoms:
        if not s.evidence:
            unverified.append(s.text)
        check_ids(s.evidence, "impact.symptom")
    for t in report.timeline:
        check_ids(t.evidence, "timeline")
    for f in report.contributing_factors:
        if not f.evidence:
            unverified.append(f.text)
        check_ids(f.evidence, "contributing")
    for r in report.ruled_out:
        check_ids(r.evidence, "ruled_out")

    if report.outcome == "root_cause_found":
        if not report.root_cause.evidence:
            issues.append(VerifyIssue("root_cause_no_evidence", "root cause lacks evidence ids"))
            report.outcome = "abstained"
        else:
            check_ids(report.root_cause.evidence, "root_cause")
        if (
            report.root_cause.service
            and known_services
            and report.root_cause.service not in known_services
        ):
            issues.append(
                VerifyIssue(
                    "root_cause_unknown_service",
                    f"service {report.root_cause.service} not in known services",
                )
            )
        # every cited evidence must exist
        if any(i.code == "missing_evidence" and i.detail.startswith("root_cause") for i in issues):
            report.outcome = "abstained"
            issues.append(VerifyIssue("forced_abstain", "unverifiable root cause"))

    passed = not any(
        i.code
        in {
            "missing_evidence",
            "root_cause_no_evidence",
            "root_cause_unknown_service",
            "forced_abstain",
        }
        for i in issues
    )
    return VerifyResult(passed=passed, issues=issues, unverified=unverified)


def mutate_for_test(report: Report, kind: str) -> Report:
    """Used by mutation tests — returns a copy with one intentional flaw."""
    data: dict[str, Any] = report.model_dump()
    if kind == "swap_evidence":
        data["root_cause"]["evidence"] = ["ev_DOES_NOT_EXIST"]
        data["outcome"] = "root_cause_found"
    elif kind == "bad_service":
        data["root_cause"]["service"] = "not-a-real-service"
        data["outcome"] = "root_cause_found"
        data["root_cause"]["evidence"] = data["root_cause"]["evidence"] or ["ev_x"]
    elif kind == "unsupported_claim":
        data["contributing_factors"].append({"text": "unsupported claim", "evidence": []})
    return Report.model_validate(data)
