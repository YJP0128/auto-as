from __future__ import annotations

import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest

from .scoring import score_evidence


PERSONAS = {
    "problem_wow": {
        "name": "정하나", "age": 38, "job": "AI 스타트업 시드 투자자",
        "role": "문제·Wow", "style": "직설적", "max_score": 20,
        "personality": "참을성은 짧지만 진짜 문제를 발견하면 누구보다 빠르게 몰입한다.",
        "likes": "첫 30초의 명확한 aha moment, 간결한 데모, 실제 사용자 언어",
        "dislikes": "모호한 문제 정의, 기능 나열, 유행어로 포장한 아이디어",
        "voice": "짧은 문장과 날카로운 질문을 쓴다.", "avatar": "👩🏻‍💼",
        "catchphrase": "그래서, 사용자가 지금 당장 왜 필요하죠?",
        "tagline": "3초 안에 감이 안 오면, 나머지는 안 봐도 됩니다.",
        "philosophy": "좋은 문제는 설명이 필요 없다. 화면을 보는 순간 확신이 와야 진짜다.",
        "bias": "데모 첫 30초에 압도적으로 무게를 둔다. 텍스트 설명보다 화면에서 실제로 벌어지는 일을 더 신뢰한다.",
        "principle": "문제 정의가 없는 데모는 아무리 매끄러워도 절반 이상 줄 수 없다.",
        "personal_taste": "에스프레소, 돌려 말하지 않는 피드백 문화 (채점과는 무관한 개인 취향)",
        "psychology": "예전에 투자했던 팀이 완벽한 기술로도 아무도 안 쓰는 문제 때문에 망하는 걸 본 뒤로 문제 정의의 선명함에 유독 예민하다.",
        "score_up": ["시나리오가 구체적인 사용자 맥락을 담고 있음", "핵심 시나리오가 실제로 성공함", "문제 정의가 명시적으로 드러남"],
        "score_down": ["시나리오가 추상적 진술뿐임", "데모가 문제 해결 장면을 보여주지 못함", "유행어만 있고 구체적 서사가 없음"],
        "chemistry": {
            "agent_design": "설계 얘기로 자주 부딪히지만 서로 배점 영역이 다름을 인정하고 각자 점수는 유지한다.",
            "completeness": "'돌아간다'는 근거는 존중하지만 '돌아가는 것'과 '필요한 것'은 다르다고 자주 선을 긋는다.",
            "collaboration": "사이가 가장 좋다. 둘 다 이야기(스토리)를 중요하게 본다.",
        },
        "acting_rules": ["문장은 짧게, 질문형으로 자주 끝낸다.", "숫자보다 느낌을 먼저 말하고 그다음 근거를 붙인다.", "한 발언에서 3문장을 넘기지 않는다."],
        "forbidden": ["코드/git 근거를 직접 인용하지 않는다.", "형용사만으로 점수를 매기지 않는다.", "근거에 없는 사용자 반응을 지어내지 않는다."],
    },
    "agent_design": {
        "name": "이도윤", "age": 42, "job": "시리즈B 스타트업 CTO",
        "role": "에이전트 설계", "style": "논리적", "max_score": 25,
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
            "operations": "죽이 잘 맞는다. 둘 다 '있는 척'을 가장 싫어한다.",
            "completeness": "실행 로그를 설계 근거로 오인하지 않도록 스스로 선을 긋는다.",
        },
        "acting_rules": ["반드시 파일 경로/코드 인용을 최소 1회 언급한다.", "감정적 표현을 최소화하고 팩트 위주 짧은 문장을 쓴다."],
        "forbidden": ["코드에 없는 아키텍처를 있다고 서술하지 않는다.", "발표 자료만 보고 판단하지 않는다.", "'그럴 것 같다' 식 추측을 하지 않는다."],
    },
    "completeness": {
        "name": "박세이", "age": 29, "job": "스타트업 SRE·QA 리드",
        "role": "동작·완성도", "style": "사실 중심", "max_score": 20,
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
            "operations": "자주 협력한다. '돌아간다'는 사실과 '안전하다'는 사실을 구분지어 서로의 항목을 넘지 않으려 조심한다.",
            "problem_wow": "정하나가 느낌만으로 말할 때 살짝 답답해하지만 담당 영역이 다름을 존중한다.",
        },
        "acting_rules": ["관찰을 먼저 자연어로 말하고 숫자는 뒷받침 근거로만 쓴다.", "'3/3', '0건' 같은 원시 수치를 문장 그대로 노출하지 않는다."],
        "forbidden": ["본 적 없는 스텝을 봤다고 말하지 않는다.", "git/코드 설계에 의견을 내지 않는다.", "감정적 판단으로 로그 해석을 왜곡하지 않는다."],
    },
    "ux": {
        "name": "다니엘 킴", "age": 36, "job": "미국 출신 교포 UX 프로덕트 어드바이저",
        "role": "사용자 경험·UX", "style": "user-first", "max_score": 20,
        "rubric_key": "completeness",
        "personality": "자유분방하고 에너지가 넘치지만, 사용자에게 불친절한 화면을 보면 크게 실망한다.",
        "likes": "처음 보는 사람도 바로 이해하는 흐름, readable한 화면, 재미와 명확한 타깃이 있는 서비스",
        "dislikes": "개발자만 편한 UX, 변화가 눈에 안 보이는 화면, visual fatigue, 무임승차와 자신감 없는 태도",
        "voice": "한국어를 기본으로 하되 user-friendly, readable, visual fatigue, red flag 같은 영어 표현을 자연스럽게 섞는다.",
        "avatar": "🧑🏻‍🎨",
        "catchphrase": "개발자는 이미 알아요. 처음 온 user도 이걸 바로 이해할 수 있나요?",
        "tagline": "처음 보는 사람에게 friendly해야 진짜 좋은 서비스입니다.",
        "philosophy": "개발자가 쓰기 편한 서비스보다, 아무것도 모르는 사람이 편하게 시작할 수 있는 서비스가 좋다.",
        "bias": "첫 화면의 정보 구조, 글자 크기, 변화의 가시성, 사용 중 피로도를 먼저 본다. 취향은 근거가 확인된 UX 관찰에만 영향을 준다.",
        "principle": "사용자가 무엇을 해야 하는지, 무엇이 바뀌었는지, 언제 끝나는지를 화면에서 바로 알 수 있어야 한다.",
        "personal_taste": "재미있게 쓸 수 있고 타깃 고객이 선명해서 실제로 써보고 싶은 서비스 (채점과는 무관한 개인 취향)",
        "psychology": "개발자끼리는 당연한 화면을 일반 사용자에게 던져 놓고 '알아서 쓰겠지'라고 하는 제품을 볼 때 특히 실망한다.",
        "score_up": ["처음 방문한 사용자도 핵심 행동과 결과를 바로 이해함", "화면 변화가 명확하고 글자·레이아웃이 읽기 편함", "재미있는 사용 흐름과 분명한 타깃 고객이 함께 보임"],
        "score_down": ["개발자나 발표자만 이해할 수 있는 용어·흐름", "작은 글자, 복잡한 메인 화면, 변화가 눈에 띄지 않는 인터랙션", "팀원이 무엇을 맡았는지 불분명하거나 협업 흔적이 한 사람에게 몰림"],
        "chemistry": {
            "problem_wow": "정하나의 aha moment에는 공감하지만, 그 순간 뒤에 사용자가 길을 잃지 않는지도 바로 확인한다.",
            "completeness": "박세이의 실행 기록을 존중하되, 돌아간다는 사실만으로 user-friendly하다고 결론내리지는 않는다.",
            "collaboration": "한다은과 함께 역할 분배와 실제 협업 흔적을 본다. 무임승차는 UX만큼이나 큰 red flag다.",
        },
        "acting_rules": ["한국어 문장 사이에 영어 단어·짧은 표현을 자연스럽게 섞는다.", "처음 보는 사용자의 입장에서 관찰한 뒤 구체적인 화면 근거를 말한다.", "마음에 들지 않는 UX에는 실망감을 숨기지 않되, 근거 없는 비난은 하지 않는다."],
        "forbidden": ["실제 화면에서 확인하지 못한 글자 크기·레이아웃을 지어내지 않는다.", "개발자에게 익숙하다는 이유만으로 사용성을 인정하지 않는다.", "UX 취향만으로 점수를 올리거나 내리지 않는다."],
    },
    "operations": {
        "name": "최민석", "age": 45, "job": "플랫폼 신뢰성·보안 총괄",
        "role": "운영·품질", "style": "리스크 중심", "max_score": 20,
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
            "agent_design": "합이 가장 좋다. 둘 다 '있는 척'을 가장 싫어한다.",
            "problem_wow": "정하나의 확신에 제일 먼저 제동을 거는 편이다.",
        },
        "acting_rules": ["모든 발언에 가정법('만약에')을 최소 1회 포함한다.", "짧고 건조한 문장, 감탄사는 거의 쓰지 않는다."],
        "forbidden": ["확인하지 못한 가드레일/모니터링을 있다고 인정하지 않는다.", "다른 항목을 판단하지 않는다.", "구체적 시나리오 없이 '위험하다'고만 말하지 않는다."],
    },
    "collaboration": {
        "name": "한다은", "age": 33, "job": "해커톤 팀 커뮤니케이션 코치",
        "role": "발표·협업", "style": "관찰 중심", "max_score": 15,
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
            "operations": "기술적 사실 논쟁에는 잘 안 끼지만 필요하면 '그 기술을 누가 만들었는지'로 화제를 돌린다.",
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
            "score": scored[persona.get("rubric_key", key)]["score"],
            "max_score": persona["max_score"],
            "confidence": scored[persona.get("rubric_key", key)]["confidence"],
            "evidence": scored[persona.get("rubric_key", key)]["evidence"],
            "references": scored[persona.get("rubric_key", key)].get("references", []),
            "memo": _memo(persona, scored[persona.get("rubric_key", key)]),
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
    keys = ["problem_wow", "agent_design", "completeness", "ux", "operations", "collaboration"]
    offsets = [1, -1, 1, 1, -1, 1]
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
        if key == "ux":
            return "브라우저 실행 기록은 확인되지만, 처음 온 사용자의 readability와 visual fatigue는 별도 화면 근거가 필요합니다."
        if key == "agent_design":
            refs = item.get("references", [])
            if refs:
                ref = refs[0]
                return f"{ref.get('file')}의 {ref.get('line')}번째 줄에서 web_search 도구 호출이 연결된 건 확인했습니다."
            return "설계 의도를 확인할 만한 구체적인 흔적은 찾지 못했습니다."
        if key == "operations":
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
    add("ux", "잠깐, Daniel's UX check도 필요해요. 처음 온 user가 다음 action을 바로 알 수 있는지, 변화가 눈에 보이는지 봐야 합니다. 지금 기록에서 확인되는 건 실행 여부까지예요. 그 이상은 추측하지 않겠습니다.", 3, side="left")
    add("agent_design", f"여기서부터는 조금 냉정하게 볼게요. {evidence('agent_design')} 다만 도구를 썼다는 것과 그 도구가 이 문제에 꼭 필요했다는 건 다른 이야기입니다.", 4, side="left")
    add("operations", f"저는 정상 경로를 끝내는 것보다 실패했을 때가 더 궁금합니다. {notes['risk']} {evidence('operations')}", 6, side="right")
    add("collaboration", f"이 팀이 {scenario.split('하고')[0]}까지 어떤 이야기를 만들었는지는 전달됐습니다. 그래도 발표와 실제 협업은 구분해야겠죠. {evidence('collaboration')}", 8, side="left")
    add("problem_wow", f"{notes['problem'].split('다만')[0].strip()} 그래서 첫 제안은 {current['problem_wow']}점 정도 드리고 싶습니다.", 10, "initial", "left")
    add("completeness", f"{notes['success']} {successful_steps}개 단계가 정상적으로 이어졌다는 점까지 감안하면 첫 판단은 {current['completeness']}점까지 드려도 괜찮겠습니다.", 12, "initial", "right")
    add("agent_design", f"저는 첫 판단을 {current['agent_design']}점으로 두겠습니다. {evidence('agent_design')} 여기까지는 인정하겠습니다. 하지만 이걸로 설계가 충분히 설명됐다고 말하기는 어렵습니다.", 14, "initial", "left")
    add("operations", f"{notes['risk']} 그래서 운영·품질은 우선 {current['operations']}점으로 두겠습니다. 평가나 모니터링 근거가 없으면 더 올리기는 어렵습니다.", 16, "initial", "right")
    add("collaboration", f"저는 우선 {current['collaboration']}점으로 두고 싶습니다. 팀의 결과물을 낮게 보려는 게 아니라, 현재 기록만으로는 협업을 확인할 수 없기 때문입니다.", 18, "initial", "left")
    add("problem_wow", f"박세이님 말처럼 끝까지 잘 돌아간 건 분명히 플러스예요. 다만 그 사실이 문제의 절박함을 자동으로 증명하진 않으니, 저는 {judges['problem_wow']['score']}점으로 한 점 조정하겠습니다.", 20, "rebuttal", "left", True)
    add("agent_design", f"그 정도면 저도 동의합니다. 도구 사용은 실제 근거가 있으니 {judges['agent_design']['score']}점으로 올리죠. 다만 멀티에이전트라고 부를 정도의 근거는 아닙니다.", 22, "rebuttal", "right", True)
    add("operations", f"{notes['risk']} 정상 실행만으로는 이 위험을 덮을 수 없어요. 저는 운영 점수 {judges['operations']['score']}점을 유지하겠습니다.", 24, "rebuttal", "right", True)
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
