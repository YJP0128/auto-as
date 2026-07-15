from __future__ import annotations

import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

from .presentation import criterion_label
from .scoring import RUBRIC, score_evidence


SCORING_INVARIANTS = (
    "페르소나의 말투와 취향은 설명 방식에만 영향을 주며 점수를 올리거나 내리는 근거가 될 수 없다.",
    "모든 점수 주장에는 제공된 코드·브라우저·Git·제출 정보의 구체적인 참조가 필요하다.",
    "담당 기준에 유효한 근거가 없으면 추정하지 말고 근거 부족을 명시한다.",
    "제공되지 않은 기능·화면·팀원·사용자 조사·실행 결과를 만들어내지 않는다.",
    "monitoring과 guardrails는 참고 정보일 뿐 operational_quality 점수 근거가 아니다.",
)


# 모든 인물은 이 프로젝트를 위해 만든 허구의 캐릭터다. 요청서에 언급된
# 실존 인물은 넓은 직업적 모티프만 제공했으며 실제 외모·성격·말투를 재현하지 않는다.
PERSONAS = {
    "vc_investor": {
        "id": "vc_investor",
        "display_name": "윤서린",
        "role": f"VC 투자자 · {criterion_label('problem_wow')}",
        "specialty": "사용자 문제 정의와 차별적 가치 검증",
        "primary_criterion": "problem_wow",
        "tone_guidance": "차분하고 짧게 묻고, 확인한 사실과 아직 모르는 것을 분리한다.",
        "preferences": ["문제와 대상 사용자의 연결", "데모 전후의 관찰 가능한 변화", "비교 가능한 차별성"],
        "favored_evidence": ["제출 시나리오", "브라우저 실행 결과", "문제와 결과가 연결되는 관찰"],
        "critique_guidance": "시장성이나 사용자 수요를 추정하지 않고 제출된 문제와 데모가 실제로 연결되는지만 비평한다.",
        "prohibited_scoring": ["화려한 소개만으로 가점", "근거 없는 시장 규모·PMF 추정", "캐릭터 취향에 따른 점수 변경"],
        "representative_utterances": [
            "[문제와 결과 연결 근거가 있을 때] 연결은 확인했습니다. 차별성은 비교 가능한 근거가 더 필요합니다.",
            "[전후 변화 근거가 부족할 때] 대상 사용자는 보이지만 무엇이 나아지는지는 확인되지 않습니다.",
        ],
        "style_label": "간결한 가치 검증",
        "summary": "좋은 이야기보다 사용자가 실제로 얻는 변화를 먼저 확인한다.",
        "catchphrase": "문제와 변화가 같은 흐름에 있나요?",
        "tagline": "문제와 변화가 같은 화면에 있어야 합니다.",
        "dialogue_avatar": "💡",
        "fallback_avatar": "👤",
        "profile_image_path": "assets/personas/vc_investor.svg",
        "profile_image_alt": "보라색 피치 카드를 든 가상의 VC 투자자 윤서린",
        "is_scoring_persona": True,
    },
    "open_source_maintainer": {
        "id": "open_source_maintainer",
        "display_name": "임도현",
        "role": f"오픈소스 메인테이너 · {criterion_label('ai_implementation')}",
        "specialty": "모델·도구·RAG 호출 경로와 실제 코드 연결 검증",
        "primary_criterion": "ai_implementation",
        "tone_guidance": "협력적으로 말하되 파일과 줄, 입력과 출력의 연결을 정확히 짚는다.",
        "preferences": ["목적에 필요한 최소 구현", "추적 가능한 도구 호출", "실제 결과로 이어지는 RAG 흐름"],
        "favored_evidence": ["코드 파일과 줄", "도구 호출 순서", "입력에서 결과까지 이어지는 구현 경로"],
        "critique_guidance": "import나 키워드 존재와 실제 실행 경로를 구분하고 구현이 문제 해결에 기여하는지 본다.",
        "prohibited_scoring": ["프레임워크 이름만으로 가점", "주석·죽은 코드를 실제 구현으로 인정", "근거 없는 아키텍처 추정"],
        "representative_utterances": [
            "[호출 경로가 결과까지 이어질 때] 연결은 확인됩니다. 선언만 있는 기능은 점수 근거로 쓰지 않겠습니다.",
            "[키워드만 확인될 때] 기능 이름보다 연결 경로를 보겠습니다.",
        ],
        "style_label": "근거 중심 코드 리뷰",
        "summary": "기술 이름보다 입력이 실제 결과로 이어지는 코드 경로를 본다.",
        "catchphrase": "입력부터 결과까지 연결된 줄을 봅시다.",
        "tagline": "호출됐다는 줄과 결과가 이어지는 줄을 보여주세요.",
        "dialogue_avatar": "🧩",
        "fallback_avatar": "👤",
        "profile_image_path": "assets/personas/open_source_maintainer.svg",
        "profile_image_alt": "노트북과 브랜치 그래프를 살피는 가상의 오픈소스 개발자 임도현",
        "is_scoring_persona": True,
    },
    "staff_engineer": {
        "id": "staff_engineer",
        "display_name": "한태산",
        "role": f"글로벌 테크 Staff Engineer · {criterion_label('completeness')}",
        "specialty": "브라우저 실행 안정성, 실패 지점, 복구 가능성과 재현성",
        "primary_criterion": "completeness",
        "tone_guidance": "힘 있고 단정적인 문장으로 관찰된 실행 사실부터 말한다.",
        "preferences": ["끝까지 이어지는 핵심 흐름", "재현 가능한 성공", "명확한 실패와 복구 상태"],
        "favored_evidence": ["Playwright 스텝 상태", "콘솔 오류", "스텝별 스크린샷과 실패 메시지"],
        "critique_guidance": "클릭 성공과 문제 해결 성공을 구분하고 브라우저 기록 밖의 화면 상태는 추정하지 않는다.",
        "prohibited_scoring": ["보지 않은 화면을 봤다고 주장", "코드 설계를 완성도 점수에 혼합", "근거 없는 안정성 인정"],
        "representative_utterances": [
            "[핵심 흐름이 성공했을 때] 끝까지 이어진 점은 확인했습니다. 실패한 단계는 안정성 판단에 남깁니다.",
            "[재시도 기록이 없을 때] 복구 가능성은 근거 부족으로 두겠습니다.",
        ],
        "style_label": "단단한 실행 검증",
        "summary": "발표 화면보다 직접 실행한 기록을 우선한다.",
        "catchphrase": "끝까지 같은 결과가 재현되나요?",
        "tagline": "끝까지 재현돼야 완성입니다.",
        "dialogue_avatar": "🧱",
        "fallback_avatar": "👤",
        "profile_image_path": "assets/personas/staff_engineer.svg",
        "profile_image_alt": "브라우저 창과 체크리스트를 든 가상의 Staff Engineer 한태산",
        "is_scoring_persona": True,
    },
    "evaluation_reviewer": {
        "id": "evaluation_reviewer",
        "display_name": "문정석",
        "role": f"AI 평가·논문 리뷰어 · {criterion_label('operational_quality')}",
        "specialty": "골든 데이터셋, 성능·품질 평가 지표와 실행 흔적의 타당성 검토",
        "primary_criterion": "operational_quality",
        "tone_guidance": "주장, 측정 방법, 결과의 순서로 차분히 검토한다.",
        "preferences": ["정답 기준이 있는 골든 데이터셋", "서비스 목표와 연결된 평가지표", "재현 가능한 평가 흔적"],
        "favored_evidence": ["golden_dataset 강 신호(8점)", "eval_metric 중 신호(5점)", "eval_signal 약 신호(2점)"],
        "critique_guidance": "세 평가 신호의 파일·줄 근거를 확인하고 monitoring·guardrails는 참고 정보로만 본다.",
        "prohibited_scoring": ["monitoring·guardrails만으로 가점", "일반 로깅을 골든셋 평가로 간주", "없는 결과 수치 생성"],
        "representative_utterances": [
            "[golden_dataset 신호가 확인될 때] 골든셋 근거는 확인했습니다. 정답 기준과 대표성은 별도로 보겠습니다.",
            "[monitoring만 확인될 때] 모니터링은 참고하되 운영품질 점수 근거로 사용하지 않겠습니다.",
        ],
        "style_label": "차분한 평가 타당성 검토",
        "summary": "품질 주장을 실제 데이터와 측정 결과로 되짚는다.",
        "catchphrase": "무엇으로, 어떻게 측정했나요?",
        "tagline": "좋다는 주장보다 어떻게 측정했는지가 먼저입니다.",
        "dialogue_avatar": "📊",
        "fallback_avatar": "👤",
        "profile_image_path": "assets/personas/evaluation_reviewer.svg",
        "profile_image_alt": "데이터 표와 평가 차트를 검토하는 가상의 AI 평가 리뷰어 문정석",
        "is_scoring_persona": True,
    },
    "it_creator": {
        "id": "it_creator",
        "display_name": "노기찬",
        "role": f"IT 콘텐츠 크리에이터 · {criterion_label('presentation_collaboration')}",
        "specialty": "발표 구조, 메시지 전달과 Git 기반 역할 분담 검증",
        "primary_criterion": "presentation_collaboration",
        "tone_guidance": "짧고 건조한 유머를 섞되 관찰한 기록을 먼저 말한다.",
        "preferences": ["한 번에 이해되는 발표 흐름", "역할과 결과의 일치", "Git 기록으로 확인되는 협업"],
        "favored_evidence": ["발표·시나리오 구조", "Git 작성자 분포", "커밋 시점과 역할 설명"],
        "critique_guidance": "발표의 재미와 점수를 분리하고 설명한 역할이 실제 Git 기록과 맞는지 확인한다.",
        "prohibited_scoring": ["웃기다는 이유만으로 가점", "Git 근거 없이 협업 추정", "개인에 대한 조롱이나 모욕"],
        "representative_utterances": [
            "[발표 흐름이 명확할 때] 이해하기 쉽습니다. 역할 분담은 Git 기록만큼만 인정하겠습니다.",
            "[재미 요소를 평가할 때] 재미는 있습니다. 점수는 별개입니다.",
        ],
        "style_label": "건조한 전달력 점검",
        "summary": "이야기가 명확한지, 그 이야기를 정말 팀이 함께 만들었는지 본다.",
        "catchphrase": "설명과 Git 기록이 같은 이야기인가요?",
        "tagline": "설명과 Git 기록이 같은 이야기를 해야 합니다.",
        "dialogue_avatar": "🎙️",
        "fallback_avatar": "👤",
        "profile_image_path": "assets/personas/it_creator.svg",
        "profile_image_alt": "마이크와 스토리보드를 든 가상의 IT 크리에이터 노기찬",
        "is_scoring_persona": True,
    },
}


