from __future__ import annotations

# 공식 루브릭 (단일 출처). 배점은 여기서만 정의하고 나머지 모듈은 이 값을 참조한다.
# 필요 시 이 딕셔너리만 바꾸면 배점 조정이 전 파이프라인에 전파된다.
RUBRIC = {
    "problem_wow": {
        "label": "문제·Wow",
        "max_score": 20,
        "definition": "해결할 문제를 명확히 정의했고 서비스만의 차별화된 가치가 있는가",
        "evidence_sources": ("scenario", "browser", "readme"),
    },
    "ai_implementation": {
        "label": "AI 기능 구현",
        "max_score": 20,
        "definition": "적절한 도구·RAG 등 기술로 서비스에 필요한 기능을 효과적으로 구현했는가",
        "evidence_sources": ("static_analysis",),
    },
    "completeness": {
        "label": "동작·완성도",
        "max_score": 25,
        "definition": "정의한 문제가 서비스로 실질적으로 해결됐고 주요 기능이 안정적으로 구현됐는가",
        "evidence_sources": ("browser",),
    },
    "operational_quality": {
        "label": "운영·품질",
        "max_score": 15,
        "definition": "골든 데이터셋을 구축하고 이를 활용해 서비스 성능·품질을 적절히 평가했는가",
        "evidence_sources": ("static_analysis",),
    },
    "presentation_collaboration": {
        "label": "발표·협업",
        "max_score": 20,
        "definition": "발표 스토리·전달 구조가 명확하고 팀원 간 역할 분담·협업이 체계적인가",
        "evidence_sources": ("git_analysis",),
    },
}

MAX_TOTAL = sum(spec["max_score"] for spec in RUBRIC.values())


def _item(key: str, score: int, evidence: list[str], confidence: str = "low", references: list[dict] | None = None) -> dict:
    spec = RUBRIC[key]
    maximum = spec["max_score"]
    return {"name": spec["label"], "score": max(0, min(maximum, score)), "max_score": maximum, "evidence": evidence, "confidence": confidence, "references": references or []}


def _browser_score(data: dict) -> tuple[int, list[str], list[dict]]:
    browser = data.get("browser") or {}
    steps = browser.get("steps", [])
    executed = [step for step in steps if step.get("status") in {"success", "failed"}]
    successful = sum(step.get("status") == "success" for step in executed)
    errors = len(browser.get("console_errors", []))
    if not executed:
        return 0, ["브라우저 실행 근거 없음"], []
    maximum = RUBRIC["completeness"]["max_score"]
    score = round(maximum * successful / len(executed)) - min(10, errors * 2)
    references = [{"type": "browser", "step": step.get("step"), "status": step.get("status"), "screenshot": step.get("screenshot")} for step in steps]
    return score, [f"실행 성공 {successful}/{len(executed)}", f"콘솔 오류 {errors}건"], references


def score_evidence(data: dict) -> dict:
    static = data.get("static_analysis", {})
    categories = static.get("categories", {})
    git = data.get("git_analysis", {})
    browser = data.get("browser") or {}

    wow_evidence = []
    if data.get("submission", {}).get("scenario"):
        wow_evidence.append("데모 시나리오가 제출됨")
    if browser.get("steps"):
        wow_evidence.append("데모 실행 스텝이 기록됨")
    wow_refs = [{"type": "scenario", "text": data.get("submission", {}).get("scenario", "")}]
    wow = _item("problem_wow", 10 * len(wow_evidence), wow_evidence or ["문제·Wow 근거 부족"], references=wow_refs)

    design_flags = [key for key in ("agent_orchestration", "tools", "rag", "multi_agent") if categories.get(key)]
    design_refs = [{"type": "code", **match} for flag in design_flags for match in static.get("matches", {}).get(flag, [])[:5]]
    design = _item("ai_implementation", 5 * len(design_flags), [f"탐지된 AI 구현 신호: {', '.join(design_flags) or '없음'}"], references=design_refs)

    completeness_score, completeness_evidence, completeness_refs = _browser_score(data)
    completeness = _item("completeness", completeness_score, completeness_evidence, "medium" if browser.get("available") else "low", completeness_refs)

    operations_flags = [key for key in ("evaluation", "monitoring", "guardrails") if categories.get(key)]
    operations_refs = [{"type": "code", **match} for flag in operations_flags for match in static.get("matches", {}).get(flag, [])[:5]]
    operations = _item("operational_quality", round(RUBRIC["operational_quality"]["max_score"] * len(operations_flags) / 3), [f"탐지된 운영 품질 신호: {', '.join(operations_flags) or '없음'}"], references=operations_refs)

    authors = git.get("authors", {}) if git.get("available") else {}
    counts = list(authors.values())
    if len(counts) < 2:
        collaboration_score = 0
        collaboration_evidence = [f"커밋 작성자 {len(counts)}명"]
    else:
        total = sum(counts)
        evenness = 1 - sum(abs(count / total - 1 / len(counts)) for count in counts) / 2
        collaboration_score = round(RUBRIC["presentation_collaboration"]["max_score"] * evenness)
        collaboration_evidence = [f"커밋 작성자 {len(counts)}명", f"기여 균등도 {evenness:.2f}"]
    collaboration = _item("presentation_collaboration", collaboration_score, collaboration_evidence, references=[{"type": "git", "authors": authors}])

    items = {key: value for key, value in zip(RUBRIC, (wow, design, completeness, operations, collaboration))}
    return {
        "mode": "local_provisional",
        "items": items,
        "total": sum(item["score"] for item in items.values()),
        "max_total": MAX_TOTAL,
    }
