from __future__ import annotations

import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

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
        "role": "VC 투자자 · 문제·Wow",
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
        "role": "오픈소스 메인테이너 · AI 기능 구현",
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
        "role": "글로벌 테크 Staff Engineer · 동작 완성도",
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
        "role": "AI 평가·논문 리뷰어 · 운영 품질",
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
        "role": "IT 콘텐츠 크리에이터 · 발표 협업",
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

    battles = build_battles(judges)
    return {
        "repeats": len(rounds),
        "judges": judges,
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


def run_openai_panel(data: dict) -> dict:
    prompt = build_openai_panel_prompt(data)
    reference_catalog = _reference_catalog(data)
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

    content = payload["choices"][0]["message"]["content"]
    result = json.loads(content)
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
        "score_snapshot": {key: judge["score"] for key, judge in judges.items()},
    })
    return {
        "repeats": 1,
        "provider": "openai",
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        "reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "medium"),
        "judges": judges,
        "coordinator": dict(COORDINATOR),
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