COORDINATOR = {
    "id": "panel_coordinator",
    "display_name": "한결 코디네이터",
    "role": "최종 결정",
    "tone_guidance": "심사위원이 제시한 근거와 점수만 정리하며 새로운 사실이나 기준을 추가하지 않는다.",
    "fallback_avatar": "🎬",
    "is_scoring_persona": False,
}


# ── Task 7: 2:2 담당 매핑 ──────────────────────────────────────────
# 각 기준을 두 명(주담당 primary + 부담당 secondary)이 본다. primary는 위
# PERSONAS의 primary_criterion과 일치하고, secondary는 전문성이 인접한 다른
# 페르소나다. 이 매핑은 데이터 정의일 뿐이며 실제 2인 채점·토론은 이후 단계
# (1차 채점·의견 조정)에서 소비한다. 기존 1:1 채점 흐름은 변경하지 않는다.
CRITERION_REVIEWERS = {
    "problem_wow": {"primary": "vc_investor", "secondary": "it_creator"},
    "ai_implementation": {"primary": "open_source_maintainer", "secondary": "evaluation_reviewer"},
    "completeness": {"primary": "staff_engineer", "secondary": "open_source_maintainer"},
    "operational_quality": {"primary": "evaluation_reviewer", "secondary": "staff_engineer"},
    "presentation_collaboration": {"primary": "it_creator", "secondary": "vc_investor"},
}


def validate_assignments(assignments: dict | None = None, personas: dict | None = None, rubric: dict | None = None) -> None:
    """2:2 담당 매핑의 불변식을 검증한다. 위반 시 ValueError를 던진다."""
    assignments = assignments if assignments is not None else CRITERION_REVIEWERS
    personas = personas if personas is not None else PERSONAS
    rubric = rubric if rubric is not None else RUBRIC

    scoring_ids = {pid for pid, persona in personas.items() if persona.get("is_scoring_persona")}
    if set(assignments) != set(rubric):
        raise ValueError(f"assignments must cover exactly the rubric criteria: {sorted(rubric)}")

    per_persona: dict[str, list[str]] = {pid: [] for pid in scoring_ids}
    for criterion, roles in assignments.items():
        if set(roles) != {"primary", "secondary"}:
            raise ValueError(f"{criterion} must define exactly 'primary' and 'secondary'")
        if roles["primary"] == roles["secondary"]:
            raise ValueError(f"{criterion} primary and secondary must differ")
        for role, pid in roles.items():
            if pid not in scoring_ids:
                raise ValueError(f"{criterion} {role} is not a scoring persona: {pid}")
            per_persona[pid].append(role)
        if personas[roles["primary"]]["primary_criterion"] != criterion:
            raise ValueError(f"{criterion} primary {roles['primary']} does not own this criterion")

    for pid, roles in per_persona.items():
        if sorted(roles) != ["primary", "secondary"]:
            raise ValueError(f"{pid} must be primary for one criterion and secondary for another, got {roles}")


