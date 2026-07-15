from __future__ import annotations

import html
import json
import os
from pathlib import Path

from .presentation import criterion_display

def _e(value: object) -> str:
    return html.escape(str(value))


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
    items = score.get("items", {})
    browser = data.get("browser") or {}
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = "".join(
        f"<tr class='score-row'><th>{_e(criterion_display(key, item)['label'])}</th><td>{item['score']} / {criterion_display(key, item)['max_score']}<div class='bar'><i style='--score:{item['score'] / item['max_score'] * 100:.1f}%'></i></div></td>"
        f"<td>{_e(item['confidence'])}</td><td>{'<br>'.join(_e(x) for x in item['evidence'])}{_references(item, output)}</td></tr>"
        for key, item in items.items()
    )
    steps = "".join(
        f"<li class='step-item'><b>{_e(step.get('status'))}</b> {_e(step.get('text', ''))}"
        f"{f' — {_e(step.get("error"))}' if step.get('error') else ''}"
        f"{f'<br><img src="{_e(os.path.relpath(step["screenshot"], output.parent))}" alt="step screenshot">' if step.get('screenshot') and Path(step['screenshot']).exists() else ''}</li>"
        for step in browser.get("steps", [])
    )
    categories = data.get("static_analysis", {}).get("categories", {})
    category_list = "".join(f"<li>{_e(key)}: {'detected' if value else 'not detected'}</li>" for key, value in categories.items())
    authors = data.get("git_analysis", {}).get("authors", {})
    author_list = "".join(f"<li>{_e(author)}: {count}</li>" for author, count in authors.items()) or "<li>분석 불가</li>"
    panel = data.get("panel", {})
    judge_rows = "".join(
        f"<tr><td>{_e(judge['persona'])}</td><td>{_e(judge['role'])}</td><td>{judge['score']} / {judge['max_score']}</td>"
        f"<td>{_e(judge['confidence'])}</td><td>{_e(judge['memo'])}<br>반복: {_e(judge['rounds'])}</td></tr>"
        for judge in panel.get("judges", {}).values()
    )
    battles = "".join(f"<details><summary>{_e(battle['left'])} vs {_e(battle['right'])}</summary><pre>{_e(battle['transcript'])}</pre></details>" for battle in panel.get("battles", [])) or "<p>배틀 조건을 만족한 항목 조합이 없습니다.</p>"
    discussion = "".join(f"<li class='discussion-step'><b>{_e(event['speaker'])}</b> · {_e(event['role'])}<p>{_e(event['text'])}</p></li>" for event in panel.get("discussion", []))
    browser_status = "available" if browser.get("available") else f"unavailable: {browser.get('error', 'no run')}"
    html_body = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>auto-as report</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px;color:#222}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:10px;text-align:left;vertical-align:top}}th{{background:#f5f5f5}}.total{{font-size:2em;margin:20px 0}}button{{padding:8px 14px;margin:4px;cursor:pointer}}.bar{{height:8px;background:#eee;margin-top:6px}}.bar i{{display:block;width:0;height:100%;background:#356ae6;transition:width .8s ease}}.revealed .bar i{{width:var(--score)}}.step-item,.discussion-step{{display:none;margin:12px 0;padding:12px;border-left:4px solid #356ae6;background:#f7f9ff}}.step-item:first-child,.discussion-step:first-child,.step-item.active,.discussion-step.active{{display:block}}.discussion-step p{{white-space:pre-line;margin-bottom:0}}img{{max-width:600px;margin-top:8px;border:1px solid #ddd}}</style>
</head><body><h1>auto-as 제출물 리포트</h1>
<p>데모: <a href="{_e(data.get('submission', {}).get('demo_url', ''))}">{_e(data.get('submission', {}).get('demo_url', ''))}</a></p>
<p>저장소: <a href="{_e(data.get('submission', {}).get('repo_url', ''))}">{_e(data.get('submission', {}).get('repo_url', ''))}</a></p>
<div class="total">총점 {score.get('total', 0)} / {score.get('max_total', 100)} <small>({ _e(score.get('mode', 'unknown')) })</small></div>
<h2>루브릭</h2><button id="reveal">점수 공개</button><table><tr><th>항목</th><th>점수</th><th>신뢰도</th><th>근거</th></tr>{rows}</table>
<h2>심사위원 패널</h2><p>반복 채점: {panel.get('repeats', 0)}회 · 아래 과정은 저장된 근거에서 재구성한 심사 리플레이입니다.</p><table><tr><th>심사위원</th><th>담당</th><th>점수</th><th>신뢰도</th><th>메모·반복값</th></tr>{judge_rows}</table>
<h3>심사 과정 리플레이</h3><button id="discussion-prev">이전 발언</button><button id="discussion-next">다음 발언</button><ol id="discussion">{discussion or '<li>심사 과정 없음</li>'}</ol><h3>심사위원 배틀</h3>{battles}
<h2>브라우저 실행</h2><p>상태: {_e(browser_status)} · 콘솔 오류: {len(browser.get('console_errors', []))}건</p><button id="prev">이전 스텝</button><button id="next">다음 스텝</button><ol id="steps">{steps or '<li>실행 기록 없음</li>'}</ol>
<h2>정적 분석</h2><ul>{category_list}</ul>
<h2>Git 분석</h2><ul>{author_list}</ul>
</body><script>
const report=document.body;
document.getElementById('reveal').onclick=()=>report.classList.add('revealed');
const steps=[...document.querySelectorAll('.step-item')]; let current=0;
function showStep(index){{ if(!steps.length)return; current=Math.max(0,Math.min(index,steps.length-1)); steps.forEach((step,i)=>step.classList.toggle('active',i===current)); }}
document.getElementById('prev').onclick=()=>showStep(current-1);
document.getElementById('next').onclick=()=>showStep(current+1);
showStep(0);
const discussion=[...document.querySelectorAll('.discussion-step')]; let discussionCurrent=0;
function showDiscussion(index){{ if(!discussion.length)return; discussionCurrent=Math.max(0,Math.min(index,discussion.length-1)); discussion.forEach((item,i)=>item.classList.toggle('active',i===discussionCurrent)); }}
document.getElementById('discussion-prev').onclick=()=>showDiscussion(discussionCurrent-1);
document.getElementById('discussion-next').onclick=()=>showDiscussion(discussionCurrent+1);
showDiscussion(0);
</script></html>"""
    output.write_text(html_body, encoding="utf-8")
