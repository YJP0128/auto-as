import json
import tempfile
from pathlib import Path

from auto_as.pipeline import SubmissionError, load_submission, validate_submission
from auto_as.browser import is_destructive, split_scenario
from auto_as.planner import heuristic_plan, plan_scenario
from auto_as.scoring import RUBRIC, score_evidence
from auto_as.report import render_report
from auto_as.leaderboard import _persona_image_html, assign_badges, render_leaderboard
from auto_as.presentation import criterion_display
from auto_as.panel import (
    COORDINATOR,
    PERSONAS,
    SCORING_INVARIANTS,
    _parse_openai_discussion_event,
    _reference_catalog,
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


def test_downstream_rubric_display_uses_canonical_metadata():
    assert criterion_display("ai_implementation")["label"] == "AI 기능 구현"
    assert criterion_display("completeness")["max_score"] == 25
    assert criterion_display("operational_quality")["badge"] == "평가 품질상"


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


def test_persona_assets_and_leaderboard_fallback():
    root = Path(__file__).parent
    package = root / "auto_as"
    paths = [package / persona["profile_image_path"] for persona in PERSONAS.values()]
    assert len(paths) == len(set(paths)) == 5
    assert set((package / "assets" / "personas").glob("*.svg")) == set(paths)
    real_person_names = ("아이유", "손흥민", "강호동", "백종원", "박명수")
    document = (root / "docs" / "judge-personas.md").read_text(encoding="utf-8")
    for persona, path in zip(PERSONAS.values(), paths):
        svg = path.read_text(encoding="utf-8")
        assert "<svg" in svg and 'width="512"' in svg and 'height="512"' in svg
        assert persona["profile_image_alt"]
        assert f"`auto_as/{persona['profile_image_path']}`" in document
        assert persona["profile_image_alt"] in document
        assert not any(name in svg for name in real_person_names)

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

    same_directory = _persona_image_html(first_judge["profile"], package / "leaderboard.html")
    assert "data-image-state='ready'" in same_directory
    escaped = _persona_image_html({"image_path": "../README.md", "image_alt": "unsafe", "avatar": "👤"}, package / "leaderboard.html")
    assert "data-image-state='missing'" in escaped


def test_panel():
    data = {"submission": {"scenario": "x"}, "static_analysis": {"categories": {}}, "git_analysis": {}}
    result = run_local_panel(data)
    rubric_keys = {resolve_criterion_key(persona) for persona in PERSONAS.values()}
    assert len(PERSONAS) == 5
    assert set(result["judges"]) == rubric_keys
    assert all(judge["persona_id"] in PERSONAS for judge in result["judges"].values())
    assert "AI 기능 구현" in result["judges"]["ai_implementation"]["role"]
    assert all(judge["rounds"] == [judge["score"], judge["score"]] for judge in result["judges"].values())
    assert result["coordinator"]["is_scoring_persona"] is False
    assert result["discussion"][-1]["speaker"] == COORDINATOR["display_name"]
    for event in result["discussion"]:
        assert set(event.get("score_snapshot", {})).issubset(rubric_keys)


def test_persona_configuration_and_prompt_invariants():
    required = {
        "id", "display_name", "role", "specialty", "primary_criterion", "tone_guidance",
        "preferences", "favored_evidence", "critique_guidance", "prohibited_scoring",
        "representative_utterances", "catchphrase", "profile_image_path", "profile_image_alt",
        "is_scoring_persona",
    }
    expected_mapping = {
        "vc_investor": "problem_wow",
        "open_source_maintainer": "ai_implementation",
        "staff_engineer": "completeness",
        "evaluation_reviewer": "operational_quality",
        "it_creator": "presentation_collaboration",
    }
    assert set(PERSONAS) == set(expected_mapping)
    assert {key: persona["primary_criterion"] for key, persona in PERSONAS.items()} == expected_mapping
    assert len({persona["id"] for persona in PERSONAS.values()}) == 5
    assert all(required <= set(persona) and persona["is_scoring_persona"] for persona in PERSONAS.values())
    assert COORDINATOR["id"] not in PERSONAS and not COORDINATOR["is_scoring_persona"]
    assert all(resolve_criterion_key(persona) == persona["primary_criterion"] for persona in PERSONAS.values())

    canonical_rubric = {criterion: {"max_score": maximum} for criterion, maximum in {
        "problem_wow": 20,
        "ai_implementation": 20,
        "completeness": 25,
        "operational_quality": 15,
        "presentation_collaboration": 20,
    }.items()}
    for persona in PERSONAS.values():
        assert criterion_max_score(persona, canonical_rubric) == canonical_rubric[persona["primary_criterion"]]["max_score"]

    evidence = {
        "submission": {"scenario": "x"},
        "static_analysis": {
            "categories": {"golden_dataset": True, "monitoring": True},
            "matches": {
                "golden_dataset": [{"file": "eval/golden.jsonl", "line": 1, "text": "golden set"}],
                "monitoring": [{"file": "metrics.py", "line": 1, "text": "prometheus"}],
            },
        },
        "git_analysis": {},
    }
    prompt = build_openai_panel_prompt(evidence)
    for persona_id, persona in PERSONAS.items():
        context = build_persona_prompt_context(persona_id)
        assert context["id"] == persona_id
        assert context["primary_criterion"] == persona["primary_criterion"]
        assert context["profile_image"]["alt"]
        assert persona_id in prompt
    assert all(rule in prompt for rule in SCORING_INVARIANTS)
    assert "Persona voice changes wording only and never changes rubric scoring" in prompt
    assert "EVIDENCE.reference_catalog[primary_criterion]" in prompt
    assert "static_analysis.matches.golden_dataset[0]" in prompt
    reference_catalog = _reference_catalog(evidence)
    assert reference_catalog["operational_quality"] == ["static_analysis.matches.golden_dataset[0]"]
    assert "static_analysis.matches.monitoring[0]" not in reference_catalog["operational_quality"]
    operations = PERSONAS["evaluation_reviewer"]
    assert all(signal in " ".join(operations["favored_evidence"]) for signal in ("golden_dataset", "eval_metric", "eval_signal"))
    assert "monitoring·guardrails만으로 가점" in operations["prohibited_scoring"]

    runtime = (Path(__file__).parent / "auto_as" / "panel.py").read_text(encoding="utf-8")
    assert all(legacy not in runtime for legacy in ('"agent_design"', '"operations"', '"collaboration"'))
    assert not any(name in runtime for name in ("아이유", "손흥민", "강호동", "백종원", "박명수"))


def test_persona_tone_and_evidence_gaps_do_not_change_scores():
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

    panel = run_local_panel(data)
    assert panel["judges"]["operational_quality"]["score"] == 0
    assert panel["judges"]["operational_quality"]["confidence"] == "low"


def test_openai_judge_requires_known_references():
    grounded = {
        "score": 12,
        "confidence": "medium",
        "insufficient_evidence": False,
        "evidence": [{"claim": "시나리오가 제출됨", "reference": "submission.scenario"}],
    }
    rubric_key, accepted = parse_openai_judge("vc_investor", grounded, {"submission.scenario"})
    assert rubric_key == "problem_wow"
    assert accepted["score"] == 12
    assert accepted["references"] == [{"type": "ai_reference", "value": "submission.scenario"}]
    assert accepted["insufficient_evidence"] is False

    _, rejected = parse_openai_judge("vc_investor", {
        **grounded,
        "evidence": [{"claim": "근거를 찾음", "reference": "invented.reference"}],
    }, {"submission.scenario"})
    assert rejected["score"] == 0
    assert rejected["confidence"] == "low"
    assert rejected["references"] == []
    assert rejected["insufficient_evidence"] is True

    _, monitoring_rejected = parse_openai_judge("evaluation_reviewer", {
        "score": 15,
        "confidence": "high",
        "insufficient_evidence": False,
        "evidence": [{"claim": "모니터링이 있음", "reference": "static_analysis.matches.monitoring[0]"}],
    }, {"static_analysis.matches.golden_dataset[0]"})
    assert monitoring_rejected["score"] == 0
    assert monitoring_rejected["confidence"] == "low"

    _, mixed = parse_openai_judge("vc_investor", {
        **grounded,
        "evidence": [
            {"claim": "시나리오가 제출됨", "reference": "submission.scenario"},
            {"claim": "확인하지 않은 주장", "reference": "invented.reference"},
        ],
    }, {"submission.scenario"})
    assert mixed["score"] == 0
    assert mixed["evidence"] == ["시나리오가 제출됨"]
    assert mixed["insufficient_evidence"] is True


def test_openai_discussion_scores_require_known_references():
    catalog = {key: [] for key in RUBRIC}
    catalog["operational_quality"] = ["static_analysis.matches.golden_dataset[0]"]
    event = {
        "persona_id": "evaluation_reviewer",
        "at_seconds": 16,
        "side": "right",
        "kind": "proposal",
        "score_after": 8,
        "reference": "static_analysis.matches.golden_dataset[0]",
        "text": "골든셋 근거로 8점을 제안합니다.",
    }
    accepted = _parse_openai_discussion_event(event, catalog)
    assert accepted["score_snapshot"] == {"operational_quality": 8}
    assert accepted["references"] == [{"type": "ai_reference", "value": "static_analysis.matches.golden_dataset[0]"}]

    try:
        _parse_openai_discussion_event({**event, "reference": "static_analysis.matches.monitoring[0]"}, catalog)
    except ValueError:
        pass
    else:
        raise AssertionError("discussion score with an unsupported reference should fail")


def test_operational_persona_uses_only_t2_scoring_signals():
    monitoring_only = {
        "submission": {"scenario": "x"},
        "static_analysis": {
            "categories": {"monitoring": True, "guardrails": True},
            "matches": {"monitoring": [{"file": "metrics.py", "line": 1, "text": "prometheus"}]},
        },
        "git_analysis": {},
    }
    panel = run_local_panel(monitoring_only)
    assert panel["judges"]["operational_quality"]["score"] == 0
    review = " ".join(event["text"] for event in panel["discussion"] if event.get("persona_id") == "evaluation_reviewer")
    assert "점수 근거로 사용하지 않습니다" in review

    golden = {
        "submission": {"scenario": "x"},
        "static_analysis": {
            "categories": {"golden_dataset": True},
            "matches": {"golden_dataset": [{"file": "eval/golden.jsonl", "line": 1, "text": "golden set"}]},
        },
        "git_analysis": {},
    }
    panel = run_local_panel(golden)
    assert panel["judges"]["operational_quality"]["score"] == 8
    review = " ".join(event["text"] for event in panel["discussion"] if event.get("persona_id") == "evaluation_reviewer")
    assert "golden_dataset" in review and "eval/golden.jsonl" in review


def test_assignment_mapping():
    from auto_as.panel import CRITERION_REVIEWERS, PERSONAS, assignments_for, reviewers_for, validate_assignments

    validate_assignments()
    assert set(CRITERION_REVIEWERS) == set(RUBRIC)
    assert reviewers_for("problem_wow") == {"primary": "vc_investor", "secondary": "it_creator"}

    scoring = [pid for pid, persona in PERSONAS.items() if persona["is_scoring_persona"]]
    seen = [pid for roles in CRITERION_REVIEWERS.values() for pid in roles.values()]
    for pid in scoring:
        assert sorted(role for _, role in assignments_for(pid)) == ["primary", "secondary"]
        assert seen.count(pid) == 2

    for bad in (
        {**CRITERION_REVIEWERS, "problem_wow": {"primary": "vc_investor", "secondary": "vc_investor"}},
        {**CRITERION_REVIEWERS, "problem_wow": {"primary": "vc_investor", "secondary": "panel_coordinator"}},
    ):
        try:
            validate_assignments(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid assignment must raise")


def test_first_round_assessments():
    from collections import Counter

    from auto_as.panel import CRITERION_REVIEWERS, build_first_round_prompt, first_round_assessments

    data = {
        "submission": {"scenario": "x"},
        "static_analysis": {"categories": {"tools": True}, "matches": {"tools": [{"file": "a.py", "line": "1", "text": "t"}]}},
        "git_analysis": {"available": True, "authors": {"a": 2, "b": 2}},
        "browser": {"available": True, "steps": [{"status": "success"}], "console_errors": []},
    }
    drafts = first_round_assessments(data)
    assert len(drafts) == 10
    assert all(count == 2 for count in Counter(d["criterion"] for d in drafts).values())
    assert all(count == 2 for count in Counter(d["persona_id"] for d in drafts).values())
    for draft in drafts:
        assert CRITERION_REVIEWERS[draft["criterion"]][draft["role"]] == draft["persona_id"]
        assert 0 <= draft["score"] <= draft["max_score"]
        assert isinstance(draft["insufficient_evidence"], bool)
    assert first_round_assessments(data) == drafts  # 결정론

    empty = first_round_assessments({"submission": {}, "static_analysis": {"categories": {}}, "git_analysis": {}})
    operational = [d for d in empty if d["criterion"] == "operational_quality"]
    assert operational and all(d["insufficient_evidence"] for d in operational)

    prompt = build_first_round_prompt(data)
    assert prompt.count('"role": "primary"') == 5
    assert prompt.count('"role": "secondary"') == 5
    assert "ONLY its own assigned criterion" in prompt


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