def reviewers_for(criterion: str) -> dict[str, str]:
    """기준을 담당하는 주담당/부담당 페르소나 id."""
    return dict(CRITERION_REVIEWERS[criterion])


def assignments_for(persona_id: str) -> list[tuple[str, str]]:
    """페르소나가 담당하는 (criterion, role) 목록 — 주담당 1 + 부담당 1."""
    return [(criterion, role) for criterion, roles in CRITERION_REVIEWERS.items() for role, pid in roles.items() if pid == persona_id]


# 기본 매핑은 항상 유효해야 한다 — 잘못된 편집이면 import 시점에 즉시 실패한다.
validate_assignments()


def resolve_criterion_key(persona: dict, rubric: dict | None = None) -> str:
    available = rubric or RUBRIC
    key = persona["primary_criterion"]
    if key not in available:
        raise KeyError(f"criterion is not available: {key}")
    return key


def criterion_max_score(persona: dict, rubric: dict | None = None) -> int:
    available = rubric or RUBRIC
    entry = available[resolve_criterion_key(persona, available)]
    return int(entry["max_score"])


def _profile(persona: dict) -> dict:
    return {
        "job": persona["role"],
        "personality": persona["summary"],
        "likes": ", ".join(persona["preferences"]),
        "dislikes": ", ".join(persona["prohibited_scoring"]),
        "voice": persona["tone_guidance"],
        "catchphrase": persona["catchphrase"],
        "tagline": persona["tagline"],
        "avatar": persona["fallback_avatar"],
        "image_path": persona["profile_image_path"],
        "image_alt": persona["profile_image_alt"],
    }


def build_persona_prompt_context(persona_id: str) -> dict:
    persona = PERSONAS[persona_id]
    runtime_key = resolve_criterion_key(persona)
    return {
        "id": persona["id"],
        "display_name": persona["display_name"],
        "fictional_parody": True,
        "is_scoring_persona": persona["is_scoring_persona"],
        "role": persona["role"],
        "specialty": persona["specialty"],
        "primary_criterion": persona["primary_criterion"],
        "runtime_criterion": runtime_key,
        "max_score": criterion_max_score(persona),
        "tone_guidance": persona["tone_guidance"],
        "preferences": persona["preferences"],
        "favored_evidence": persona["favored_evidence"],
        "critique_guidance": persona["critique_guidance"],
        "prohibited_scoring": persona["prohibited_scoring"],
        "representative_utterances": persona["representative_utterances"],
        "catchphrase": persona["catchphrase"],
        "profile_image": {"path": persona["profile_image_path"], "alt": persona["profile_image_alt"]},
        "scoring_invariants": list(SCORING_INVARIANTS),
    }


def _memo(persona: dict, item: dict) -> str:
    evidence = "; ".join(str(value) for value in item.get("evidence", [])) or "확인 가능한 근거가 없습니다."
    return f"{persona['display_name']} ({persona['style_label']}): {evidence}"


def _judge_record(persona: dict, item: dict) -> dict:
    return {
        "persona_id": persona["id"],
        "persona": persona["display_name"],
        "role": persona["role"],
        "style": persona["style_label"],
        "primary_criterion": persona["primary_criterion"],
        "rubric_key": resolve_criterion_key(persona),
        "profile": _profile(persona),
        "score": item["score"],
        "max_score": item["max_score"],
        "confidence": item["confidence"],
        "evidence": item.get("evidence", []),
        "references": item.get("references", []),
        "memo": _memo(persona, item),
    }


def judge_once(data: dict) -> dict[str, dict]:
    scored = score_evidence(data)["items"]
    judges = {}
    for persona in PERSONAS.values():
        rubric_key = resolve_criterion_key(persona, scored)
        judges[rubric_key] = _judge_record(persona, scored[rubric_key])
    return judges


def run_panel(data: dict, repeats: int = 2) -> dict:
    if os.getenv("OPENAI_API_KEY"):
        try:
            return run_openai_panel(data)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            fallback = run_local_panel(data, repeats)
            fallback["provider"] = "local_fallback"
            fallback["ai_error"] = str(exc)
            return fallback
    return run_local_panel(data, repeats)


INSUFFICIENT_EVIDENCE_MARKERS = ("근거 없음", "근거 부족", "확인 안 됨", "실행 근거 없음")


def _draft_insufficient(item: dict) -> bool:
    text = " ".join(str(entry) for entry in item.get("evidence", []))
    return any(marker in text for marker in INSUFFICIENT_EVIDENCE_MARKERS)


def first_round_assessments(data: dict) -> list[dict]:
    """1차 채점(stage 1): 담당 2인이 각 기준을 독립 채점한 10개 초안.

    task 7의 CRITERION_REVIEWERS를 소비해 기준마다 주담당·부담당 두 초안을 만든다.
    로컬은 규칙 점수라 primary·secondary가 같은 점수를 내되 페르소나 관점에 따라
    근거 프레이밍만 달라진다(실제 점수 발산은 OpenAI 모드). 각 페르소나는 담당한
    2개 기준만 채점한다. 이 초안은 이후 의견 조정·코디네이터 단계가 소비한다.
    """
    scored = score_evidence(data)["items"]
    drafts = []
    for criterion, roles in CRITERION_REVIEWERS.items():
        item = scored[criterion]
        insufficient = _draft_insufficient(item)
        for role in ("primary", "secondary"):
            persona = PERSONAS[roles[role]]
            role_label = "주담당" if role == "primary" else "부담당"
            evidence = [str(entry) for entry in item.get("evidence", [])]
            drafts.append({
                "criterion": criterion,
                "persona_id": persona["id"],
                "persona": persona["display_name"],
                "role": role,
                "score": item["score"],
                "max_score": item["max_score"],
                "confidence": item["confidence"],
                "evidence": evidence,
                "references": list(item.get("references", [])),
                "insufficient_evidence": insufficient,
                "rationale": f"{persona['display_name']}·{role_label} 관점: " + ("; ".join(evidence) or "확인 가능한 근거가 없습니다."),
            })
    return drafts


