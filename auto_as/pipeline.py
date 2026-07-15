"""First-pass submission evidence collection."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


class SubmissionError(ValueError):
    pass


def validate_submission(data: dict) -> dict:
    required = ("demo_url", "repo_url", "scenario")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        raise SubmissionError(f"missing required fields: {', '.join(missing)}")

    for key in ("demo_url", "repo_url"):
        parsed = urlparse(data[key])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SubmissionError(f"invalid {key}: {data[key]}")

    parsed_repo = urlparse(data["repo_url"])
    if parsed_repo.netloc.lower() not in {"github.com", "www.github.com"}:
        raise SubmissionError("repo_url must point to public GitHub")
    result = {key: data[key].strip() for key in required}
    test_files = data.get("test_files", [])
    if not isinstance(test_files, list) or not all(isinstance(path, str) and path.strip() for path in test_files):
        raise SubmissionError("test_files must be a list of file paths")
    result["test_files"] = test_files
    return result


def clone_repository(repo_url: str, destination: Path) -> None:
    """Clone source only; never install, build, or execute repository code."""
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--no-tags", repo_url, str(destination)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "clone failed"
        raise SubmissionError(detail)


SIGNALS = {
    "agent_orchestration": ("agent", "crew", "autogen", "langgraph", "workflow"),
    "tools": ("tool_call", "tools", "function_call", "@tool"),
    "rag": ("retrieval", "vectorstore", "vector_store", "embedding", "chroma", "pinecone"),
    "multi_agent": ("multi-agent", "multi_agent", "subagent", "handoff"),
    # 운영품질(operational_quality) — 골든셋/성능평가 3단계 신호 (강→중→약)
    "golden_dataset": ("golden set", "golden dataset", "golden_dataset", "ground truth", "ground_truth", "gold standard", "gold_standard", "labeled dataset", "eval set", "eval_set", "test set"),
    "eval_metric": ("accuracy", "precision", "recall", "f1", "f1_score", "bleu", "rouge", "perplexity", "benchmark", "evaluation"),
    "eval_signal": ("eval", "evaluate", "quality check", "regression test"),
    # 아래 두 신호는 정적분석 표시용 — 운영품질 점수에는 반영하지 않는다 (신 루브릭 정의와 무관)
    "monitoring": ("telemetry", "tracing", "prometheus", "opentelemetry", "monitoring"),
    "guardrails": ("guardrail", "moderation", "sanitize", "validation", "content_filter"),
}

TEXT_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb", ".php",
    ".yaml", ".yml", ".json", ".toml",
}
SKIP_DIRS = {".git", ".github", ".claude", ".specify", "node_modules", ".venv", "venv", "dist", "build", "docs", "templates", "__pycache__"}


def static_analysis(repo: Path) -> dict:
    matches: dict[str, list[dict[str, str]]] = {key: [] for key in SIGNALS}
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(repo).parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            lowered = line.lower()
            for category, keywords in SIGNALS.items():
                if any(re.search(rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])", lowered) for keyword in keywords):
                    matches[category].append({"file": str(path.relative_to(repo)), "line": str(line_number), "text": line[:300]})

    return {
        "categories": {key: bool(value) for key, value in matches.items()},
        "matches": {key: value[:20] for key, value in matches.items()},
    }


def git_analysis(repo: Path) -> dict:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%aN%x09%aE%x09%aI"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        return {"available": False, "error": result.stderr.strip() or "git log failed"}

    authors: dict[str, int] = {}
    timestamps: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        name, email, timestamp = parts
        authors[f"{name} <{email}>"] = authors.get(f"{name} <{email}>", 0) + 1
        timestamps.append(timestamp)
    return {"available": True, "commit_count": len(timestamps), "authors": authors, "timestamps": timestamps}


def collect_evidence(submission: dict, artifact_dir: Path | None = None) -> dict:
    test_files = submission.get("test_files", [])
    submission = validate_submission(submission)
    submission["test_files"] = test_files
    with tempfile.TemporaryDirectory(prefix="auto-as-") as temporary:
        repo = Path(temporary) / "repo"
        clone_repository(submission["repo_url"], repo)
        browser_result = None
        if artifact_dir is not None:
            from .browser import run_demo_sync

            browser_result = run_demo_sync(submission["demo_url"], submission["scenario"], artifact_dir, submission.get("test_files", []))
        evidence = {
            "submission": submission,
            "repository": {"status": "available", "url": submission["repo_url"]},
            "static_analysis": static_analysis(repo),
            "git_analysis": git_analysis(repo),
            "browser": browser_result,
        }
        from .scoring import score_evidence
        from .panel import run_panel

        evidence["score"] = score_evidence(evidence)
        evidence["panel"] = run_panel(evidence)
        for key, judge in evidence["panel"].get("judges", {}).items():
            if key in evidence["score"]["items"]:
                evidence["score"]["items"][key]["confidence"] = judge["confidence"]
        if evidence["panel"].get("provider") == "openai":
            for key, judge in evidence["panel"].get("judges", {}).items():
                if key in evidence["score"]["items"]:
                    evidence["score"]["items"][key]["score"] = judge["score"]
            evidence["score"]["total"] = sum(item["score"] for item in evidence["score"]["items"].values())
            evidence["score"]["mode"] = "openai"
        return evidence


def load_submission(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionError(f"cannot read input JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SubmissionError("input JSON must be an object")
    return data


def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
