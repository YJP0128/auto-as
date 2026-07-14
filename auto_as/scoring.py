from __future__ import annotations

RUBRIC = {
    "problem_wow": ("문제·Wow", 20),
    "agent_design": ("에이전트 설계", 25),
    "completeness": ("동작·완성도", 20),
    "operations": ("운영·품질", 20),
    "collaboration": ("발표·협업", 15),
}


def _item(key: str, score: int, evidence: list[str], confidence: str = "low", references: list[dict] | None = None) -> dict:
    name, maximum = RUBRIC[key]
    return {"name": name, "score": max(0, min(maximum, score)), "max_score": maximum, "evidence": evidence, "confidence": confidence, "references": references or []}


def _browser_score(data: dict) -> tuple[int, list[str], list[dict]]:
    browser = data.get("browser") or {}
    steps = browser.get("steps", [])
    executed = [step for step in steps if step.get("status") in {"success", "failed"}]
    successful = sum(step.get("status") == "success" for step in executed)
    errors = len(browser.get("console_errors", []))
    if not executed:
        return 0, ["브라우저 실행 근거 없음"], []
    score = round(20 * successful / len(executed)) - min(10, errors * 2)
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
    wow = _item("problem_wow", 5 * len(wow_evidence), wow_evidence or ["문제·Wow 근거 부족"], references=wow_refs)

    design_flags = [key for key in ("agent_orchestration", "tools", "rag", "multi_agent") if categories.get(key)]
    design_refs = [{"type": "code", **match} for flag in design_flags for match in static.get("matches", {}).get(flag, [])[:5]]
    design = _item("agent_design", min(25, 5 * len(design_flags)), [f"탐지된 설계 신호: {', '.join(design_flags) or '없음'}"], references=design_refs)

    completeness_score, completeness_evidence, completeness_refs = _browser_score(data)
    completeness = _item("completeness", completeness_score, completeness_evidence, "medium" if browser.get("available") else "low", completeness_refs)

    operations_flags = [key for key in ("evaluation", "monitoring", "guardrails") if categories.get(key)]
    operations_refs = [{"type": "code", **match} for flag in operations_flags for match in static.get("matches", {}).get(flag, [])[:5]]
    operations = _item("operations", round(20 * len(operations_flags) / 3), [f"탐지된 운영 품질 신호: {', '.join(operations_flags) or '없음'}"], references=operations_refs)

    authors = git.get("authors", {}) if git.get("available") else {}
    counts = list(authors.values())
    if len(counts) < 2:
        collaboration_score = 0
        collaboration_evidence = [f"커밋 작성자 {len(counts)}명"]
    else:
        total = sum(counts)
        evenness = 1 - sum(abs(count / total - 1 / len(counts)) for count in counts) / 2
        collaboration_score = round(15 * evenness)
        collaboration_evidence = [f"커밋 작성자 {len(counts)}명", f"기여 균등도 {evenness:.2f}"]
    collaboration = _item("collaboration", collaboration_score, collaboration_evidence, references=[{"type": "git", "authors": authors}])

    items = {key: value for key, value in zip(RUBRIC, (wow, design, completeness, operations, collaboration))}
    return {
        "mode": "local_provisional",
        "items": items,
        "total": sum(item["score"] for item in items.values()),
        "max_total": 100,
    }