def reconcile_criteria(data: dict) -> list[dict]:
    """의견 조정(stage 2): 기준마다 주담당·부담당 두 초안을 맞대어 조정한 5개 레코드.

    로컬은 결정론이라 두 초안이 동점이므로 근거를 공유·합의한다(unresolved=False).
    실제 점수 발산과 반박은 OpenAI 모드에서 build_reconciliation_prompt가 처리한다.
    이 레코드의 proposed_score는 제안일 뿐이며, 최종 확정은 task 10(코디네이터)가 한다.
    """
    drafts: dict[str, dict[str, dict]] = {}
    for draft in first_round_assessments(data):
        drafts.setdefault(draft["criterion"], {})[draft["role"]] = draft

    records = []
    for criterion in RUBRIC:
        primary = drafts[criterion]["primary"]
        secondary = drafts[criterion]["secondary"]
        label = criterion_label(criterion)
        agree = primary["score"] == secondary["score"]
        insufficient = primary["insufficient_evidence"] and secondary["insufficient_evidence"]
        p_name, s_name = primary["persona"], secondary["persona"]
        if insufficient:
            comparison = f"{p_name}과 {s_name} 모두 {label}에서 확인 가능한 근거를 찾지 못했습니다."
            challenge = f"{s_name}: 근거가 없으면 점수를 추정하지 않겠습니다."
            rebuttal = f"{p_name}: 동의합니다. 근거 부족을 그대로 남깁니다."
        else:
            comparison = f"{p_name}(주담당)과 {s_name}(부담당) 모두 {label}을(를) {primary['score']}점으로 봤습니다."
            challenge = f"{s_name}: 같은 근거를 부담당 관점에서 다시 짚었습니다."
            rebuttal = f"{p_name}: 관점 차이는 있지만 점수 근거는 같습니다."
        records.append({
            "criterion": criterion,
            "primary_persona": primary["persona_id"],
            "secondary_persona": secondary["persona_id"],
            "primary_score": primary["score"],
            "secondary_score": secondary["score"],
            "max_score": primary["max_score"],
            "comparison": comparison,
            "challenge": challenge,
            "rebuttal": rebuttal,
            "accepted_evidence": list(primary["evidence"]),
            "accepted_references": list(primary["references"]),
            "rejected_evidence": [],
            "proposed_score": primary["score"],
            "proposed_confidence": primary["confidence"],
            "unresolved": not agree,
        })
    return records


def _reference_value(reference: dict) -> str:
    if reference.get("type") == "ai_reference":
        return str(reference.get("value", ""))
    if reference.get("type") == "code":
        return f"static_analysis.matches.{reference.get('category', '')}[{reference.get('line', '')}]"
    if reference.get("type") == "browser":
        return f"browser.steps[{reference.get('step', '')}]"
    if reference.get("type") == "scenario":
        return "submission.scenario"
    if reference.get("type") == "git":
        return "git_analysis.authors"
    return str(reference.get("value", ""))


def _decision_references(drafts: list[dict], reconciliation: dict) -> list[dict]:
    references = []
    seen = set()
    for draft in drafts:
        for reference in draft.get("references", []):
            value = _reference_value(reference)
            if value and value not in seen:
                seen.add(value)
                references.append(reference)
    for reference in reconciliation.get("accepted_references", []):
        value = _reference_value(reference)
        if value and value not in seen:
            seen.add(value)
            references.append(reference)
    return references[:10]


def _decision_record(criterion: str, drafts: list[dict], reconciliation: dict, score: int, reason: str, sufficient: bool, adjustment: str) -> dict:
    references = _decision_references(drafts, reconciliation)
    trace = [f"draft:{criterion}:primary", f"draft:{criterion}:secondary", f"reconciliation:{criterion}"]
    return {
        "criterion": criterion,
        "final_score": max(0, min(int(RUBRIC[criterion]["max_score"]), int(score))),
        "max_score": int(RUBRIC[criterion]["max_score"]),
        "reason": reason,
        "evidence_ids": sorted({_reference_value(reference) for reference in references if _reference_value(reference)}),
        "references": references,
        "decision_trace": trace,
        "evidence_sufficient": bool(sufficient),
        "adjustment": {"status": adjustment, "supported_by": trace[2:] if adjustment == "supported" else []},
    }


def validate_coordinator_decisions(decisions: list[dict], drafts: list[dict] | None = None, reconciliations: list[dict] | None = None) -> list[dict]:
    if not isinstance(decisions, list) or len(decisions) != len(RUBRIC):
        raise ValueError("coordinator must return exactly one decision per criterion")
    by_criterion = {decision.get("criterion"): decision for decision in decisions}
    if set(by_criterion) != set(RUBRIC):
        raise ValueError("coordinator decisions must cover every rubric criterion once")
    draft_map = {}
    for draft in drafts or []:
        draft_map.setdefault(draft["criterion"], []).append(draft)
    for criterion, decision in by_criterion.items():
        maximum = int(RUBRIC[criterion]["max_score"])
        if not isinstance(decision.get("final_score"), int) or not 0 <= decision["final_score"] <= maximum:
            raise ValueError(f"invalid final score for {criterion}")
        if not str(decision.get("reason", "")).strip() or not decision.get("decision_trace"):
            raise ValueError(f"incomplete coordinator trace for {criterion}")
        if not decision.get("references") and decision.get("evidence_sufficient", True):
            raise ValueError(f"missing coordinator references for {criterion}")
        if drafts and not set(decision["decision_trace"]).issuperset({f"draft:{criterion}:primary", f"draft:{criterion}:secondary"}):
            raise ValueError(f"untraceable coordinator decision for {criterion}")
        positions = {draft["score"] for draft in draft_map.get(criterion, [])}
        if positions and decision["final_score"] not in positions and decision.get("adjustment", {}).get("status") != "supported":
            raise ValueError(f"unsupported coordinator adjustment for {criterion}")
    return [by_criterion[criterion] for criterion in RUBRIC]


def finalize_criteria(data: dict, drafts: list[dict] | None = None, reconciliations: list[dict] | None = None) -> list[dict]:
    drafts = drafts if drafts is not None else first_round_assessments(data)
    reconciliations = reconciliations if reconciliations is not None else reconcile_criteria(data)
    grouped = {criterion: [draft for draft in drafts if draft["criterion"] == criterion] for criterion in RUBRIC}
    records = []
    for reconciliation in reconciliations:
        criterion = reconciliation["criterion"]
        criterion_drafts = grouped[criterion]
        positions = [draft["score"] for draft in criterion_drafts]
        insufficient = all(draft["insufficient_evidence"] or not draft["references"] for draft in criterion_drafts)
        proposed = int(reconciliation["proposed_score"])
        supported = proposed in positions or insufficient
        if insufficient:
            score, reason, status = 0, "확인 가능한 근거가 부족해 점수를 확정하지 않습니다.", "insufficient"
        elif supported:
            score, reason, status = proposed, "두 담당 심사자의 초안과 조정 기록에서 확인된 점수입니다.", "supported"
        else:
            score, reason, status = min(positions), "조정 점수가 두 초안에서 지지되지 않아 확인된 위치를 유지합니다.", "unsupported_rejected"
        records.append(_decision_record(criterion, criterion_drafts, reconciliation, score, reason, not insufficient, status))
    return validate_coordinator_decisions(records, drafts, reconciliations)


