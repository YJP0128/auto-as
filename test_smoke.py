import json
import tempfile
from pathlib import Path

from auto_as.pipeline import SubmissionError, load_submission, validate_submission
from auto_as.browser import is_destructive, split_scenario
from auto_as.planner import heuristic_plan, plan_scenario
from auto_as.scoring import score_evidence
from auto_as.report import render_report
from auto_as.leaderboard import _persona_image_html, assign_badges, render_leaderboard
from auto_as.panel import (
    COORDINATOR,
    PERSONAS,
    SCORING_INVARIANTS,
    build_openai_panel_prompt,
    build_persona_prompt_context,
    criterion_max_score,
    judge_once,
    parse_openai_judge,
    resolve_criterion_key,
    run_local_panel,
)
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
    data = {"submission": {"scenario": "x"}, "static_analysis": {"categories": {}}, "git_analysis": {}}
    result = run_local_panel(data)
    rubric_keys = {resolve_criterion_key(persona) for persona in PERSONAS.values()}
    assert len(PERSONAS) == 5
    assert set(result["judges"]) == rubric_keys
    assert all(judge["persona_id"] in PERSONAS for judge in result["judges"].values())
    assert "ux" not in result["judges"]
    assert all(judge["rounds"] == [judge["score"], judge["score"]] for judge in result["judges"].values())
    assert result["coordinator"]["is_scoring_persona"] is False
    assert result["discussion"][-1]["speaker"] == COORDINATOR["display_name"]
    for event in result["discussion"]:
        assert set(event.get("score_snapshot", {})).issubset(rubric_keys)


def test_persona_configuration_and_prompt():
    required = {
        "id", "display_name", "role", "specialty", "primary_criterion", "tone_guidance",
        "preferences", "favored_evidence", "critique_guidance", "prohibited_scoring",
        "representative_utterances", "catchphrase", "profile_image_path", "profile_image_alt", "is_scoring_persona",
    }
    expected_mapping = {
        "vc_investor": "problem_wow",
        "open_source_maintainer": "ai_implementation",
        "staff_engineer": "completeness",
        "evaluation_reviewer": "operational_quality",
        "it_creator": "presentation_collaboration",
    }
    assert set(PERSONAS) == {
        "vc_investor", "open_source_maintainer", "staff_engineer", "evaluation_reviewer", "it_creator",
    }
    assert {persona_id: persona["primary_criterion"] for persona_id, persona in PERSONAS.items()} == expected_mapping
    assert len({persona["id"] for persona in PERSONAS.values()}) == 5
    assert all(required <= set(persona) and persona["is_scoring_persona"] is True for persona in PERSONAS.values())
    assert COORDINATOR["id"] not in PERSONAS and COORDINATOR["is_scoring_persona"] is False
    canonical_rubric = {criterion: {"max_score": maximum} for criterion, maximum in {
        "problem_wow": 20,
        "ai_implementation": 20,
        "completeness": 25,
        "operational_quality": 15,
        "presentation_collaboration": 20,
    }.items()}
    for persona in PERSONAS.values():
        assert criterion_max_score(persona, canonical_rubric) == canonical_rubric[persona["primary_criterion"]]["max_score"]

    data = {"submission": {"scenario": "x"}, "static_analysis": {"categories": {}, "matches": {}}, "git_analysis": {}}
    prompt = build_openai_panel_prompt(data)
    for persona_id, persona in PERSONAS.items():
        context = build_persona_prompt_context(persona_id)
        assert context["id"] == persona_id
        assert context["primary_criterion"] == persona["primary_criterion"]
        assert context["profile_image"]["alt"]
        assert persona_id in prompt
        assert all(line.startswith("[") for line in persona["representative_utterances"])
    assert all(rule in prompt for rule in SCORING_INVARIANTS)
    assert "Persona voice changes wording only and never changes rubric scoring" in prompt
    assert "Every scored claim must cite a concrete supplied reference" in prompt


def test_persona_assets_and_documentation():
    root = Path(__file__).parent
    package = root / "auto_as"
    paths = []
    runtime = (package / "panel.py").read_text(encoding="utf-8")
    real_person_names = ("아이유", "손흥민", "강호동", "백종원", "박명수")
    assert not any(name in runtime for name in real_person_names)
    for persona in PERSONAS.values():
        path = package / persona["profile_image_path"]
        paths.append(path)
        assert path.is_file()
        svg = path.read_text(encoding="utf-8")
        assert "<svg" in svg and 'width="512"' in svg and 'height="512"' in svg
        assert persona["profile_image_alt"]
        assert not any(name in svg for name in real_person_names)
    assert len(paths) == len(set(paths)) == 5

    document = (root / "docs" / "judge-personas.md").read_text(encoding="utf-8")
    assert document.count("## Persona:") == 5
    assert "실존 인물의 실제 외모·말투·인격·생애·대표 표현을 재현" in document
    assert "근거 부족" in document
    assert all(persona["id"] in document for persona in PERSONAS.values())
    blocks = {block.split("—", 1)[0].strip(): block for block in document.split("## Persona:")[1:]}
    required_labels = (
        "역할 및 전문 분야", "주 담당 기준", "선호 근거", "비판 성향",
        "허용 말투", "금지 채점", "대표 합성 발언", "프로필 이미지", "대체 텍스트",
    )
    for persona_id, persona in PERSONAS.items():
        block = blocks[persona_id]
        assert all(label in block for label in required_labels)
        assert f"`{persona['primary_criterion']}`" in block
        assert f"`auto_as/{persona['profile_image_path']}`" in block
        assert persona["profile_image_alt"] in block


