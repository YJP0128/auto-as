import json
import tempfile
from pathlib import Path

from auto_as.pipeline import SubmissionError, load_submission, normalize_artifacts, route_artifacts, static_analysis, validate_submission
from auto_as.browser import is_destructive, split_scenario
from auto_as.planner import heuristic_plan, plan_scenario
from auto_as.scoring import RUBRIC, score_evidence
from auto_as.report import render_report
from auto_as.leaderboard import assign_badges, render_leaderboard
from auto_as.panel import run_panel
from auto_as.cli import main as cli_main


def test_validate_submission():
    data = validate_submission({
        "demo_url": "https://example.com/demo",
        "repo_url": "https://github.com/example/project",
        "scenario": "Click the start button",
    })
    assert data["scenario"] == "Click the start button"

    try:
        validate_submission({"demo_url": "nope", "repo_url": "https://github.com/a/b", "scenario": "x"})
    except SubmissionError:
        pass
    else:
        raise AssertionError("invalid URL should fail")


def test_load_submission():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "submission.json"
        path.write_text(json.dumps({"scenario": "x"}), encoding="utf-8")
        assert load_submission(path)["scenario"] == "x"


def test_scenario_helpers():
    assert split_scenario("로그인 버튼을 클릭하고 이메일을 입력한다") == ["로그인 버튼을 클릭", "이메일을 입력한다"]
    assert is_destructive("계정을 삭제한다")
    assert heuristic_plan("'시작' 버튼을 클릭한다")[0]["action"] == "click"
    plan = heuristic_plan("받는 사람 입력란에 민수 입력하고 추천 버튼을 클릭한다")
    assert plan[0]["value"] == "민수"
    assert plan[1]["target"] == "추천"
    assert heuristic_plan("대화 파일을 업로드한다")[0]["action"] == "upload"
    assert plan_scenario("계정을 삭제한다")[1]["mode"] == "local_rules"


def test_score_bounds():
    result = score_evidence({"submission": {"scenario": "x"}, "static_analysis": {"categories": {}}, "git_analysis": {}})
    assert 0 <= result["total"] <= 100
    assert sum(item["max_score"] for item in result["items"].values()) == 100


def test_static_evidence_schema_and_stable_ids():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        (repo / "app.py").write_text("from langgraph import StateGraph\n", encoding="utf-8")
        first = static_analysis(repo)
        second = static_analysis(repo)

    assert first["evidence"] == second["evidence"]
    assert len(first["evidence"]) == 1
    evidence = first["evidence"][0]
    assert evidence["id"].startswith("static_analysis:signal:")
    assert evidence["source"] == "static_analysis"
    assert evidence["kind"] == "signal"
    assert evidence["category"] == "agent_orchestration"
    assert evidence["reference"] == {"category": "agent_orchestration", "file": "app.py", "line": 1}


def test_artifact_normalization():
    artifacts = normalize_artifacts(
        {"evidence": []},
        {"steps": [{"step": 1, "text": "click start", "status": "success", "screenshot": "step-1.png"}], "console_errors": ["boom"]},
        {"commits": [{"id": "abc", "author": "A <a@example.com>", "timestamp": "2026-01-01T00:00:00Z"}]},
    )
    assert [artifact["source"] for artifact in artifacts] == ["browser", "browser", "git_analysis"]
    assert {artifact["kind"] for artifact in artifacts} == {"step", "console_error", "commit"}
    assert len({artifact["id"] for artifact in artifacts}) == 3


def test_criteria_artifact_routing():
    rubric = {
        "ai_implementation": {"evidence_sources": ("static_analysis",)},
        "operational_quality": {"evidence_sources": ("static_analysis",)},
        "completeness": {"evidence_sources": ("browser",)},
    }
    artifacts = [
        {"id": "a", "source": "static_analysis", "category": "tools"},
        {"id": "b", "source": "static_analysis", "category": "monitoring"},
        {"id": "c", "source": "static_analysis", "category": "golden_dataset"},
        {"id": "d", "source": "browser", "category": "step"},
    ]
    routed = route_artifacts(artifacts, rubric)
    assert [item["id"] for item in routed["ai_implementation"]] == ["a"]
    assert [item["id"] for item in routed["operational_quality"]] == ["c"]
    assert [item["id"] for item in routed["completeness"]] == ["d"]


def test_routing_gap_contracts():
    routed = route_artifacts([], RUBRIC)
    assert set(routed) == set(RUBRIC)
    assert all(items == [] for items in routed.values())

    artifacts = [
        {"id": "browser", "source": "browser", "kind": "step"},
        {"id": "monitor", "source": "static_analysis", "category": "monitoring"},
        {"id": "eval", "source": "static_analysis", "category": "eval_metric"},
    ]
    routed = route_artifacts(artifacts, RUBRIC)
    assert all(item["source"] == "browser" for item in routed["completeness"])
    assert [item["id"] for item in routed["operational_quality"]] == ["eval"]


def test_missing_operational_evidence_is_insufficient():
    result = score_evidence({"submission": {}, "static_analysis": {"categories": {}}, "git_analysis": {}})
    operational = result["items"]["operational_quality"]
    assert operational["score"] == 0
    assert operational["confidence"] == "low"
    assert operational["references"] == []


