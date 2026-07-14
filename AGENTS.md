# auto-as

AI 에이전트 해커톤 Day 4 발표 제출물을 자동 채점하는 파이썬 CLI. 팀이 제출한 **데모 URL + GitHub 저장소 URL + 자연어 데모 시나리오**를 입력받아 (1) 저장소를 읽기 전용으로 clone해 소스·git 로그를 정적 분석하고 (2) Playwright headless 브라우저로 데모를 직접 눌러본 뒤 (3) 5명의 AI 심사위원 페르소나가 공식 루브릭(100점)대로 채점하고, 근거가 붙은 HTML 리포트와 리더보드를 산출한다. 이 점수는 최종 점수의 **AI 담당분(40%)** 이며, 교수 심사 60%와의 결합은 시스템 밖에서 처리한다. 자세한 배경·범위·루브릭은 `PRD.md` 참조.

**저장소 코드는 절대 실행하지 않는다** — clone은 `--depth 1` 읽기 전용이며 install/build/run 없음(`pipeline.py:clone_repository`). 이건 설계 불변식이니 유지한다.

---

## 🔒 LOCKED RULES — 위반 = 즉시 중단

> **이 섹션은 협업 계약이다. 위반 = 작업 즉시 중단 + 사용자에게 보고.**
> **이 섹션 자체의 수정·삭제·완화는 사용자의 명시적 승인 없이 금지.** 갱신이 필요해 보이면 먼저 옵션 제시 → 승인 → 진행.

### L1. 비자명 작업 전에 옵션 제시 + 승인

다음은 **착수 전에** 옵션 (a)/(b)/(c) 형태로 제시하고 승인을 받은 뒤에만 실행한다:

- 새 파일/모듈 추가, 다중 파일 리팩터
- **설계 결정** — 루브릭 배점 변경, 심사위원 페르소나(`panel.py`)의 성격/편향/점수 규칙 수정, 정적 분석 신호(`SIGNALS`) 추가·삭제, 채점 공식(`scoring.py`) 변경, 브라우저 액션 종류 추가
- 외부 라이브러리 신규 도입, `requirements.txt` 변경
- `PRD.md` / `AGENTS.md` 의 의미 변경

**예외 (승인 불필요):** read / grep / 테스트 실행 / 명백한 버그 1줄 수정 / 사용자가 직접 명시한 정확한 변경.

**모호한 명령** → 추측해서 진행하지 말고 옵션 (a)/(b)/(c) 제시. 제안은 "이렇게 해보시죠" 톤으로.

### L2. Commit 단위 — 한 기능 = 한 commit

사용자가 명시한 한 가지 기능/수정 범위만 한 commit에 담는다. 작업 중 발견한 별개 concern(요청하지 않은 정정·개선·후속 이슈)은 **반드시 별개 commit** 으로 분리한다.

- 별개 concern 발견 시: 보고 → 이번 작업에 포함할지 별도 commit으로 뺄지 옵션 제시.
- 자체 판단으로 "겸사겸사" 묶기 금지.
- Commit message는 기존 스타일 유지 — 영어 명령형 요약 한 줄 (예: `Add Vercel deploy config and document the redeploy workflow`).
- Footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### L3. 자율 commit은 검증 통과 + 단일 concern 일 때만

`python -m pytest test_smoke.py` (또는 `python test_smoke.py`) 통과 + commit 범위가 **사용자 명시 요청 한 가지** 라면 자율 commit. 그 외(테스트 실패, 별개 concern 포함, 미승인 설계 결정 포함)는 commit 전에 보고.

### L4. Destructive 작업은 항상 승인 필수

`git reset --hard`, `git push --force`, `git rebase`(공유 히스토리), branch 삭제, history 재작성, `rm -rf`, 추적 파일 대량 삭제 등. 자율 판단으로 "되돌리기"(revert/reset) 시도 금지 — 그것도 destructive 결정이다.

---

## 브랜치 운영 — Trunk-Based

`main` 하나를 trunk로 삼는다. **짧게 사는 브랜치, 자주 머지**가 원칙.