def run_local_panel(data: dict, repeats: int = 2) -> dict:
    rounds = [judge_once(data) for _ in range(max(1, repeats))]
    judges = {}
    for persona in PERSONAS.values():
        rubric_key = resolve_criterion_key(persona)
        scores = [round_result[rubric_key]["score"] for round_result in rounds]
        result = dict(rounds[0][rubric_key])
        result["rounds"] = scores
        result["spread"] = max(scores) - min(scores)
        if result["spread"] > result["max_score"] * 0.15:
            result["confidence"] = "low"
        judges[rubric_key] = result

    first_round = first_round_assessments(data)
    reconciliation = reconcile_criteria(data)
    final_decisions = finalize_criteria(data, first_round, reconciliation)
    battles = build_battles(judges)
    return {
        "repeats": len(rounds),
        "judges": judges,
        "first_round": first_round,
        "reconciliation": reconciliation,
        "final_decisions": final_decisions,
        "coordinator": dict(COORDINATOR),
        "battles": battles,
        "discussion": build_discussion(data, judges, battles),
    }


def _reference_catalog(data: dict) -> dict[str, list[str]]:
    references = {key: set() for key in RUBRIC}
    submission = data.get("submission", {})
    if submission.get("scenario"):
        references["problem_wow"].add("submission.scenario")

    matches = data.get("static_analysis", {}).get("matches", {})
    for category, values in matches.items():
        if not isinstance(values, list):
            continue
        if category in {"agent_orchestration", "tools", "rag", "multi_agent"}:
            criterion = "ai_implementation"
        elif category in {"golden_dataset", "eval_metric", "eval_signal"}:
            criterion = "operational_quality"
        else:
            continue
        for index, value in enumerate(values[:5]):
            if isinstance(value, dict):
                references[criterion].add(f"static_analysis.matches.{category}[{index}]")

    git = data.get("git_analysis", {})
    for key in ("authors", "timestamps", "commit_count"):
        if git.get(key):
            references["presentation_collaboration"].add(f"git_analysis.{key}")

    browser = data.get("browser") or {}
    for index, step in enumerate(browser.get("steps", [])):
        if isinstance(step, dict):
            reference = f"browser.steps[{index}]"
            references["problem_wow"].add(reference)
            references["completeness"].add(reference)
    for index, _ in enumerate(browser.get("console_errors", [])[:10]):
        references["completeness"].add(f"browser.console_errors[{index}]")
    return {key: sorted(values) for key, values in references.items()}


def _openai_evidence(data: dict) -> dict:
    return {
        "reference_catalog": _reference_catalog(data),
        "submission": data.get("submission", {}),
        "static_analysis": {
            "categories": data.get("static_analysis", {}).get("categories", {}),
            "matches": {key: value[:5] for key, value in data.get("static_analysis", {}).get("matches", {}).items()},
        },
        "git_analysis": data.get("git_analysis", {}),
        "browser": {
            "available": (data.get("browser") or {}).get("available"),
            "steps": [
                {
                    "step": step.get("step"),
                    "text": step.get("text"),
                    "action": step.get("action"),
                    "status": step.get("status"),
                    "error": step.get("error"),
                }
                for step in (data.get("browser") or {}).get("steps", [])
            ],
            "console_errors": (data.get("browser") or {}).get("console_errors", [])[:10],
        },
    }


def build_openai_panel_prompt(data: dict) -> str:
    persona_context = {persona_id: build_persona_prompt_context(persona_id) for persona_id in PERSONAS}
    schema = {
        "judges": {
            persona_id: {
                "score": f"integer 0..{context['max_score']}",
                "confidence": "high|medium|low",
                "insufficient_evidence": "boolean",
                "evidence": [{"claim": "short Korean claim", "reference": "one exact value from EVIDENCE.reference_catalog[primary_criterion]"}],
            }
            for persona_id, context in persona_context.items()
        },
        "discussion": [
            {
                "persona_id": "one scoring persona id",
                "at_seconds": "integer 0..30",
                "side": "left|right|center",
                "kind": "observation|proposal|rebuttal|synthesis",
                "score_after": "integer for a score proposal/rebuttal, otherwise null",
                "reference": "exact allowed reference when score_after is not null, otherwise null",
                "text": "natural Korean dialogue",
            }
        ],
    }
    return f"""You are the lead evaluator for an interactive hackathon leaderboard.
Evaluate the submission using only the supplied evidence. Return valid JSON only.

All five judges are fictional project characters. Do not imitate or mention any real person's appearance, biography,
personality, signature phrase, or actual speech. Persona voice changes wording only and never changes rubric scoring.
Apply every rule in SCORING_INVARIANTS. Every scored claim must cite an exact value from the judge's
EVIDENCE.reference_catalog[primary_criterion]. If valid evidence is missing, set insufficient_evidence=true, state the
gap, and do not invent compensating facts. Every discussion score_after also requires one allowed reference.

Each judge evaluates only primary_criterion. The first 8 seconds contain observations only. Judges may then propose
scores and respond to evidence. A personality, preference, authority, joke, or disagreement is never a scoring reason.
Mention scores naturally as '12점', never '12/20'.

SCORING_INVARIANTS:
{json.dumps(SCORING_INVARIANTS, ensure_ascii=False)}

JUDGES:
{json.dumps(persona_context, ensure_ascii=False)}

COORDINATOR:
{json.dumps(COORDINATOR, ensure_ascii=False)}

EVIDENCE:
{json.dumps(_openai_evidence(data), ensure_ascii=False)}

OUTPUT_SCHEMA:
{json.dumps(schema, ensure_ascii=False)}"""