def test_operational_quality_tiers():
    def op(categories):
        return score_evidence({"submission": {}, "static_analysis": {"categories": categories}, "git_analysis": {}})["items"]["operational_quality"]

    assert op({"golden_dataset": True})["score"] == 8
    assert op({"eval_metric": True})["score"] == 5
    assert op({"eval_signal": True})["score"] == 2
    assert op({"golden_dataset": True, "eval_metric": True, "eval_signal": True})["score"] == 15
    empty = op({})
    assert empty["score"] == 0
    assert "근거 확인 안 됨" in empty["evidence"][0]
    assert op({"monitoring": True, "guardrails": True})["score"] == 0


def test_persona_documentation():
    document = (Path(__file__).parent / "docs" / "judge-personas.md").read_text(encoding="utf-8")
    expected_mapping = {
        "vc_investor": "problem_wow",
        "open_source_maintainer": "ai_implementation",
        "staff_engineer": "completeness",
        "evaluation_reviewer": "operational_quality",
        "it_creator": "presentation_collaboration",
    }
    assert set(expected_mapping.values()) == set(RUBRIC)
    assert document.count("## Persona:") == 5
    assert "실존 인물의 실제 외모·말투·인격·생애·대표 표현을 재현" in document
    assert "근거 부족" in document

    blocks = {}
    for section in document.split("## Persona:")[1:]:
        heading, body = section.split("\n", 1)
        blocks[heading.split("—", 1)[0].strip()] = body
    assert set(blocks) == set(expected_mapping)

    required_labels = (
        "역할 및 전문 분야",
        "주 담당 기준",
        "선호 근거",
        "비판 성향",
        "허용 말투",
        "금지 채점",
        "대표 합성 발언",
    )
    for persona_id, criterion in expected_mapping.items():
        block = blocks[persona_id]
        assert all(label in block for label in required_labels)
        assert f"**주 담당 기준:** `{criterion}`" in block
        assert document.count(f"**주 담당 기준:** `{criterion}`") == 1
        utterances = block.split("- **대표 합성 발언:**", 1)[1].split("- **프로필 이미지:**", 1)[0]
        assert utterances.count("  - “[") == 2

    operations = blocks["evaluation_reviewer"]
    for signal, weight in (("golden_dataset", 8), ("eval_metric", 5), ("eval_signal", 2)):
        assert f"`{signal}`" in operations
        assert f"{weight}점" in operations
    assert "`monitoring`·`guardrails`만으로 운영품질 점수 부여" in operations


def test_report_rendering():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "report.html"
        render_report({"submission": {"demo_url": "<unsafe>", "repo_url": "https://github.com/a/b"}, "score": {"items": {}, "total": 0, "max_total": 100}}, output)
        report = output.read_text(encoding="utf-8")
        assert "&lt;unsafe&gt;" in report


def test_leaderboard_rendering():
    result = {"team": "alpha", "score": {"total": 10, "items": {"problem_wow": {"name": "문제·Wow", "score": 10, "max_score": 20, "confidence": "medium"}}}, "browser": {}}
    assert assign_badges([result]) == {"alpha": ["가장 대담한 도전상"]}
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "leaderboard.html"
        render_leaderboard([result], output)
        rendered = output.read_text(encoding="utf-8")
        assert "alpha" in rendered
        assert "alpha/report.html" in rendered
        assert "검토 필요" not in rendered
        assert "data-replay" not in rendered and "replay-button" not in rendered
        assert "card-front" in rendered and "card-back" in rendered
        assert "data-badge-key='problem_wow'" in rendered
        assert "visibility:hidden" in rendered.split("<style>", 1)[1].split("</style>", 1)[0]


def test_leaderboard_review_flag():
    low_confidence = {"team": "beta", "score": {"total": 5, "items": {"problem_wow": {"name": "문제·Wow", "score": 5, "max_score": 20, "confidence": "low"}}}, "browser": {}}
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "leaderboard.html"
        render_leaderboard([low_confidence], output)
        assert "검토 필요" in output.read_text(encoding="utf-8")


def test_panel():
    result = run_panel({"submission": {"scenario": "x"}, "static_analysis": {"categories": {}}, "git_analysis": {}})
    assert set(result["judges"]) == {"problem_wow", "ai_implementation", "completeness", "operational_quality", "presentation_collaboration"}
    assert all(judge["rounds"] == [judge["score"], judge["score"]] for judge in result["judges"].values())
    assert result["discussion"][-1]["speaker"] == "Coordinator"


def test_test_file_path_is_contained():
    with tempfile.TemporaryDirectory() as directory:
        input_path = Path(directory) / "submission.json"
        input_path.write_text(json.dumps({
            "demo_url": "https://example.com",
            "repo_url": "https://github.com/a/b",
            "scenario": "x",
            "test_files": ["../../etc/passwd"],
        }), encoding="utf-8")
        assert cli_main([str(input_path)]) == 2


if __name__ == "__main__":
    test_validate_submission()
    test_load_submission()
