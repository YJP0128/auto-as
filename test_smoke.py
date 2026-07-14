import json
import tempfile
from pathlib import Path

from auto_as.pipeline import SubmissionError, load_submission, validate_submission
from auto_as.browser import is_destructive, split_scenario
from auto_as.planner import heuristic_plan, plan_scenario
from auto_as.scoring import score_evidence
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
    assert set(result["judges"]) == {"problem_wow", "agent_design", "completeness", "ux", "operations", "collaboration"}
    assert result["judges"]["ux"]["persona"] == "다니엘 킴"
    assert "user" in result["judges"]["ux"]["style"]
    assert any("UX check" in event["text"] for event in result["discussion"])
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