def build_first_round_prompt(data: dict) -> str:
    """1차 채점(OpenAI) 프롬프트 — 담당 2인 구조로 정확히 10개 평가를 요구한다.

    각 리뷰어는 자신이 배정된 단일 기준만 채점하고, 그 기준의 allowed_references만
    인용한다. run_openai_panel(1:1)과 별개이며, task 9(의견 조정)가 이 초안을 소비한다.
    """
    catalog = _reference_catalog(data)
    reviewers = []
    for criterion, roles in CRITERION_REVIEWERS.items():
        for role in ("primary", "secondary"):
            context = build_persona_prompt_context(roles[role])
            reviewers.append({
                "persona_id": context["id"],
                "display_name": context["display_name"],
                "criterion": criterion,
                "role": role,
                "max_score": int(RUBRIC[criterion]["max_score"]),
                "allowed_references": catalog.get(criterion, []),
                "favored_evidence": context["favored_evidence"],
                "critique_guidance": context["critique_guidance"],
                "prohibited_scoring": context["prohibited_scoring"],
            })
    schema = {
        "assessments": [
            {
                "persona_id": "the reviewer's persona id",
                "criterion": "the reviewer's assigned criterion",
                "role": "primary|secondary",
                "score": "integer 0..max_score for that criterion",
                "confidence": "high|medium|low",
                "insufficient_evidence": "boolean",
                "evidence": [{"claim": "short Korean claim", "reference": "one exact value from that criterion's allowed_references"}],
                "rationale": "short Korean rationale",
            }
        ]
    }
    return f"""You are running stage 1 (independent first-round scoring) of a hackathon judging panel.
Return valid JSON only. Produce exactly one assessment for every entry in REVIEWERS (10 total).

All judges are fictional project characters. Do not imitate or mention any real person. Persona voice changes wording
only and never changes the rubric score. Apply every rule in SCORING_INVARIANTS.
Each reviewer scores ONLY its own assigned criterion — never another criterion. Every scored claim must cite one exact
value from that criterion's allowed_references. If no valid reference supports a score, set insufficient_evidence=true,
state the gap, and do not invent compensating facts. Keep each score within 0..max_score for that criterion.

SCORING_INVARIANTS:
{json.dumps(SCORING_INVARIANTS, ensure_ascii=False)}

REVIEWERS:
{json.dumps(reviewers, ensure_ascii=False)}

EVIDENCE:
{json.dumps(_openai_evidence(data), ensure_ascii=False)}

OUTPUT_SCHEMA:
{json.dumps(schema, ensure_ascii=False)}"""


def build_reconciliation_prompt(data: dict) -> str:
    """의견 조정(OpenAI) 프롬프트 — 기준마다 두 리뷰어의 초안을 맞대어 5개 조정을 요구한다.

    점수 변경은 오직 해당 기준의 allowed_references 근거를 채택·재가중할 때만 허용하며,
    권위·성격·말투·단순 주장으로는 바꿀 수 없다. 근거로 못 좁히면 unresolved=true.
    """
    catalog = _reference_catalog(data)
    pairs = []
    for criterion, roles in CRITERION_REVIEWERS.items():
        pairs.append({
            "criterion": criterion,
            "max_score": int(RUBRIC[criterion]["max_score"]),
            "primary": {"persona_id": roles["primary"], "display_name": PERSONAS[roles["primary"]]["display_name"]},
            "secondary": {"persona_id": roles["secondary"], "display_name": PERSONAS[roles["secondary"]]["display_name"]},
            "allowed_references": catalog.get(criterion, []),
        })
    schema = {
        "reconciliations": [
            {
                "criterion": "the criterion",
                "comparison": "short Korean comparison of the two drafts",
                "challenge": "short Korean challenge citing evidence",
                "rebuttal": "short Korean rebuttal citing evidence",
                "accepted_evidence": ["exact allowed_references kept"],
                "rejected_evidence": ["exact allowed_references dismissed"],
                "proposed_score": "integer 0..max_score for that criterion",
                "proposed_confidence": "high|medium|low",
                "unresolved": "boolean",
            }
        ]
    }
    return f"""You are running stage 2 (per-criterion reconciliation) of a hackathon judging panel.
Return valid JSON only. Produce exactly one reconciliation per PAIRS entry (5 total).

Each criterion has two fictional reviewers (primary, secondary) who scored it independently. Compare their positions
and let them challenge and rebut using evidence only. A score change is valid ONLY when it cites accepted or reweighted
evidence from that criterion's allowed_references — never authority, personality, tone, or a bare assertion. Apply every
rule in SCORING_INVARIANTS. If evidence cannot settle the gap, set unresolved=true. Keep proposed_score within 0..max_score.

SCORING_INVARIANTS:
{json.dumps(SCORING_INVARIANTS, ensure_ascii=False)}

PAIRS:
{json.dumps(pairs, ensure_ascii=False)}

EVIDENCE:
{json.dumps(_openai_evidence(data), ensure_ascii=False)}

OUTPUT_SCHEMA:
{json.dumps(schema, ensure_ascii=False)}"""


def build_coordinator_prompt(data: dict, drafts: list[dict] | None = None, reconciliations: list[dict] | None = None) -> str:
    drafts = drafts if drafts is not None else first_round_assessments(data)
    reconciliations = reconciliations if reconciliations is not None else reconcile_criteria(data)
    schema = {
        "decisions": [{
            "criterion": "one rubric criterion",
            "final_score": "integer 0..max_score",
            "reason": "short Korean evidence-backed reason",
            "evidence_ids": ["exact reference catalog values"],
            "references": ["exact reference catalog values"],
            "decision_trace": ["draft:criterion:primary", "draft:criterion:secondary", "reconciliation:criterion"],
            "evidence_sufficient": "boolean",
            "adjustment": {"status": "supported|unsupported_rejected|insufficient", "supported_by": ["trace id"]},
        }]
    }
    return f"""You are the non-scoring coordinator finalizing a hackathon panel.
Return valid JSON only, with exactly one decision for each of the five criteria.
Inspect only the assigned evidence, the two first-round positions, and the reconciliation record below.
Never add facts, score from personality, or impersonate a scoring judge. A changed score is valid only when it is
one of the supported reviewer positions or cites accepted/reweighted evidence from the allowed reference catalog.
If evidence is insufficient, set final_score to 0, evidence_sufficient to false, and adjustment.status to insufficient.
Every sufficient decision must include at least one exact evidence reference and all decisions must include the three
decision_trace IDs. Keep scores within their rubric maxima.

COORDINATOR:
{json.dumps(COORDINATOR, ensure_ascii=False)}

EVIDENCE:
{json.dumps(_openai_evidence(data), ensure_ascii=False)}

FIRST_ROUND_DRAFTS:
{json.dumps(drafts, ensure_ascii=False)}

RECONCILIATIONS:
{json.dumps(reconciliations, ensure_ascii=False)}

OUTPUT_SCHEMA:
{json.dumps(schema, ensure_ascii=False)}"""


def parse_coordinator_decisions(payload: dict, data: dict, drafts: list[dict] | None = None, reconciliations: list[dict] | None = None) -> list[dict]:
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("coordinator response is missing decisions")
    allowed = {reference for values in _reference_catalog(data).values() for reference in values}
    normalized = []
    for decision in decisions:
        criterion = decision.get("criterion")
        if criterion not in RUBRIC:
            raise ValueError(f"unknown coordinator criterion: {criterion}")
        references = [str(reference).strip() for reference in decision.get("references", []) if str(reference).strip()]
        if any(reference not in allowed for reference in references):
            raise ValueError(f"coordinator returned an unsupported reference for {criterion}")
        trace = [str(value) for value in decision.get("decision_trace", [])]
        normalized.append({
            "criterion": criterion,
            "final_score": int(decision.get("final_score", -1)),
            "max_score": int(RUBRIC[criterion]["max_score"]),
            "reason": str(decision.get("reason", "")).strip(),
            "evidence_ids": references,
            "references": [{"type": "ai_reference", "value": reference} for reference in references],
            "decision_trace": trace,
            "evidence_sufficient": bool(decision.get("evidence_sufficient", False)),
            "adjustment": decision.get("adjustment", {}),
        })
    return validate_coordinator_decisions(normalized, drafts, reconciliations)


