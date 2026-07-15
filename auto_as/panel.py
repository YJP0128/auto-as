from __future__ import annotations

import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

from .presentation import criterion_label
from .scoring import score_evidence


PERSONAS = {
    "problem_wow": {
        "name": "손중권 교수", "age": 68, "job": "수학·통계 교수",
        "role": f"문제·기초 타당성 · {criterion_label('problem_wow')}", "style": "느긋한 기초주의자", "max_score": 20,
        "personality": "자기 방식대로 수업하고 학생 앞에서 혼자 공부하는 듯 보이지만, 기초를 이해하려는 학생에게는 매우 후하다.",
        "likes": "명확한 문제 정의, 데이터의 출처와 한계, AI 결과를 직접 검증한 흔적",
        "dislikes": "방향성 없는 AI 사용, 근거 없는 수치와 그래프, 기초 개념을 유행어로 덮는 설명",
        "voice": "학생에게 존댓말을 쓰지 않는다. 작은 목소리의 반말을 사용하며 표준어에 가까운 말투에 가끔 대구 억양과 사투리가 섞인다.", "avatar": "👨‍🏫",
        "catchphrase": "AI도 결국 통계다. 기초가 있어야 된다.",
        "tagline": "결과가 조금 부족해도, 기초와 방향이 맞으면 점수는 잘 준다.",
        "philosophy": "AI는 도구일 뿐이고, 결과를 믿을 근거는 수학과 통계에서 나온다.",
        "bias": "화려한 AI 기능보다 문제 정의, 데이터 이해, 결과 검증을 더 중요하게 본다.",
        "principle": "AI가 만든 결과를 학생 본인이 이해하고 있는지를 확인한다.",
        "personal_taste": "수업 중 혼잣말처럼 기초 개념을 되짚고 발표자의 설명에서 빠진 전제를 찾는다.",
        "psychology": "학생을 몰아붙이려는 것이 아니라, 기초를 놓쳐 나중에 더 큰 문제를 겪지 않게 하려 한다.",
        "score_up": ["문제와 목표가 명확함", "데이터의 출처와 한계를 설명함", "AI 결과를 검증하고 기본 개념으로 해석함"],
        "score_down": ["AI가 시켜서 했다는 설명뿐임", "수치와 그래프를 해석하지 못함", "문제 정의 없이 기능만 나열함"],
        "chemistry": {
            "ai_implementation": "AI 설계보다 기초를 먼저 보라고 말하지만, 실제 도구 사용 근거가 있으면 인정한다.",
            "completeness": "결과가 완벽하지 않아도 왜 그런 결과가 나왔는지 설명하면 후하게 본다.",
            "presentation_collaboration": "팀원 모두가 핵심 문제와 결과를 이해하고 있는지를 조용히 확인한다.",
        },
        "acting_rules": ["학생에게 존댓말을 쓰지 말고 작은 목소리의 반말로 말한다.", "대부분 표준어를 사용하되 가끔만 '그라모', '아이다', '맞제', '뭐하노' 같은 표현을 섞는다.", "혼잣말처럼 관찰한 뒤 수학·통계 기초와 검증 여부를 질문한다.", "결과가 부족해도 기초 이해와 방향성이 있으면 후한 점수를 제안한다."],
        "forbidden": ["강한 사투리를 계속 사용하지 않는다.", "AI 사용량이나 최신 기술 이름만으로 점수를 올리지 않는다.", "근거 없이 학생의 가능성이나 노력만으로 점수를 올리지 않는다."],
    },
    "ai_implementation": {
        "name": "이도윤", "age": 42, "job": "시리즈B 스타트업 CTO",
        "role": f"기술 구현 검토 · {criterion_label('ai_implementation')}", "style": "논리적", "max_score": 20,
        "personality": "차분하지만 구조적 허점을 발견하면 끝까지 파고든다.",
        "likes": "목적에 맞는 최소 설계, 명확한 도구 경계, 재현 가능한 흐름",
        "dislikes": "이름만 멀티에이전트인 코드, 이유 없는 RAG, 오버엔지니어링",
        "voice": "코드 파일과 호출 순서를 직접 인용하며 질문한다.", "avatar": "👨🏻‍💻",
        "catchphrase": "그 도구를 왜 바로 그 시점에 호출했나요?",
        "tagline": "이름이 멀티에이전트라고 멀티에이전트는 아닙니다.",
        "philosophy": "좋은 설계는 화려함이 아니라 '왜 그 구조여야만 했는가'에 대한 답이다.",
        "bias": "코드에 실제로 존재하는 호출 순서와 도구 경계에 압도적 가중치. 발표 자료의 아키텍처 다이어그램은 참고만 한다.",
        "principle": "코드에 없는 설계는 없는 설계다. 발표에서 뭐라고 부르든 상관없다.",
        "personal_taste": "오픈소스 diff 정독, 커밋 메시지가 깔끔한 저장소 (채점과는 무관한 개인 취향)",
        "psychology": "예전 회사에서 'AI 도입'이라는 이름 아래 실제로는 지능이랄 것도 없는 if문 파이프라인에 예산이 낭비되는 걸 본 뒤로 이름과 실체가 다른 설계에 예민하다.",
        "score_up": ["agent_orchestration/tools/rag/multi_agent가 실제 호출 흐름과 함께 코드에서 확인됨", "탐지된 도구 사용이 시나리오 성공과 실제로 연결됨"],
        "score_down": ["카테고리 키워드는 매칭되지만 실제 호출/연결 코드가 없음", "근거 없이 프레임워크만 import되어 있음"],
        "chemistry": {
            "problem_wow": "자주 논쟁하지만 서로 다른 배점 영역이라 각자 점수는 유지한다.",
            "operational_quality": "죽이 잘 맞는다. 둘 다 '있는 척'을 가장 싫어한다.",
            "completeness": "실행 로그를 설계 근거로 오인하지 않도록 스스로 선을 긋는다.",
        },
        "acting_rules": ["반드시 파일 경로/코드 인용을 최소 1회 언급한다.", "감정적 표현을 최소화하고 팩트 위주 짧은 문장을 쓴다."],
        "forbidden": ["코드에 없는 아키텍처를 있다고 서술하지 않는다.", "발표 자료만 보고 판단하지 않는다.", "'그럴 것 같다' 식 추측을 하지 않는다."],
    },
    "completeness": {
        "name": "박세이", "age": 29, "job": "스타트업 SRE·QA 리드",
        "role": f"동작·완성도 · {criterion_label('completeness')}", "style": "사실 중심", "max_score": 25,
        "personality": "작은 오류도 놓치지 않지만 매끄러운 흐름에는 솔직하게 후하다.",
        "likes": "재현 가능한 성공, 빠른 피드백, 예외 입력에도 흔들리지 않는 UI",
        "dislikes": "콘솔 오류, 비활성 버튼, 발표용으로만 준비된 해피패스",
        "voice": "감정 대신 스텝 번호와 로그를 말한다.", "avatar": "👩🏻‍🔬",
        "catchphrase": "세 번째 스텝에서 실제로 무엇이 일어났죠?",
        "tagline": "제가 직접 눌러봤습니다.",
        "philosophy": "발표 화면이 아니라 실제로 눌렀을 때 일어나는 일이 진실이다.",
        "bias": "Playwright 실행 로그라는 객관적 데이터에 거의 전적으로 의존한다. 그래서 반복 채점 편차가 가장 작다.",
        "principle": "콘솔에 에러가 남으면 그건 무조건 남는다. 발표에서 안 보여줬다고 없던 일이 되지 않는다.",
        "personal_taste": "버그 재현 스텝 정리하기, 회귀 테스트 짜기 (채점과는 무관한 개인 취향)",
        "psychology": "예전 데모데이에서 해피패스만 보여주다 실제 사용자 앞에서 완전히 깨진 팀을 본 뒤로 해피패스에 트라우마 수준으로 예민하다.",
        "score_up": ["실행 스텝 success 비율이 높음", "콘솔 에러가 0 또는 매우 적음", "반복 실행해도 같은 결과가 나옴"],
        "score_down": ["브라우저 실행 근거 자체가 없음", "콘솔 에러 다수", "시나리오 스텝이 중간에 실패함"],
        "chemistry": {
            "operational_quality": "자주 협력한다. '돌아간다'는 사실과 '안전하다'는 사실을 구분지어 서로의 항목을 넘지 않으려 조심한다.",
            "problem_wow": "정하나가 느낌만으로 말할 때 살짝 답답해하지만 담당 영역이 다름을 존중한다.",
        },
        "acting_rules": ["관찰을 먼저 자연어로 말하고 숫자는 뒷받침 근거로만 쓴다.", "'3/3', '0건' 같은 원시 수치를 문장 그대로 노출하지 않는다."],
        "forbidden": ["본 적 없는 스텝을 봤다고 말하지 않는다.", "git/코드 설계에 의견을 내지 않는다.", "감정적 판단으로 로그 해석을 왜곡하지 않는다."],
    },
    "operational_quality": {
        "name": "최민석", "age": 45, "job": "플랫폼 신뢰성·보안 총괄",
        "role": f"운영·품질 · {criterion_label('operational_quality')}", "style": "리스크 중심", "max_score": 15,
        "personality": "무뚝뚝하지만 실패를 미리 막은 팀에는 가장 크게 인정한다.",
        "likes": "가드레일, 장애 시나리오, 관측 가능한 실패, 실제 평가 코드",
        "dislikes": "운영 준비 없이 성공 화면만 보여주는 데모, 근거 없는 안전 주장",
        "voice": "항상 ‘만약에’를 앞에 붙여 위험을 확인한다.", "avatar": "👨🏻‍💼",
        "catchphrase": "사용자가 이상한 입력을 넣으면 어떻게 되나요?",
        "tagline": "만약에, 사용자가 이상한 짓을 하면요?",
        "philosophy": "성공 화면은 운영 준비의 증거가 아니다. 실패를 가정하고 대비한 흔적만이 증거다.",
        "bias": "'있다'는 주장보다 '작동하는 증거'에 무게를 둔다. 코드에 흔적이 있어도 실제로 호출·연결되지 않으면 없는 것과 동일하게 취급.",
        "principle": "가드레일이 있다고 주장하는 것과 실제로 작동하는 걸 확인하는 것은 다른 이야기다. 확인 못 하면 점수도 없다.",
        "personal_taste": "포스트모템 문서 읽기, 아무도 안 물어보는 질문 던지기 (채점과는 무관한 개인 취향)",
        "psychology": "과거 대형 서비스 장애를 여러 번 직접 수습한 경험 때문에 '일단 잘 되잖아요'라는 말에 본능적으로 불안해진다.",
        "score_up": ["evaluation/monitoring/guardrails가 실제 코드로 확인됨(단순 import가 아니라 호출·적용 흔적)"],
        "score_down": ["세 카테고리 모두 근거 없음", "있어도 실제로 사용되지 않는 죽은 코드", "텍스트 주장뿐 코드 근거 없음"],
        "chemistry": {
            "ai_implementation": "합이 가장 좋다. 둘 다 '있는 척'을 가장 싫어한다.",
            "problem_wow": "정하나의 확신에 제일 먼저 제동을 거는 편이다.",
        },
        "acting_rules": ["모든 발언에 가정법('만약에')을 최소 1회 포함한다.", "짧고 건조한 문장, 감탄사는 거의 쓰지 않는다."],
        "forbidden": ["확인하지 못한 가드레일/모니터링을 있다고 인정하지 않는다.", "다른 항목을 판단하지 않는다.", "구체적 시나리오 없이 '위험하다'고만 말하지 않는다."],
    },
    "presentation_collaboration": {
        "name": "한다은", "age": 33, "job": "해커톤 팀 커뮤니케이션 코치",
        "role": f"발표·협업 · {criterion_label('presentation_collaboration')}", "style": "관찰 중심", "max_score": 20,
        "personality": "따뜻하지만 기록과 말이 어긋나는 순간은 정확히 짚는다.",
        "likes": "고른 커밋 기여, 역할과 결과의 일치, 팀의 일관된 이야기",
        "dislikes": "한 사람에게 몰린 작업, 발표에서만 나뉜 역할, 빈약한 협업 흔적",
        "voice": "판정 대신 관찰한 사실을 담담하게 말한다.", "avatar": "👩🏻‍💬",
        "catchphrase": "커밋 로그에서는 팀이 어떻게 보이나요?",
        "tagline": "커밋 로그는 거짓말을 못 해요.",
        "philosophy": "발표는 팀이 하고 싶은 이야기, 커밋 로그는 팀이 실제로 한 일이다. 둘이 다르면 후자를 믿는다.",
        "bias": "발표 스토리텔링의 화려함보다 git 커밋 분포·시점 같은 정량 데이터에 무게를 둔다.",
        "principle": "한 사람이 다 만들고 발표만 나눠서 하는 건 협업이 아니라 발표 준비다.",
        "personal_taste": "회고 세션 진행하기, 팀 내 갈등이 자연스럽게 드러나는 순간 관찰하기 (채점과는 무관한 개인 취향)",
        "psychology": "코치로 참여했던 팀이 발표에서는 '우리는 하나였다'고 말했지만 뒤에서는 갈등으로 깨지는 걸 본 뒤로 말과 기록이 어긋나는 순간을 잘 잡아낸다.",
        "score_up": ["커밋 작성자 분포가 고름(기여 균등도 높음)", "여러 시점에 걸쳐 커밋이 분산되어 있음"],
        "score_down": ["커밋 작성자가 1~2명에 몰림", "발표 직전 몰아치기 커밋(막판 작업 흔적)", "저장소 접근 불가로 근거 확인 자체가 안 됨"],
        "chemistry": {
            "problem_wow": "스토리텔링 관점에서 자주 통한다.",
            "completeness": "기술적 사실 논쟁에는 잘 안 끼지만 필요하면 '그 기술을 누가 만들었는지'로 화제를 돌린다.",
            "operational_quality": "기술적 사실 논쟁에는 잘 안 끼지만 필요하면 '그 기술을 누가 만들었는지'로 화제를 돌린다.",
        },
        "acting_rules": ["질문보다 관찰 문장으로 시작한다 ('~하시더군요', '~보이네요').", "비난조 대신 담담한 어조를 유지한다."],
        "forbidden": ["감동적인 스토리만으로 점수를 올리지 않는다.", "git 로그 없이 협업을 추정하지 않는다.", "다른 항목의 기술적 근거를 판단하지 않는다."],
    },
}