- **작업 브랜치는 짧게.** 기능 하나 = 브랜치 하나, 하루 안에 `main`으로 머지하는 것을 목표로 한다. 오래 떠 있는 feature 브랜치를 만들지 않는다.
- **브랜치 이름:** `feat/<요약>`, `fix/<요약>`, `docs/<요약>`, `chore/<요약>` (예: `feat/openai-panel-retry`).
- **`main`에 직접 커밋 금지** (L1/L3 승인 흐름을 거친다). 항상 작업 브랜치 → `main` 머지.
- **머지는 rebase 우선.** `main` 위로 rebase해 선형 히스토리를 유지하고, 머지 후 브랜치는 삭제한다. force-push·history 재작성은 L4 대상이니 승인받는다.
- **`main`은 항상 초록.** 머지 전에 `test_smoke.py`가 통과해야 한다. 깨진 채로 trunk에 넣지 않는다.
- **`output/`는 커밋하지 않는다** (`.gitignore` 대상). 채점은 로컬/서버에서 돌리고, 생성된 정적 HTML만 Vercel에 CLI로 별도 배포한다 (README 참조).

작업 착수 시 제안 예: *"이 기능은 `feat/xxx` 브랜치 파서 trunk-based로 한번 작업해보시죠!"*

## 사용 언어 & 코딩 컨벤션

- **언어:** Python 3.10+ (`str | None`, `list[dict]` 등 PEP 604/585 문법 사용).
- **소통·문서·주석:** 한국어. 기술 용어(Playwright, headless, rubric, persona 등)는 영문 유지. **커밋 메시지·코드 식별자는 영어.**
- **의존성 최소화:** 표준 라이브러리 우선(`urllib`, `subprocess`, `pathlib`, `argparse`, `tempfile`). 외부 패키지는 `playwright` / `jinja2` / `python-dotenv`만 — 새 의존성은 L1 승인 대상.

기존 코드에서 지켜지는 스타일(이어서 따른다):

- 모든 모듈 최상단에 `from __future__ import annotations`.
- 함수 시그니처에 타입 힌트 필수. 작고 순수한 함수 지향, 부수효과는 IO 경계(`write_json`, `render_*`)에 모은다.
- 문자열은 **큰따옴표**. f-string 사용.
- **방어적 입력 검증** 유지 — URL 스킴 검증, path traversal 차단(`base not in resolved.parents`), 외부 응답 파싱 시 `try/except`로 로컬 폴백. 사용자 데이터를 HTML에 넣을 때는 반드시 escape(`test_report_rendering`이 이걸 검증).
- 예외는 도메인 예외(`SubmissionError`)로 좁혀 잡고, CLI 경계에서 exit code로 변환.
- 채점은 **근거 우선** — 점수에는 항상 `evidence`/`references`를 함께 남긴다. 근거 없는 점수 조정 금지(이건 페르소나 프롬프트의 불변식이기도 하다).

## 검증

```bash
pip install -r requirements.txt
python -m playwright install chromium        # 브라우저 실행 근거가 필요할 때

python -m pytest test_smoke.py               # 스모크 테스트 (pytest 있으면)
python test_smoke.py                          # pytest 없이 일부 테스트 직접 실행

# 실제 채점 파이프라인
python -m auto_as examples/submission.json -o output/evidence.json   # 단건
python -m auto_as.batch examples/submissions -o output               # 배치 → leaderboard.html
```

- 채점 로직·리포트 렌더링을 바꿨으면 `test_smoke.py`를 먼저 통과시킨다 (리포트/리더보드 테스트가 HTML 구조 문자열까지 검증하므로, 마크업을 바꾸면 테스트도 같이 갱신).
- 기본은 `local_provisional` 모드(외부 키 불필요, 결정론적). OpenAI 모드는 `OPENAI_API_KEY` 설정 시에만 켜지고, 실패하면 자동으로 로컬 폴백 후 `panel.ai_error`에 기록한다.

## 구조 (요약)

```
auto_as/
├── cli.py          # 단건 진입점 (python -m auto_as)
├── batch.py        # 배치 진입점 (python -m auto_as.batch)
├── pipeline.py     # collect_evidence — 검증→clone→정적분석→git→브라우저→채점→패널
├── browser.py      # Playwright 실행 + 시나리오 파괴적 스텝 skip
├── planner.py      # 자연어 시나리오 → click/fill/upload/observe/skip 액션 (local_rules)
├── scoring.py      # RUBRIC(100점) 규칙 기반 채점
├── panel.py        # 5 심사위원 페르소나 + 로컬/OpenAI 패널 토론
├── report.py       # 팀별 report.html
└── leaderboard.py  # leaderboard.html + 뱃지
```