def _normalize_ai_evidence(item: dict, allowed_references: set[str]) -> tuple[list[str], list[dict], bool]:
    evidence = []
    references = []
    all_grounded = True
    values = item.get("evidence", []) or []
    if not isinstance(values, list):
        values = [values]
    for value in values:
        if isinstance(value, dict):
            claim = str(value.get("claim", "")).strip()
            reference = str(value.get("reference", "")).strip()
            reference_is_valid = bool(reference) and reference in allowed_references
            if claim and reference_is_valid:
                evidence.append(claim)
                references.append({"type": "ai_reference", "value": reference})
            else:
                all_grounded = False
        elif str(value).strip():
            evidence.append(str(value).strip())
            all_grounded = False
    if not evidence:
        evidence.append("근거 부족")
        all_grounded = False
    return evidence[:5], references[:10], all_grounded


def parse_openai_judge(persona_id: str, item: dict, allowed_references: set[str]) -> tuple[str, dict]:
    persona = PERSONAS[persona_id]
    rubric_key = resolve_criterion_key(persona)
    maximum = criterion_max_score(persona)
    score = max(0, min(maximum, int(item["score"])))
    evidence, references, all_grounded = _normalize_ai_evidence(item, allowed_references)
    confidence = str(item.get("confidence", "medium"))
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    insufficient_evidence = bool(item.get("insufficient_evidence")) or not all_grounded or not references
    if insufficient_evidence:
        confidence = "low"
    if not all_grounded or not references:
        score = 0
    record = _judge_record(persona, {
        "score": score,
        "max_score": maximum,
        "confidence": confidence,
        "evidence": evidence,
        "references": references,
    })
    record.update(rounds=[score], spread=0, insufficient_evidence=insufficient_evidence)
    return rubric_key, record


def _parse_openai_discussion_event(event: dict, reference_catalog: dict[str, list[str]]) -> dict | None:
    persona_id = event.get("persona_id")
    if persona_id not in PERSONAS:
        return None
    persona = PERSONAS[persona_id]
    rubric_key = resolve_criterion_key(persona)
    score_after = event.get("score_after")
    score_snapshot = {}
    references = []
    if score_after is not None:
        reference = str(event.get("reference", "")).strip()
        if reference not in set(reference_catalog.get(rubric_key, [])):
            raise ValueError(f"unsupported discussion score reference: {reference or 'missing'}")
        maximum = criterion_max_score(persona)
        score_snapshot[rubric_key] = max(0, min(maximum, int(score_after)))
        references.append({"type": "ai_reference", "value": reference})
    return {
        "speaker": persona["display_name"],
        "avatar": persona["dialogue_avatar"],
        "role": persona["role"],
        "text": str(event["text"]),
        "at_seconds": max(0, min(30, int(event["at_seconds"]))),
        "kind": event.get("kind", "observation"),
        "side": event.get("side", "left"),
        "judge_key": rubric_key if score_after is not None else None,
        "criterion_key": rubric_key,
        "persona_id": persona_id,
        "references": references,
        "score_snapshot": score_snapshot,
    }