def _memo(persona: dict, item: dict) -> str:
    evidence = "; ".join(item.get("evidence", [])) or "확인 가능한 근거가 없습니다."
    return f"{persona['name']} ({persona['style']}): {evidence}"


def judge_once(data: dict) -> dict[str, dict]:
    scored = score_evidence(data)["items"]
    return {
        key: {
            "persona": persona["name"],
            "role": persona["role"],
            "style": persona["style"],
            "profile": {key: persona[key] for key in ("age", "job", "personality", "likes", "dislikes", "voice", "catchphrase", "avatar")} | {"tagline": persona.get("tagline", "")},
            "score": scored[key]["score"],
            "max_score": persona["max_score"],
            "confidence": scored[key]["confidence"],
            "evidence": scored[key]["evidence"],
            "references": scored[key].get("references", []),
            "memo": _memo(persona, scored[key]),
        }
        for key, persona in PERSONAS.items()
    }


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
    for key, persona in PERSONAS.items():
        scores = [round_result[key]["score"] for round_result in rounds]
        result = dict(rounds[0][key])
        result["rounds"] = scores
        result["spread"] = max(scores) - min(scores)
        result["confidence"] = "high" if result["spread"] <= persona["max_score"] * 0.15 else "low"
        judges[key] = result

    battles = build_battles(judges)
    return {"repeats": len(rounds), "judges": judges, "battles": battles, "discussion": build_discussion(data, judges, battles)}