def test_persona_tone_does_not_change_scores():
    data = {"submission": {"scenario": "x"}, "static_analysis": {"categories": {}}, "git_analysis": {}}
    before = judge_once(data)
    persona = PERSONAS["vc_investor"]
    original = persona["tone_guidance"]
    try:
        persona["tone_guidance"] = "완전히 다른 표현 방식"
        after = judge_once(data)
    finally:
        persona["tone_guidance"] = original
    for key in before:
        assert before[key]["score"] == after[key]["score"]
        assert before[key]["evidence"] == after[key]["evidence"]
        assert before[key]["references"] == after[key]["references"]


def test_openai_judge_requires_references():
    rubric_key, missing = parse_openai_judge("vc_investor", {
        "score": 18,
        "confidence": "high",
        "insufficient_evidence": False,
        "evidence": [{"claim": "문제가 명확함", "reference": ""}],
    })
    assert rubric_key == "problem_wow"
    assert missing["insufficient_evidence"] is True
    assert missing["confidence"] == "low"
    assert missing["references"] == []

    for invalid_references in ([""], [{}], [{"type": "ai_reference", "value": ""}]):
        _, invalid = parse_openai_judge("vc_investor", {
            "score": 18,
            "confidence": "high",
            "insufficient_evidence": False,
            "evidence": [{"claim": "문제가 명확함", "reference": ""}],
            "references": invalid_references,
        })
        assert invalid["insufficient_evidence"] is True
        assert invalid["confidence"] == "low"
        assert invalid["references"] == []

    _, missing_claim = parse_openai_judge("vc_investor", {
        "score": 18,
        "confidence": "high",
        "insufficient_evidence": False,
        "evidence": [{"claim": "", "reference": "submission.scenario"}],
    })
    assert missing_claim["insufficient_evidence"] is True
    assert missing_claim["confidence"] == "low"

    _, grounded = parse_openai_judge("vc_investor", {
        "score": 12,
        "confidence": "medium",
        "insufficient_evidence": False,
        "evidence": [{"claim": "시나리오가 제출됨", "reference": "submission.scenario"}],
    })
    assert grounded["insufficient_evidence"] is False
    assert grounded["references"] == [{"type": "ai_reference", "value": "submission.scenario"}]


def test_legacy_operations_signal_is_not_rebranded_as_evaluation():
    data = {
        "submission": {"scenario": "x"},
        "static_analysis": {
            "categories": {"monitoring": True},
            "matches": {"monitoring": [{"file": "metrics.py", "line": "1", "text": "prometheus"}]},
        },
        "git_analysis": {},
    }
    result = run_local_panel(data)
    review = " ".join(event["text"] for event in result["discussion"] if event.get("persona_id") == "evaluation_reviewer")
    assert "레거시 운영 신호" in review
    assert "평가 관련 코드 참조가 있습니다" not in review


def test_leaderboard_persona_images_and_fallback():
    data = {"submission": {"scenario": "x"}, "static_analysis": {"categories": {}}, "git_analysis": {}, "browser": {}}
    data["score"] = score_evidence(data)
    data["panel"] = run_local_panel(data)
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "leaderboard.html"
        render_leaderboard([{**data, "team": "alpha"}], output)
        rendered = output.read_text(encoding="utf-8")
        assert rendered.count("class='persona-card'") == 5
        assert rendered.count("data-image-state='ready'") == 5
        assert "class='persona-fallback'" in rendered and "onerror=" in rendered
        assert ".persona-fallback{display:grid!important" not in rendered
        for persona in PERSONAS.values():
            assert persona["profile_image_alt"] in rendered
            assert (output.parent / "assets" / "personas" / Path(persona["profile_image_path"]).name).is_file()

        first_judge = next(iter(data["panel"]["judges"].values()))
        original = first_judge["profile"]["image_path"]
        try:
            first_judge["profile"]["image_path"] = "assets/personas/missing.svg"
            render_leaderboard([{**data, "team": "alpha"}], output)
            missing_rendered = output.read_text(encoding="utf-8")
            assert "data-image-state='missing'" in missing_rendered
            assert "class='persona-fallback' aria-hidden='true'>👤</span>" in missing_rendered
        finally:
            first_judge["profile"]["image_path"] = original

        same_directory = _persona_image_html(first_judge["profile"], Path(__file__).parent / "auto_as" / "leaderboard.html")
        assert "data-image-state='ready'" in same_directory


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
    tests = [(name, function) for name, function in sorted(globals().items()) if name.startswith("test_") and callable(function)]
    for _, function in tests:
        function()
    print(f"{len(tests)} tests passed")
