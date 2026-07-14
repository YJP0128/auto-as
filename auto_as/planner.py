from __future__ import annotations

import json
import re

from .browser import is_destructive, split_scenario


def heuristic_plan(scenario: str) -> list[dict[str, str]]:
    plan = []
    for step in split_scenario(scenario):
        if is_destructive(step):
            plan.append({"action": "skip", "text": step, "reason": "destructive action"})
        elif any(word in step.lower() for word in ("upload", "업로드", "첨부", "파일")):
            plan.append({"action": "upload", "text": step})
        elif any(word in step.lower() for word in ("click", "클릭", "누르", "선택")):
            plan.append({"action": "click", "target": _target(step), "text": step})
        elif any(word in step.lower() for word in ("type", "enter", "fill", "입력", "작성")):
            value = _value(step)
            plan.append({"action": "fill", "target": "", "value": value or "", "text": step})
        else:
            plan.append({"action": "observe", "text": step})
    return plan


def _target(step: str) -> str:
    quoted = re.search(r"['\"“”‘’]([^'\"“”‘’]+)['\"“”‘’]", step)
    if quoted:
        return quoted.group(1).strip()
    target = re.sub(r"\s*버튼(?:을|를)?\s*(?:클릭(?:한다)?|누른다|선택한다?)\s*$", "", step)
    return re.sub(r"(?i)click|클릭|누르기|눌러|누르고|선택", "", target).strip(" .")


def _value(step: str) -> str | None:
    quoted = re.search(r"['\"“”‘’]([^'\"“”‘’]+)['\"“”‘’]", step)
    if quoted:
        return quoted.group(1).strip()
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", step)
    if email:
        return email.group(0)
    korean_value = re.search(r"(?:에|으로)\s*([가-힣A-Za-z0-9_-]+)\s*입력", step)
    return korean_value.group(1) if korean_value else None


def _decode(text: str) -> list[dict[str, str]]:
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    data = json.loads(fenced.group(1) if fenced else text)
    if not isinstance(data, list):
        raise ValueError("planner output must be a JSON list")
    allowed = {"click", "fill", "observe", "skip"}
    result = []
    for item in data:
        if not isinstance(item, dict) or item.get("action") not in allowed:
            raise ValueError("planner returned an invalid action")
        result.append({str(key): str(value) for key, value in item.items()})
    return result


def plan_scenario(scenario: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    return heuristic_plan(scenario), {"mode": "local_rules"}
