"""First-pass submission evidence collection."""

from __future__ import annotations

import json
import hashlib
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

    evidence = [
        _artifact("static_analysis", "signal", match["text"], {"category": category, "file": match["file"], "line": int(match["line"])}, category)
        for category, category_matches in matches.items()
        for match in category_matches[:20]
    ]
    return {
        "categories": {key: bool(value) for key, value in matches.items()},
        "matches": {key: value[:20] for key, value in matches.items()},
        "evidence": evidence,
    }


def _artifact(source: str, kind: str, detail: str, reference: dict, category: str | None = None) -> dict:
    payload = json.dumps({"source": source, "kind": kind, "detail": detail, "reference": reference}, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    result = {"id": f"{source}:{kind}:{digest}", "source": source, "kind": kind, "detail": detail, "reference": reference}
    if category:
        result["category"] = category
    return result


def normalize_artifacts(static: dict, browser: dict | None, git: dict) -> list[dict]:
    artifacts = list(static.get("evidence", []))
    for step in (browser or {}).get("steps", []):
        reference = {key: step[key] for key in ("step", "screenshot", "error") if key in step}
        artifacts.append(_artifact("browser", "step", step.get("text", ""), {**reference, "status": step.get("status")}))
    for index, error in enumerate((browser or {}).get("console_errors", [])):
        artifacts.append(_artifact("browser", "console_error", error, {"index": index}))
    for commit in git.get("commits", []):
        artifacts.append(_artifact("git_analysis", "commit", commit.get("author", ""), commit))
    return artifacts


def route_artifacts(artifacts: list[dict], rubric: dict) -> dict[str, list[dict]]:
    implementation_categories = {"agent_orchestration", "tools", "rag", "multi_agent"}
    quality_categories = {"golden_dataset", "eval_metric", "eval_signal"}
    routed = {}
    for criterion, spec in rubric.items():
        allowed = set(spec.get("evidence_sources", ()))
        selected = [artifact for artifact in artifacts if artifact["source"] in allowed]
        if criterion == "ai_implementation":
            selected = [artifact for artifact in selected if artifact.get("category") in implementation_categories]
        elif criterion == "operational_quality":
            selected = [artifact for artifact in selected if artifact.get("category") in quality_categories]
        routed[criterion] = selected
    return routed


def git_analysis(repo: Path) -> dict:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%H%x09%aN%x09%aE%x09%aI"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        return {"available": False, "error": result.stderr.strip() or "git log failed"}

    authors: dict[str, int] = {}
    timestamps: list[str] = []
    commits: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        commit_id, name, email, timestamp = parts
        authors[f"{name} <{email}>"] = authors.get(f"{name} <{email}>", 0) + 1
        timestamps.append(timestamp)
        commits.append({"id": commit_id, "author": f"{name} <{email}>", "timestamp": timestamp})
    return {"available": True, "commit_count": len(timestamps), "authors": authors, "timestamps": timestamps, "commits": commits}


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
        static_result = static_analysis(repo)
        git_result = git_analysis(repo)
        evidence = {
            "submission": submission,
            "repository": {"status": "available", "url": submission["repo_url"]},
            "static_analysis": static_result,
            "git_analysis": git_result,
            "browser": browser_result,
        }
        evidence["artifacts"] = normalize_artifacts(static_result, browser_result, git_result)
        from .scoring import RUBRIC

        evidence["criteria_artifacts"] = route_artifacts(evidence["artifacts"], RUBRIC)
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