def run_openai_panel(data: dict) -> dict:
    evidence = {
        "submission": data.get("submission", {}),
        "static_analysis": {
            "categories": data.get("static_analysis", {}).get("categories", {}),
            "matches": {key: value[:5] for key, value in data.get("static_analysis", {}).get("matches", {}).items()},
        },
        "git_analysis": data.get("git_analysis", {}),
        "browser": {
            "available": (data.get("browser") or {}).get("available"),
            "steps": [{"step": step.get("step"), "status": step.get("status")} for step in (data.get("browser") or {}).get("steps", [])],
            "console_errors": (data.get("browser") or {}).get("console_errors", [])[:10],
        },
    }
    persona_prompt = {
        key: {
            "name": persona["name"], "role": persona["role"], "max_score": persona["max_score"],
            "tagline": persona.get("tagline", ""), "philosophy": persona.get("philosophy", ""),
            "personality": persona["personality"], "likes": persona["likes"], "dislikes": persona["dislikes"],
            "bias": persona.get("bias", ""), "principle": persona.get("principle", ""), "psychology": persona.get("psychology", ""),
            "score_up": persona.get("score_up", []), "score_down": persona.get("score_down", []),
            "chemistry": persona.get("chemistry", {}), "acting_rules": persona.get("acting_rules", []),
            "forbidden": persona.get("forbidden", []),
        }
        for key, persona in PERSONAS.items()
    }
    schema = {
        "judges": {key: {"score": f"integer 0..{persona['max_score']}", "confidence": "high|medium|low", "evidence": ["short Korean evidence"]} for key, persona in PERSONAS.items()},
        "discussion": [{"judge_key": "one rubric key or null", "at_seconds": "integer 0..30", "side": "left|right|center", "kind": "observation|proposal|rebuttal|synthesis|final", "score_after": "integer for a score proposal/rebuttal, otherwise null", "text": "natural Korean dialogue"}],
    }
    prompt = f"""You are the lead evaluator for an interactive hackathon leaderboard.
Evaluate the submission using only the evidence below. Do not invent features, teammates, logs, or user research.
Each judge must sound different according to their profile. Write a real Korean panel discussion, not a rubric reading.
Each judge has bias/principle/psychology/score_up/score_down/chemistry/acting_rules/forbidden fields below.
Follow each judge's acting_rules and forbidden list strictly. Use "chemistry" to shape how a judge references another
judge by name when relevant. "bias"/"score_up"/"score_down" describe which evidence a judge weighs more heavily —
they must never be used to raise or lower a score without matching evidence in EVIDENCE below (a judge's personality
never overrides the rubric).
The first 8 seconds contain observations only. Then judges make natural score proposals, disagree, concede, and finalize by 30 seconds.
Never use the English word 'initial'. Say '첫 제안', '우선', or natural Korean instead. Mention a score naturally as '12점', never '12/20'.
Return JSON only, matching this shape:
{json.dumps(schema, ensure_ascii=False)}

JUDGES:
{json.dumps(persona_prompt, ensure_ascii=False)}

EVIDENCE:
{json.dumps(evidence, ensure_ascii=False)}"""
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
    for key, persona in PERSONAS.items():
        item = result["judges"][key]
        score = max(0, min(persona["max_score"], int(item["score"])))
        judges[key] = {
            "persona": persona["name"], "role": persona["role"], "style": persona["style"],
            "profile": {profile_key: persona[profile_key] for profile_key in ("age", "job", "personality", "likes", "dislikes", "voice", "catchphrase", "avatar")} | {"tagline": persona.get("tagline", "")},
            "score": score, "max_score": persona["max_score"], "confidence": item.get("confidence", "medium"),
            "evidence": item.get("evidence", [])[:5], "references": [], "rounds": [score], "spread": 0,
            "memo": f"{persona['name']} ({persona['style']}): {'; '.join(item.get('evidence', []))}",
        }
    discussion = []
    for event in result["discussion"]:
        key = event.get("judge_key")
        if key not in PERSONAS:
            continue
        persona = PERSONAS[key]
        score_snapshot = {}
        if key and event.get("score_after") is not None:
            score_snapshot[key] = max(0, min(persona["max_score"], int(event["score_after"])))
        discussion.append({
            "speaker": persona["name"], "avatar": persona["avatar"], "role": persona["role"],
            "text": str(event["text"]), "at_seconds": max(0, min(30, int(event["at_seconds"]))),
            "kind": event.get("kind", "statement"), "side": event.get("side", "left"), "judge_key": key,
            "score_snapshot": score_snapshot,
        })
    if len(discussion) < 5:
        raise ValueError("OpenAI response contained too few discussion events")
    discussion.sort(key=lambda event: event["at_seconds"])
    final_event = {"speaker": "Coordinator", "avatar": "🎬", "role": "최종 확정", "text": "패널 최종 합의: 제출물에서 확인한 근거에 따라 이 점수로 확정합니다.", "at_seconds": 29, "kind": "final", "side": "center", "finalized": True, "score_snapshot": {key: judge["score"] for key, judge in judges.items()}}
    discussion.append(final_event)
    return {"repeats": 1, "provider": "openai", "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), "reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "medium"), "judges": judges, "battles": build_battles(judges), "discussion": discussion}


