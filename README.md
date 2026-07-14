# auto-as

첫 단계는 제출물의 근거 데이터를 JSON으로 수집합니다. 저장소 코드는 실행하지 않습니다.

```bash
python -m auto_as examples/submission.json -o output/evidence.json
```

명령은 `output/evidence.json`과 `output/report.html`을 함께 생성합니다.

여러 제출물을 한 번에 처리합니다.

```bash
python -m auto_as.batch examples/submissions -o output
```

제출물별 JSON/HTML과 `output/leaderboard.html`을 생성합니다. 기본값은 외부 키가 필요 없는 `local_provisional` 모드입니다.

OpenAI로 팀별 점수와 심사 대화를 생성하려면 키를 설정하고 같은 명령을 실행합니다.

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-5.6-luna"  # 선택
export OPENAI_REASONING_EFFORT="medium"  # 선택
python -m auto_as.batch examples/submissions -o output
```

API 호출이 실패하면 해당 실행은 자동으로 로컬 평가로 대체되고 `panel.provider`와 `panel.ai_error`에 기록됩니다.

현재 포함된 분석:

- public GitHub 저장소 shallow clone
- 에이전트/RAG/도구/eval/모니터링/가드레일 패턴 탐지
- Git 작성자별 커밋 수와 커밋 시점 추출
- Playwright headless 실행, 스텝별 상태·스크린샷·콘솔 오류 수집

Playwright 브라우저가 설치되지 않은 환경에서는 `browser.available=false`로 기록하고 나머지 분석은 계속합니다. 브라우저 설치 후 같은 명령을 다시 실행하면 됩니다.

실제 URL을 넣으면 네트워크와 `git` CLI가 필요합니다.

시나리오 planner는 계속 로컬 규칙으로 동작합니다. OpenAI는 평가 점수와 패널 대화 생성에만 사용합니다.

현재 점수는 `local_provisional` 모드의 임시 규칙 기반 점수입니다. 각 항목의 점수와 근거는 `score.items`에 저장됩니다.
