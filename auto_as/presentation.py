"""Shared display metadata for rubric labels, maxima, and badges.

The scoring implementation is being migrated to a configurable rubric.  This
module keeps report and leaderboard rendering compatible with both the current
tuple-based rubric and the upcoming metadata-based rubric.
"""

from __future__ import annotations

from collections.abc import Mapping

from .scoring import RUBRIC


CRITERION_ALIASES = {
    "problem_wow": ("problem_wow",),
    "ai_implementation": ("ai_implementation", "agent_design"),
    "completeness": ("completeness",),
    "operational_quality": ("operational_quality", "operations"),
    "presentation_collaboration": ("presentation_collaboration", "collaboration"),
}

CRITERION_DISPLAY = {
    "problem_wow": {"label": "문제·Wow", "max_score": 20, "badge": "가장 대담한 도전상"},
    "ai_implementation": {"label": "AI 기능 구현", "max_score": 20, "badge": "AI 구현 장인상"},
    "completeness": {"label": "동작 완성도", "max_score": 25, "badge": "완성도 챔피언상"},
    "operational_quality": {"label": "운영 품질", "max_score": 15, "badge": "평가 품질상"},
    "presentation_collaboration": {"label": "발표·협업", "max_score": 20, "badge": "원팀 발표상"},
}


def canonical_criterion_key(key: str) -> str:
    """Return the official criterion key for a current or legacy runtime key."""
    for canonical, aliases in CRITERION_ALIASES.items():
        if key in aliases:
            return canonical
    return key


def runtime_criterion_key(key: str, rubric: Mapping | None = None) -> str:
    """Resolve an official key to the key present in a runtime rubric."""
    available = rubric or RUBRIC
    canonical = canonical_criterion_key(key)
    for alias in CRITERION_ALIASES.get(canonical, (canonical,)):
        if alias in available:
            return alias
    return key


def criterion_display(key: str, item: Mapping | None = None, rubric: Mapping | None = None) -> dict:
    """Return stable display metadata without changing score payload keys."""
    canonical = canonical_criterion_key(key)
    fallback = CRITERION_DISPLAY.get(canonical, {"label": str(key), "max_score": 0, "badge": ""})
    runtime_key = runtime_criterion_key(canonical, rubric)
    entry = (rubric or RUBRIC).get(runtime_key)
    label = fallback["label"]
    maximum = fallback["max_score"]
    if isinstance(entry, Mapping):
        label = entry.get("label", entry.get("name", label))
        maximum = int(entry.get("max_score", maximum))
    elif isinstance(entry, (tuple, list)) and len(entry) >= 2:
        maximum = int(entry[1])
    if item:
        maximum = int(item.get("max_score", maximum))
    return {
        "key": canonical,
        "runtime_key": runtime_key,
        "label": label,
        "max_score": maximum,
        "badge": fallback["badge"],
    }


def criterion_label(key: str, item: Mapping | None = None) -> str:
    return criterion_display(key, item)["label"]


def badge_definitions() -> dict[str, str]:
    return {key: metadata["badge"] for key, metadata in CRITERION_DISPLAY.items()}
