"""Evidence provenance and score-integrity validation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .scoring import RUBRIC


_KNOWN_SOURCE_TYPES = {
    "static_analysis",
    "browser",
    "scenario",
    "git_analysis",
    "readme",
    "presentation",
}
_INSUFFICIENT_MARKERS = ("근거 부족", "근거 없음", "확인 안 됨", "insufficient")
_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class EvidenceRecord:
    """A resolved evidence reference and its rubric applicability."""

    evidence_id: str
    source_type: str
    criterion_candidates: frozenset[str]
    available: bool = True


def _finding(
    code: str,
    severity: str,
    message: str,
    location: str,
    criterion: str | None = None,
    references: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "criterion": criterion,
        "location": location,
        "message": message,
        "references": sorted(set(references or [])),
    }


def _reference_value(reference: Any) -> str:
    if isinstance(reference, str):
        return reference.strip()
    if not isinstance(reference, dict):
        return ""
    if reference.get("type") == "ai_reference":
        return str(reference.get("value", "")).strip()
    if reference.get("type") == "code":
        category = str(reference.get("category", "")).strip()
        line = str(reference.get("line", "")).strip()
        return f"static_analysis.matches.{category}[{line}]" if category else ""
    if reference.get("type") == "browser":
        return f"browser.steps[{reference.get('step', '')}]"
    if reference.get("type") == "scenario":
        return "submission.scenario"
    if reference.get("type") == "git":
        return "git_analysis.authors"
    return str(reference.get("reference", reference.get("id", reference.get("value", "")))).strip()


def _source_for_reference(reference: str) -> str:
    if reference.startswith("static_analysis."):
        return "static_analysis"
    if reference.startswith("browser."):
        return "browser"
    if reference == "submission.scenario":
        return "scenario"
    if reference.startswith("git_analysis."):
        return "git_analysis"
    return "unknown"


def _criteria_for_static_category(category: str) -> set[str]:
    if category in {"agent_orchestration", "tools", "rag", "multi_agent"}:
        return {"ai_implementation"}
    if category in {"golden_dataset", "eval_metric", "eval_signal"}:
        return {"operational_quality"}
    return set(RUBRIC)


def _criteria_for_reference(reference: str) -> set[str]:
    if reference == "submission.scenario":
        return {"problem_wow"}
    if reference.startswith("browser."):
        return {"problem_wow", "completeness"}
    if reference == "git_analysis.authors":
        return {"presentation_collaboration"}
    if reference.startswith("static_analysis.matches."):
        category = reference.split(".", 3)[2].split("[", 1)[0]
        return _criteria_for_static_category(category)
    return set()


def _add_record(index: dict[str, EvidenceRecord], record: EvidenceRecord) -> None:
    if record.evidence_id:
        index[record.evidence_id] = record


def _normalized_index(evidence: Any) -> dict[str, EvidenceRecord]:
    index: dict[str, EvidenceRecord] = {}
    if not isinstance(evidence, list):
        return index
    for item in evidence:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("id", item.get("evidence_id", item.get("reference", "")))).strip()
        if not evidence_id:
            continue
        source_type = str(item.get("source_type", item.get("source", "unknown"))).strip()
        candidates = item.get("criterion_candidates", item.get("criteria", []))
        if isinstance(candidates, str):
            candidates = [candidates]
        criteria = frozenset(str(value) for value in candidates if str(value) in RUBRIC)
        if not criteria:
            criteria = frozenset(_criteria_for_reference(evidence_id))
        _add_record(index, EvidenceRecord(evidence_id, source_type, criteria, bool(item.get("available", True))))
    return index


def _artifact_index(data: Any) -> dict[str, EvidenceRecord]:
    """Index references from either raw pipeline data or normalized evidence."""
    if isinstance(data, list):
        return _normalized_index(data)
    if not isinstance(data, dict):
        return {}
    index = _normalized_index(data.get("evidence"))
    submission = data.get("submission") or {}
    if submission.get("scenario"):
        _add_record(index, EvidenceRecord("submission.scenario", "scenario", frozenset({"problem_wow"})))

    static = data.get("static_analysis") or {}
    matches = static.get("matches") or {}
    for category, values in matches.items():
        if not isinstance(values, list):
            continue
        candidates = frozenset(_criteria_for_static_category(str(category)))
        for position, value in enumerate(values):
            if not isinstance(value, dict):
                value = {"text": value}
            line = str(value.get("line", position)).strip()
            base = f"static_analysis.matches.{category}"
            record = EvidenceRecord(f"{base}[{position}]", "static_analysis", candidates)
            _add_record(index, record)
            if line != str(position):
                _add_record(index, EvidenceRecord(f"{base}[{line}]", "static_analysis", candidates))

    browser = data.get("browser") or {}
    for position, step in enumerate(browser.get("steps", []) or []):
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("step", position)).strip()
        record = EvidenceRecord(f"browser.steps[{position}]", "browser", frozenset({"problem_wow", "completeness"}))
        _add_record(index, record)
        if step_id != str(position):
            _add_record(index, EvidenceRecord(f"browser.steps[{step_id}]", "browser", record.criterion_candidates))

    git = data.get("git_analysis") or {}
    if git.get("authors"):
        _add_record(index, EvidenceRecord("git_analysis.authors", "git_analysis", frozenset({"presentation_collaboration"})))
    return index


def _records_for_references(item: dict[str, Any]) -> list[str]:
    values = []
    for key in ("evidence_ids", "evidence_references"):
        raw = item.get(key, []) or []
        values.extend(raw if isinstance(raw, list) else [raw])
    raw_references = item.get("references", []) or []
    values.extend(raw_references if isinstance(raw_references, list) else [raw_references])
    return sorted({value for value in (_reference_value(raw) for raw in values) if value})


def _as_records(value: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get(key, [])
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _exception_allows(reference: str, criterion: str, exceptions: list[dict[str, Any]]) -> bool:
    for exception in exceptions:
        if not isinstance(exception, dict) or not exception.get("approved"):
            continue
        raw_exception_refs = exception.get("evidence_ids", exception.get("references", [])) or []
        if exception.get("evidence_id"):
            raw_exception_refs = [*raw_exception_refs, exception["evidence_id"]]
        exception_refs = {
            _reference_value(value)
            for value in raw_exception_refs
        }
        criteria = exception.get("criteria", exception.get("affected_criteria", [])) or []
        if isinstance(criteria, str):
            criteria = [criteria]
        if reference in exception_refs and criterion in criteria and str(exception.get("reason", "")).strip():
            return True
    return False


def _resolve_record(index: dict[str, EvidenceRecord], reference: str, criterion: str) -> EvidenceRecord | None:
    """Resolve a reference, including legacy code references without category."""
    direct = index.get(reference)
    if direct is not None:
        return direct
    if reference.startswith("static_analysis.matches.["):
        suffix = reference.split("static_analysis.matches", 1)[1].lstrip(".")
        candidates = [
            record for key, record in index.items()
            if key.startswith("static_analysis.matches.")
            and key.endswith(suffix)
            and criterion in record.criterion_candidates
        ]
        if len(candidates) == 1:
            return candidates[0]
    return None


def _validate_schema(
    index: dict[str, EvidenceRecord],
    drafts: list[dict[str, Any]],
    debates: list[dict[str, Any]],
    finals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings = []
    for name, records in (("drafts", drafts), ("debates", debates), ("finals", finals)):
        for position, record in enumerate(records):
            criterion = record.get("criterion")
            location = f"{name}[{position}]"
            if criterion not in RUBRIC:
                findings.append(_finding("INVALID_CRITERION", "error", "알 수 없는 criterion입니다.", location, criterion))
            if name == "finals" and "final_score" not in record:
                findings.append(_finding("MISSING_FINAL_SCORE", "error", "최종 결정에 final_score가 없습니다.", location, criterion))
            if name == "drafts" and "score" not in record:
                findings.append(_finding("MISSING_DRAFT_SCORE", "error", "심사 초안에 score가 없습니다.", location, criterion))
    del index
    return findings


def validate_evidence_integrity(
    evidence: Any,
    drafts: Any = None,
    debates: Any = None,
    finals: Any = None,
    exceptions: Any = None,
) -> dict[str, Any]:
    """Validate provenance from reviewer drafts through coordinator finals.

    ``evidence`` may be the raw pipeline evidence payload or a normalized list
    of objects with ``id``, ``criterion_candidates``, ``source_type`` and
    ``available`` fields. All returned findings are sorted deterministically.
    """
    index = _artifact_index(evidence)
    draft_records = _as_records(drafts, "first_round")
    debate_records = _as_records(debates, "reconciliation")
    final_records = _as_records(finals, "final_decisions")
    exception_records = exceptions if isinstance(exceptions, list) else []
    findings = _validate_schema(index, draft_records, debate_records, final_records)

    draft_by_criterion: dict[str, list[dict[str, Any]]] = defaultdict(list)
    debate_by_criterion: dict[str, dict[str, Any]] = {}
    for draft in draft_records:
        draft_by_criterion[str(draft.get("criterion"))].append(draft)
    for debate in debate_records:
        criterion = debate.get("criterion")
        if criterion in RUBRIC:
            debate_by_criterion[criterion] = debate

    cross_criterion: dict[str, set[str]] = defaultdict(set)
    for position, final in enumerate(final_records):
        criterion = final.get("criterion")
        location = f"final_decisions[{position}]"
        if criterion not in RUBRIC:
            continue
        references = _records_for_references(final)
        sufficient = bool(final.get("evidence_sufficient", final.get("evidence_sufficient", True)))
        insufficient = bool(final.get("insufficient_evidence")) or not sufficient
        reason = str(final.get("reason", final.get("rationale", ""))).strip()
        explicitly_insufficient = insufficient and (
            bool(final.get("insufficient_evidence"))
            or not sufficient
            or any(marker in reason.lower() for marker in _INSUFFICIENT_MARKERS)
        )

        if not references and not explicitly_insufficient:
            findings.append(_finding("MISSING_EVIDENCE_REFERENCE", "error", "점수에 evidence/reference가 없습니다.", location, criterion))
        if not reason:
            findings.append(_finding("MISSING_FINAL_RATIONALE", "error", "최종 결정의 rationale이 없습니다.", location, criterion))
        if insufficient and explicitly_insufficient:
            findings.append(_finding("INSUFFICIENT_EVIDENCE_DECLARED", "info", "증거 부족 상태가 명시되었습니다.", location, criterion))

        for reference in references:
            record = _resolve_record(index, reference, criterion)
            if record is None:
                findings.append(_finding("DANGLING_REFERENCE", "error", "reference가 실제 artifact로 연결되지 않습니다.", location, criterion, [reference]))
                continue
            if record.source_type not in _KNOWN_SOURCE_TYPES:
                findings.append(_finding("UNSUPPORTED_SOURCE_TYPE", "error", "허용되지 않은 evidence source type입니다.", location, criterion, [reference]))
            if not record.available:
                findings.append(_finding("UNAVAILABLE_ARTIFACT", "error", "참조된 artifact를 사용할 수 없습니다.", location, criterion, [reference]))
            if criterion not in record.criterion_candidates:
                findings.append(_finding("CRITERION_MISMATCH", "error", "evidence가 해당 criterion에 허용되지 않습니다.", location, criterion, [reference]))
            cross_criterion[record.evidence_id].add(criterion)

        score = final.get("final_score")
        maximum = int(RUBRIC[criterion]["max_score"])
        if not isinstance(score, int) or not 0 <= score <= maximum:
            findings.append(_finding("FINAL_SCORE_OUT_OF_RANGE", "error", "최종 점수가 rubric 범위를 벗어났습니다.", location, criterion))

        trace = {str(value) for value in final.get("decision_trace", []) or []}
        expected = {f"draft:{criterion}:primary", f"draft:{criterion}:secondary", f"reconciliation:{criterion}"}
        if not expected.issubset(trace):
            findings.append(_finding("UNTRACEABLE_FINAL_DECISION", "error", "최종 결정이 reviewer/debate 기록으로 완전히 추적되지 않습니다.", location, criterion))
        if len(draft_by_criterion.get(criterion, [])) < 2 or criterion not in debate_by_criterion:
            findings.append(_finding("MISSING_PROVENANCE_RECORD", "error", "최종 결정에 필요한 draft/debate 기록이 없습니다.", location, criterion))

        positions = {draft.get("score") for draft in draft_by_criterion.get(criterion, []) if isinstance(draft.get("score"), int)}
        adjustment = final.get("adjustment") or {}
        adjustment_status = adjustment.get("status") if isinstance(adjustment, dict) else ""
        if positions and score not in positions and adjustment_status != "supported":
            findings.append(_finding("UNSUPPORTED_SCORE_ADJUSTMENT", "error", "reviewer/debate 근거 없이 최종 점수가 조정되었습니다.", location, criterion))

    for reference, criteria in sorted(cross_criterion.items()):
        if len(criteria) < 2:
            continue
        for criterion in sorted(criteria):
            if not _exception_allows(reference, criterion, exception_records):
                findings.append(_finding("CROSS_CRITERION_DUPLICATE", "error", "동일 evidence가 여러 criterion에 재사용되었습니다.", "final_decisions", criterion, [reference]))

    findings.sort(key=lambda item: (
        _SEVERITY_ORDER.get(item["severity"], 99),
        item["code"],
        item["location"],
        item.get("criterion") or "",
        tuple(item.get("references", [])),
    ))
    summary = Counter(item["severity"] for item in findings)
    return {
        "valid": summary.get("error", 0) == 0,
        "summary": {
            "error": summary.get("error", 0),
            "warning": summary.get("warning", 0),
            "info": summary.get("info", 0),
            "total": len(findings),
        },
        "findings": findings,
    }


def validate_panel_result(result: dict[str, Any], evidence: Any) -> dict[str, Any]:
    """Validate a panel result without requiring callers to unpack its stages."""
    return validate_evidence_integrity(
        evidence,
        drafts=result.get("first_round", []),
        debates=result.get("reconciliation", []),
        finals=result.get("final_decisions", []),
    )
