from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

from .presentation import criterion_display
from .scoring import RUBRIC
from .validation import validate_panel_result


def _e(value: object) -> str:
    return html.escape(str(value))


def _reference_value(reference: Any) -> str:
    if isinstance(reference, str):
        return reference.strip()
    if isinstance(reference, dict):
        if reference.get("type") == "ai_reference":
            return str(reference.get("value", "")).strip()
        if reference.get("type") == "code":
            return f"static_analysis.matches.{reference.get('category', 'unknown')}[{reference.get('line', '')}]"
        if reference.get("type") == "browser":
            return f"browser.steps[{reference.get('step', '')}]"
        if reference.get("type") == "scenario":
            return "submission.scenario"
        if reference.get("type") == "git":
            return "git_analysis.authors"
        return str(reference.get("reference", reference.get("id", reference.get("value", "")))).strip()
    return ""


def _anchor(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "unknown"
    return safe[:100]


def _reference_link(reference: str) -> str:
    anchor = _anchor(reference)
    return f"<a class='evidence-link' href='#evidence-{_e(anchor)}'>{_e(reference)}</a>"


def _criterion_models(data: dict) -> list[dict]:
    score_items = (data.get("score") or {}).get("items") or {}
    panel = data.get("panel") or {}
    judges = panel.get("judges") or {}
    drafts = panel.get("first_round") or []
    reconciliations = {item.get("criterion"): item for item in panel.get("reconciliation") or []}
    finals = {item.get("criterion"): item for item in panel.get("final_decisions") or []}
    models = []
    for key in RUBRIC:
        item = score_items.get(key, {})
        display = criterion_display(key, item)
        final = finals.get(key, {})
        criterion_drafts = [draft for draft in drafts if draft.get("criterion") == key]
        judge = judges.get(key, {})
        references = final.get("references") or item.get("references") or []
        reference_values = list(dict.fromkeys(value for value in (_reference_value(ref) for ref in references) if value))
        evidence = [str(value) for value in item.get("evidence", []) if str(value).strip()]
        sufficient = final.get("evidence_sufficient")
        if sufficient is None:
            sufficient = bool(reference_values) and not any("근거 부족" in value or "확인 안 됨" in value for value in evidence)
        reviewers = []
        for draft in criterion_drafts:
            reviewers.append({
                "name": draft.get("persona", draft.get("persona_id", "심사위원")),
                "role": draft.get("role", ""),
                "score": draft.get("score", "—"),
                "position": draft.get("rationale", "; ".join(draft.get("evidence", [])) or "근거 부족"),
            })
        if not reviewers and judge:
            reviewers.append({"name": judge.get("persona", "심사위원"), "role": judge.get("role", ""), "score": judge.get("score", "—"), "position": judge.get("memo", "")})
        models.append({
            "key": key,
            "label": display["label"],
            "score": final.get("final_score", item.get("score", 0)),
            "max_score": display["max_score"],
            "confidence": item.get("confidence", "low"),
            "rationale": final.get("reason") or "; ".join(evidence) or "확인 가능한 최종 근거가 없습니다.",
            "evidence": evidence,
            "references": reference_values,
            "sufficient": bool(sufficient),
            "reviewers": reviewers,
            "reconciliation": reconciliations.get(key, {}),
            "coordinator": final,
        })
    return models


def _evidence_quality(data: dict) -> dict:
    panel = data.get("panel") or {}
    try:
        return validate_panel_result(panel, data)
    except (TypeError, ValueError, KeyError):
        return {"valid": False, "summary": {"error": 1, "warning": 0, "info": 0, "total": 1}, "findings": [{"code": "VALIDATION_UNAVAILABLE", "severity": "warning", "message": "근거 품질 검증 결과를 계산할 수 없습니다.", "location": "report"}]}


def _references_section(models: list[dict]) -> str:
    values = []
    seen = set()
    for model in models:
        for reference in model["references"]:
            if reference in seen:
                continue
            seen.add(reference)
            values.append(f"<li id='evidence-{_e(_anchor(reference))}'><code>{_e(reference)}</code><span> { _e(model['label']) } 근거</span></li>")
    return "".join(values) or "<li>연결된 evidence/reference가 없습니다.</li>"


def _criterion_section(model: dict) -> str:
    status = "evidence-sufficient" if model["sufficient"] else "evidence-insufficient"
    status_label = "근거 확인" if model["sufficient"] else "근거 부족"
    refs = " ".join(_reference_link(value) for value in model["references"]) or "연결된 reference 없음"
    evidence = "".join(f"<li>{_e(value)}</li>" for value in model["evidence"]) or "<li>기록된 근거 없음</li>"
    reviewers = "".join(
        f"<li><strong>{_e(reviewer['name'])}</strong> · {_e(reviewer['role'])}: {_e(reviewer['score'])}점 — {_e(reviewer['position'])}</li>"
        for reviewer in model["reviewers"]
    ) or "<li>담당 심사위원 기록 없음</li>"
    reconciliation = model["reconciliation"].get("rationale") or model["reconciliation"].get("reason") or "조정 기록 없음"
    coordinator = model["coordinator"].get("reason") or "coordinator 최종 결정 기록 없음"
    return f"""<article id='criterion-{_e(model['key'])}' class='criterion-card {status}' aria-labelledby='criterion-title-{_e(model['key'])}'>
<header><div><p class='criterion-kicker'>{_e(status_label)}</p><h3 id='criterion-title-{_e(model['key'])}'>{_e(model['label'])}</h3></div><strong class='criterion-score'>{_e(model['score'])} / {_e(model['max_score'])}</strong></header>
<p class='confidence'>신뢰도: {_e(model['confidence'])}</p>
<section class='decision-block'><h4>최종 판단</h4><p>{_e(model['rationale'])}</p></section>
<section class='evidence-block'><h4>관찰된 evidence</h4><ul>{evidence}</ul><p class='references'>Reference: {refs}</p></section>
<section class='reviewer-block'><h4>심사위원 위치</h4><ul>{reviewers}</ul></section>
<section class='reconciliation-block'><h4>조정·coordinator</h4><p><strong>조정:</strong> {_e(reconciliation)}</p><p><strong>최종 결정:</strong> {_e(coordinator)}</p></section>
</article>"""


def _references(item: dict, output: Path) -> str:
    refs = item.get("references", [])
    if not refs:
        return ""
    lines = []
    for ref in refs:
        value = dict(ref)
        if value.get("screenshot"):
            screenshot = Path(value["screenshot"])
            if screenshot.exists():
                value["screenshot"] = os.path.relpath(screenshot, output.parent)
        lines.append(f"<li><code>{_e(json.dumps(value, ensure_ascii=False))}</code></li>")
    return f"<details><summary>상세 참조 {len(refs)}건</summary><ul>{''.join(lines)}</ul></details>"


def render_report(data: dict, output: Path) -> None:
    score = data.get("score", {})
    browser = data.get("browser") or {}
    panel = data.get("panel") or {}
    models = _criterion_models(data)
    quality = _evidence_quality(data)
    findings = quality.get("findings", [])
    gaps = [model for model in models if not model["sufficient"]]
    output.parent.mkdir(parents=True, exist_ok=True)
    criterion_html = "".join(_criterion_section(model) for model in models)
    quality_items = "".join(f"<li class='finding-{_e(finding.get('severity', 'info'))}'><strong>{_e(finding.get('code', 'finding'))}</strong> {_e(finding.get('message', ''))}</li>" for finding in findings) or "<li>검증 finding 없음</li>"
    gap_html = "".join(f"<li><a href='#criterion-{_e(model['key'])}'>{_e(model['label'])}</a>: 근거 부족 상태가 명시되었습니다.</li>" for model in gaps) or "<li>모든 기준에 충분한 근거가 연결되어 있습니다.</li>"
    steps = "".join(
        f"<li class='step-item'><b>{_e(step.get('status'))}</b> {_e(step.get('text', ''))}{f' — {_e(step.get("error"))}' if step.get('error') else ''}{f'<br><img src="{_e(os.path.relpath(step["screenshot"], output.parent))}" alt="step screenshot">' if step.get('screenshot') and Path(step['screenshot']).exists() else ''}</li>"
        for step in browser.get("steps", [])
    )
    categories = data.get("static_analysis", {}).get("categories", {})
    category_list = "".join(f"<li>{_e(key)}: {'detected' if value else 'not detected'}</li>" for key, value in categories.items()) or "<li>정적 분석 기록 없음</li>"
    authors = data.get("git_analysis", {}).get("authors", {})
    author_list = "".join(f"<li>{_e(author)}: {count}</li>" for author, count in authors.items()) or "<li>분석 불가</li>"
    discussion = "".join(f"<li class='discussion-step'><b>{_e(event.get('speaker', ''))}</b> · {_e(event.get('role', ''))}<p>{_e(event.get('text', ''))}</p></li>" for event in panel.get("discussion", []))
    html_body = f"""<!doctype html>
<html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>auto-as report</title>
<style>
:root{{--ink:#172033;--muted:#647089;--line:#dfe5ef;--blue:#315bd8;--soft:#f5f8ff;--good:#126b4e;--warn:#8a4b00;--bad:#a22626}}
*{{box-sizing:border-box}}body{{font:16px/1.6 system-ui,-apple-system,sans-serif;max-width:1120px;margin:0 auto;padding:32px 20px 70px;color:var(--ink);background:#fff}}a{{color:var(--blue)}}h1,h2,h3,h4{{line-height:1.25}}.lede{{color:var(--muted)}}.total{{padding:18px 20px;margin:22px 0;border-radius:14px;background:var(--ink);color:#fff;font-size:1.6rem}}.report-section{{margin-top:34px}}.criterion-grid{{display:grid;gap:18px}}.criterion-card{{padding:20px;border:1px solid var(--line);border-radius:16px;background:#fff;box-shadow:0 4px 16px #1720330b}}.criterion-card header{{display:flex;justify-content:space-between;gap:20px;align-items:start}}.criterion-card.evidence-insufficient{{border-color:#e2ad70;background:#fffaf2}}.criterion-kicker{{margin:0;color:var(--muted);font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em}}.criterion-card h3{{margin:.25rem 0 0;font-size:1.3rem}}.criterion-score{{font-size:1.35rem;white-space:nowrap}}.confidence{{color:var(--muted);font-size:.9rem}}.criterion-card section{{margin-top:16px;padding:14px;border-radius:10px}}.decision-block{{background:var(--soft);border-left:4px solid var(--blue)}}.evidence-block{{background:#f4fbf8;border-left:4px solid var(--good)}}.reviewer-block{{background:#faf7ff;border-left:4px solid #7650b8}}.reconciliation-block{{background:#fff8ed;border-left:4px solid #d8891c}}.criterion-card h4{{margin:0 0 8px}}ul{{margin:8px 0 0;padding-left:22px}}.references{{margin-bottom:0;font-size:.9rem;overflow-wrap:anywhere}}.evidence-link{{margin-right:7px}}.summary-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.summary-card{{padding:16px;border:1px solid var(--line);border-radius:12px;background:#fafbfe}}.summary-card h3{{margin-top:0}}.finding-error{{color:var(--bad)}}.finding-warning{{color:var(--warn)}}.finding-info{{color:var(--muted)}}.score-table{{border-collapse:collapse;width:100%;margin-top:12px}}.score-table th,.score-table td{{border:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}}.score-table th{{background:#f6f8fc}}.bar{{height:8px;background:#e9edf4;margin-top:6px;border-radius:10px}}.bar i{{display:block;height:100%;width:var(--score);background:var(--blue);border-radius:10px}}.step-item,.discussion-step{{margin:12px 0;padding:12px;border-left:4px solid var(--blue);background:var(--soft)}}.step-item img{{max-width:100%;height:auto}}button{{padding:8px 14px;margin:4px;cursor:pointer}}.sr-only{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}@media(max-width:700px){{body{{padding:24px 14px 50px}}.summary-grid{{grid-template-columns:1fr}}.criterion-card header{{display:block}}.criterion-score{{display:block;margin-top:10px}}}}
</style></head><body>
<header><p class='lede'>AUTO-AS / EVIDENCE REPORT</p><h1>auto-as 제출물 리포트</h1><p class='lede'>데모와 저장소에서 수집된 근거, 심사위원의 위치, coordinator의 최종 결정을 한 흐름으로 확인합니다.</p></header>
<p>데모: <a href='{_e(data.get('submission', {}).get('demo_url', ''))}'>{_e(data.get('submission', {}).get('demo_url', ''))}</a></p><p>저장소: <a href='{_e(data.get('submission', {}).get('repo_url', ''))}'>{_e(data.get('submission', {}).get('repo_url', ''))}</a></p>
<div class='total' aria-label='총점'>총점 {score.get('total', 0)} / {score.get('max_total', 100)} <small>({_e(score.get('mode', 'unknown'))})</small></div>
<main>
<section class='report-section' aria-labelledby='criteria-heading'><h2 id='criteria-heading'>기준별 점수와 근거</h2><p class='lede'>각 점수는 최종 rationale, 담당 심사위원의 위치, 연결된 reference를 함께 보여줍니다.</p><div class='criterion-grid'>{criterion_html}</div></section>
<section class='report-section' aria-labelledby='summary-heading'><h2 id='summary-heading'>패널·근거 품질 요약</h2><div class='summary-grid'><article class='summary-card'><h3>Evidence 품질</h3><p>상태: <strong>{'검증 통과' if quality.get('valid') else '검토 필요'}</strong></p><ul><li>오류: {quality.get('summary', {}).get('error', 0)}건</li><li>경고: {quality.get('summary', {}).get('warning', 0)}건</li><li>정보: {quality.get('summary', {}).get('info', 0)}건</li></ul><ul>{quality_items}</ul></article><article class='summary-card'><h3>근거 공백</h3><ul>{gap_html}</ul></article></div></section>
<section class='report-section' aria-labelledby='references-heading'><h2 id='references-heading'>Evidence reference catalog</h2><p class='lede'>각 기준 카드에서 연결된 reference의 실제 anchor입니다.</p><ul>{_references_section(models)}</ul></section>
<section class='report-section' aria-labelledby='discussion-heading'><h2 id='discussion-heading'>심사 조정 리플레이</h2><p>반복 채점: {panel.get('repeats', 0)}회</p><ol>{discussion or '<li>심사 과정 없음</li>'}</ol></section>
<section class='report-section' aria-labelledby='browser-heading'><h2 id='browser-heading'>브라우저 실행</h2><p>상태: {_e('available' if browser.get('available') else browser.get('error', '실행 기록 없음'))} · 콘솔 오류: {len(browser.get('console_errors', []))}건</p><button id='prev' type='button'>이전 스텝</button><button id='next' type='button'>다음 스텝</button><ol id='steps'>{steps or '<li>실행 기록 없음</li>'}</ol></section>
<section class='report-section' aria-labelledby='static-heading'><h2 id='static-heading'>정적 분석</h2><ul>{category_list}</ul></section><section class='report-section' aria-labelledby='git-heading'><h2 id='git-heading'>Git 분석</h2><ul>{author_list}</ul></section>
</main><script>const steps=[...document.querySelectorAll('.step-item')];let current=0;function showStep(index){{if(!steps.length)return;current=Math.max(0,Math.min(index,steps.length-1));steps.forEach((step,i)=>step.hidden=i!==current)}};document.getElementById('prev').onclick=()=>showStep(current-1);document.getElementById('next').onclick=()=>showStep(current+1);steps.forEach(step=>step.hidden=true);showStep(0);</script></body></html>"""
    output.write_text(html_body, encoding="utf-8")