def _openai_json(prompt: str) -> dict:
    body = json.dumps({
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        "reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "medium"),
        "messages": [{"role": "system", "content": "Return valid JSON only."}, {"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urlrequest.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"OpenAI API {exc.code}: {detail}") from exc

    return json.loads(payload["choices"][0]["message"]["content"])


def run_openai_panel(data: dict) -> dict:
    reference_catalog = _reference_catalog(data)
    result = _openai_json(build_openai_panel_prompt(data))
    judges = {}
    for persona_id in PERSONAS:
        criterion = PERSONAS[persona_id]["primary_criterion"]
        allowed_references = set(reference_catalog.get(criterion, []))
        rubric_key, record = parse_openai_judge(persona_id, result["judges"][persona_id], allowed_references)
        judges[rubric_key] = record

    discussion = []
    for event in result.get("discussion", []):
        parsed = _parse_openai_discussion_event(event, reference_catalog)
        if parsed is not None:
            discussion.append(parsed)
    if len(discussion) < 5:
        raise ValueError("OpenAI response contained too few discussion events")
    drafts = first_round_assessments(data)
    reconciliations = reconcile_criteria(data)
    final_decisions = parse_coordinator_decisions(
        _openai_json(build_coordinator_prompt(data, drafts, reconciliations)), data, drafts, reconciliations
    )
    final_scores = {decision["criterion"]: decision["final_score"] for decision in final_decisions}
    discussion.sort(key=lambda event: event["at_seconds"])
    discussion.append({
        "speaker": COORDINATOR["display_name"],
        "avatar": COORDINATOR["fallback_avatar"],
        "role": COORDINATOR["role"],
        "text": "제출물에서 확인한 근거와 각 담당자의 판단만 사용해 이 점수로 확정합니다.",
        "at_seconds": 29,
        "kind": "final",
        "side": "center",
        "finalized": True,
        "score_snapshot": final_scores,
    })
    return {
        "repeats": 1,
        "provider": "openai",
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        "reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "medium"),
        "judges": judges,
        "coordinator": dict(COORDINATOR),
        "first_round": drafts,
        "reconciliation": reconciliations,
        "final_decisions": final_decisions,
        "battles": build_battles(judges),
        "discussion": discussion,
    }


def build_discussion(data: dict, judges: dict[str, dict], battles: list[dict[str, str]]) -> list[dict]:
    del battles
    keys = [resolve_criterion_key(persona) for persona in PERSONAS.values()]
    current = {key: judges[key]["score"] for key in keys}
    submission = data.get("submission", {})
    scenario = submission.get("scenario", "제출된 데모 흐름")
    browser = data.get("browser") or {}
    browser_steps = browser.get("steps", [])
    successful_steps = sum(step.get("status") == "success" for step in browser_steps)
    executed_steps = sum(step.get("status") in {"success", "failed"} for step in browser_steps)

    def observed_evidence(key: str) -> str:
        item = judges[key]
        if key == resolve_criterion_key(PERSONAS["vc_investor"]):
            return f"제출 시나리오 ‘{scenario}’는 확인했습니다. 문제의 차별성은 추가 비교 근거가 필요합니다."
        if key == resolve_criterion_key(PERSONAS["staff_engineer"]):
            if not executed_steps:
                return "실행된 브라우저 단계가 없어 동작을 확인할 수 없습니다."
            errors = len(browser.get("console_errors", []))
            return f"실행 가능한 단계 {executed_steps}개 중 {successful_steps}개가 성공했고 콘솔 오류는 {errors}건 기록됐습니다."
        if key == resolve_criterion_key(PERSONAS["open_source_maintainer"]):
            refs = item.get("references", [])
            ref = next((value for value in refs if isinstance(value, dict) and value.get("type") == "code"), None)
            if ref:
                return f"{ref.get('file', '코드')} {ref.get('line', '?')}줄의 신호를 확인했습니다. 실제 결과 연결 여부는 이 근거 범위에서만 판단합니다."
            return "AI 기능의 실제 호출 경로를 가리키는 코드 참조가 없습니다."
        if key == resolve_criterion_key(PERSONAS["evaluation_reviewer"]):
            static = data.get("static_analysis", {})
            categories = static.get("categories", {})
            detected = [signal for signal in ("golden_dataset", "eval_metric", "eval_signal") if categories.get(signal)]
            code_ref = next(
                (value for value in item.get("references", []) if isinstance(value, dict) and value.get("type") == "code"),
                None,
            )
            if detected and code_ref:
                return f"{', '.join(detected)} 평가 신호와 {code_ref.get('file', '코드')} {code_ref.get('line', '?')}줄 근거를 확인했습니다."
            if detected:
                return f"{', '.join(detected)} 평가 신호는 탐지됐지만 구체적인 파일·줄 참조는 없습니다."
            informational = [signal for signal in ("monitoring", "guardrails") if categories.get(signal)]
            if informational:
                return f"{', '.join(informational)}는 참고 정보이며 운영품질 점수 근거로 사용하지 않습니다."
            return "golden_dataset·eval_metric·eval_signal 근거가 확인되지 않았습니다."
        refs = item.get("references", [])
        git_ref = next((value for value in refs if isinstance(value, dict) and value.get("type") == "git"), None)
        authors = git_ref.get("authors", {}) if git_ref else {}
        return f"Git 기록에서 확인되는 작성자는 {len(authors)}명입니다. 발표 역할은 이 기록과 일치하는 범위에서만 인정하겠습니다."

    persona_by_key = {resolve_criterion_key(persona): persona for persona in PERSONAS.values()}
    events = []

    def add(key: str, text: str, at: int, kind: str = "observation", side: str = "left") -> None:
        persona = persona_by_key[key]
        event = {
            "speaker": persona["display_name"],
            "avatar": persona["dialogue_avatar"],
            "role": persona["role"],
            "text": text,
            "at_seconds": at,
            "kind": kind,
            "side": side,
            "criterion_key": key,
            "persona_id": persona["id"],
            "score_snapshot": {},
        }
        if kind in {"proposal", "rebuttal"}:
            event["judge_key"] = key
            event["score_snapshot"] = {key: current[key]}
        events.append(event)

    problem_key = resolve_criterion_key(PERSONAS["vc_investor"])
    implementation_key = resolve_criterion_key(PERSONAS["open_source_maintainer"])
    completeness_key = resolve_criterion_key(PERSONAS["staff_engineer"])
    operations_key = resolve_criterion_key(PERSONAS["evaluation_reviewer"])
    collaboration_key = resolve_criterion_key(PERSONAS["it_creator"])

    add(problem_key, observed_evidence(problem_key), 0, side="left")
    add(completeness_key, observed_evidence(completeness_key), 2, side="right")
    add(implementation_key, observed_evidence(implementation_key), 4, side="left")
    add(operations_key, observed_evidence(operations_key), 6, side="right")
    add(collaboration_key, observed_evidence(collaboration_key), 8, side="left")
    add(problem_key, f"확인한 문제와 데모 근거를 기준으로 {judges[problem_key]['score']}점을 제안합니다.", 10, "proposal", "left")
    add(completeness_key, f"브라우저 실행 기록만 반영해 {judges[completeness_key]['score']}점을 제안합니다.", 12, "proposal", "right")
    add(implementation_key, f"코드에서 확인되는 호출 신호만 반영해 {judges[implementation_key]['score']}점을 제안합니다.", 14, "proposal", "left")
    add(operations_key, f"현재 런타임이 수집한 운영 근거 범위에서 {judges[operations_key]['score']}점을 제안합니다. 골든 데이터셋 평가 근거 여부는 별도로 명시합니다.", 16, "proposal", "right")
    add(collaboration_key, f"Git 기록으로 확인되는 협업 범위에서 {judges[collaboration_key]['score']}점을 제안합니다.", 18, "proposal", "left")
    add(problem_key, "동작 성공은 문제 해결의 근거가 될 수 있지만 차별성을 자동으로 증명하지는 않습니다. 담당 점수를 유지합니다.", 20, "rebuttal", "left")
    add(implementation_key, "키워드 탐지는 출발점일 뿐입니다. 실제 연결이 확인되지 않은 부분은 가점하지 않고 담당 점수를 유지합니다.", 22, "rebuttal", "right")
    add(operations_key, "정상 실행만으로 골든 데이터셋과 평가 품질이 증명되지는 않습니다. 담당 점수를 유지합니다.", 24, "rebuttal", "right")
    events.append({
        "speaker": COORDINATOR["display_name"],
        "avatar": COORDINATOR["fallback_avatar"],
        "role": COORDINATOR["role"],
        "text": "각 담당자가 제시한 근거와 점수의 연결을 확인했습니다. 새로운 기준이나 추정은 추가하지 않습니다.",
        "at_seconds": 26,
        "kind": "synthesis",
        "side": "center",
        "score_snapshot": dict(current),
    })
    events.append({
        "speaker": COORDINATOR["display_name"],
        "avatar": COORDINATOR["fallback_avatar"],
        "role": COORDINATOR["role"],
        "text": "패널이 제출물에서 확인한 근거에 따라 이 점수로 확정합니다.",
        "at_seconds": 29,
        "kind": "final",
        "side": "center",
        "finalized": True,
        "score_snapshot": {key: judges[key]["score"] for key in keys},
    })
    return events


def build_battles(judges: dict[str, dict]) -> list[dict[str, str]]:
    if len(judges) < 2:
        return []
    ordered = list(judges.items())
    battles = []
    for left_key, left in ordered:
        for right_key, right in ordered:
            if left_key >= right_key:
                continue
            left_ratio = left["score"] / left["max_score"]
            right_ratio = right["score"] / right["max_score"]
            if abs(left_ratio - right_ratio) < 0.5:
                continue
            battles.append({
                "left": f"{left['persona']} · {left['score']}/{left['max_score']}",
                "right": f"{right['persona']} · {right['score']}/{right['max_score']}",
                "transcript": f"{left['persona']}: {left['memo']}\n{right['persona']}: {right['memo']}\n두 평가는 담당 항목이 다르므로 각 근거를 유지합니다.",
            })
    return battles