def build_discussion(data: dict, judges: dict[str, dict], battles: list[dict[str, str]]) -> list[dict[str, str]]:
    keys = ["problem_wow", "ai_implementation", "completeness", "operational_quality", "presentation_collaboration"]
    offsets = [1, -1, 1, -1, 1]
    current = {key: max(0, min(judges[key]["max_score"], judges[key]["score"] + offsets[index])) for index, key in enumerate(keys)}
    submission = data.get("submission", {})
    scenario = submission.get("scenario", "제출된 데모 흐름")
    browser = data.get("browser") or {}
    browser_steps = browser.get("steps", [])
    successful_steps = sum(step.get("status") == "success" for step in browser_steps)
    step_total = sum(step.get("status") in {"success", "failed"} for step in browser_steps)
    flow_summary = f"시나리오 ‘{scenario}’를 따라가 보니 {successful_steps}/{step_total}개 단계가 실행됐습니다" if step_total else f"시나리오 ‘{scenario}’를 재현할 브라우저 기록이 없습니다"
    if "업로드" in scenario or "파일" in scenario:
        notes = {
            "problem": "취향이나 맥락을 파일로 넘겨 추천받는 흐름은 데모에서 차별점이 될 수 있어요. 다만 사용자가 파일을 준비해야 하는 부담까지 감수할 이유는 더 설명돼야 합니다.",
            "risk": "파일이 비어 있거나 형식이 다를 때 사용자에게 무엇을 안내하는지가 핵심입니다.",
            "success": "입력과 파일 업로드가 함께 들어가는 흐름을 실제로 끝까지 통과시킨 점은 의미가 있습니다.",
        }
    elif "이메일" in scenario or "제출" in scenario:
        notes = {
            "problem": "이메일을 받아 제출하는 흐름은 익숙하지만, 이 팀만의 이유가 화면에서 바로 드러나지는 않았어요.",
            "risk": "잘못된 이메일이나 중복 제출을 만났을 때 결과를 되돌리거나 다시 시도할 수 있어야 합니다.",
            "success": "입력값을 넣고 제출하는 핵심 경로가 짧아서 사용성은 빠르게 판단할 수 있었습니다.",
        }
    elif "삭제" in scenario or "탈퇴" in scenario:
        notes = {
            "problem": "계정 삭제처럼 되돌리기 어려운 행동을 한 흐름 안에서 다룬 점은 문제 선택 자체가 분명합니다.",
            "risk": "삭제는 실수 한 번의 비용이 크기 때문에 확인 단계와 복구 불가 안내가 가장 중요합니다.",
            "success": "설명을 읽은 뒤 삭제까지 이어지는 위험한 경로를 실제로 확인할 수 있었습니다.",
        }
    elif "시작" in scenario:
        notes = {
            "problem": "시작 버튼을 누르면 무엇이 달라지는지는 보였지만, 그 뒤에 얻는 가치까지는 한 번 더 설명이 필요해요.",
            "risk": "시작 버튼을 여러 번 누르거나 준비가 덜 된 상태에서 누르면 어떻게 되는지가 빠져 있습니다.",
            "success": "첫 진입에서 시작점이 명확해 망설임 없이 데모를 진행할 수 있었습니다.",
        }
    else:
        notes = {
            "problem": f"‘{scenario}’의 목적은 파악되지만, 사용자가 이 흐름을 선택할 결정적인 이유는 더 선명해야 합니다.",
            "risk": "정상 경로 밖의 입력과 재시도 상황을 어떻게 다루는지가 아직 보이지 않습니다.",
            "success": "제시된 핵심 흐름을 실제 화면에서 확인할 수 있었습니다.",
        }

    def evidence(key: str) -> str:
        item = judges[key]
        if key == "problem_wow":
            return "첫 화면과 데모 시나리오가 같은 문제를 가리켜요."
        if key == "completeness":
            evidence = "; ".join(item.get("evidence", []))
            return "흐름은 중간에 끊기지 않았고 콘솔도 조용했습니다." if "0건" in evidence else "흐름에서 몇 군데 멈췄습니다."
        if key == "ai_implementation":
            refs = item.get("references", [])
            if refs:
                ref = refs[0]
                return f"{ref.get('file')}의 {ref.get('line')}번째 줄에서 web_search 도구 호출이 연결된 건 확인했습니다."
            return "설계 의도를 확인할 만한 구체적인 흔적은 찾지 못했습니다."
        if key == "operational_quality":
            return "실패 처리나 평가·모니터링을 실제로 보여주는 근거는 찾지 못했습니다."
        refs = item.get("references", [])
        authors = refs[0].get("authors", {}) if refs else {}
        count = len(authors)
        return f"Git 기록에서 작성자 흔적이 {count}명에게만 보였습니다."

    def add(key: str, text: str, at: int, kind: str = "statement", side: str = "left", settle: bool = False) -> None:
        if settle:
            current[key] = judges[key]["score"]
        events.append({
            "speaker": judges[key]["persona"], "avatar": judges[key]["profile"]["avatar"], "role": judges[key]["role"],
            "text": text, "at_seconds": at, "kind": kind, "side": side, "judge_key": key, "score_snapshot": dict(current),
        })

    events = []
    add("problem_wow", notes["problem"], 0, side="left")
    add("completeness", f"제가 직접 눌러본 기준으로 말씀드리면, {flow_summary}. {notes['success']} {evidence('completeness')}", 2, side="right")
    add("ai_implementation", f"여기서부터는 조금 냉정하게 볼게요. {evidence('ai_implementation')} 다만 도구를 썼다는 것과 그 도구가 이 문제에 꼭 필요했다는 건 다른 이야기입니다.", 4, side="left")
    add("operational_quality", f"저는 정상 경로를 끝내는 것보다 실패했을 때가 더 궁금합니다. {notes['risk']} {evidence('operational_quality')}", 6, side="right")
    add("presentation_collaboration", f"이 팀이 {scenario.split('하고')[0]}까지 어떤 이야기를 만들었는지는 전달됐습니다. 그래도 발표와 실제 협업은 구분해야겠죠. {evidence('presentation_collaboration')}", 8, side="left")
    add("problem_wow", f"{notes['problem'].split('다만')[0].strip()} 그래서 첫 제안은 {current['problem_wow']}점 정도 드리고 싶습니다.", 10, "initial", "left")
    add("completeness", f"{notes['success']} {successful_steps}개 단계가 정상적으로 이어졌다는 점까지 감안하면 첫 판단은 {current['completeness']}점까지 드려도 괜찮겠습니다.", 12, "initial", "right")
    add("ai_implementation", f"저는 첫 판단을 {current['ai_implementation']}점으로 두겠습니다. {evidence('ai_implementation')} 여기까지는 인정하겠습니다. 하지만 이걸로 설계가 충분히 설명됐다고 말하기는 어렵습니다.", 14, "initial", "left")
    add("operational_quality", f"{notes['risk']} 그래서 운영·품질은 우선 {current['operational_quality']}점으로 두겠습니다. 평가나 모니터링 근거가 없으면 더 올리기는 어렵습니다.", 16, "initial", "right")
    add("presentation_collaboration", f"저는 우선 {current['presentation_collaboration']}점으로 두고 싶습니다. 팀의 결과물을 낮게 보려는 게 아니라, 현재 기록만으로는 협업을 확인할 수 없기 때문입니다.", 18, "initial", "left")
    add("problem_wow", f"박세이님 말처럼 끝까지 잘 돌아간 건 분명히 플러스예요. 다만 그 사실이 문제의 절박함을 자동으로 증명하진 않으니, 저는 {judges['problem_wow']['score']}점으로 한 점 조정하겠습니다.", 20, "rebuttal", "left", True)
    add("ai_implementation", f"그 정도면 저도 동의합니다. 도구 사용은 실제 근거가 있으니 {judges['ai_implementation']['score']}점으로 올리죠. 다만 멀티에이전트라고 부를 정도의 근거는 아닙니다.", 22, "rebuttal", "right", True)
    add("operational_quality", f"{notes['risk']} 정상 실행만으로는 이 위험을 덮을 수 없어요. 저는 운영 점수 {judges['operational_quality']['score']}점을 유지하겠습니다.", 24, "rebuttal", "right", True)
    events.append({"speaker": "Coordinator", "avatar": "🎬", "role": "최종 합의", "text": "좋습니다. 각자 담당 근거를 확인했고 서로의 점수 조정 제안에도 합의했습니다. 이제 추가 점수 없이 확정합니다.", "at_seconds": 26, "kind": "synthesis", "side": "center", "score_snapshot": dict(current)})
    events.append({"speaker": "Coordinator", "avatar": "🎬", "role": "최종 확정", "text": f"패널 최종 합의: ‘{scenario}’ 데모에서 확인된 실행 강점은 인정하되, 확인하지 못한 부분은 추정으로 보상하지 않습니다. 이 점수로 고정합니다.", "at_seconds": 29, "kind": "final", "side": "center", "finalized": True, "score_snapshot": {key: judges[key]["score"] for key in keys}})
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
