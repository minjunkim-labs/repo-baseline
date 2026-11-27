# repo-baseline

1인·소규모 팀의 개발 기준 원본이다.

## 명령

`python3 -I .baseline/baseline.py run test`처럼 부른다. 표준 라이브러리만 쓴다.

- setup: `N/A: 의존성이 없다(Python 3.9 이상, IANA 시간대 데이터. 없으면 python3 -m pip install tzdata)`
- check: `python3 -I .baseline/baseline.py check`
- test: `python3 -m unittest test_baseline test_github test_distribution`
- build: `N/A: 배포는 파일 복사다`

루트의 `.baseline/`·관리 파일·`.claude/`는 소비 레포처럼 낸 태그의 판이다. `baseline.py`·`core/`를 고쳐도 함께 고치지 않는다. 태그를 낸 직후 소유자가 `python3 -I .baseline/baseline.py upgrade <태그>`로 맞춘다. 맞추기 전에는 태그를 받은 클론에서 `test_distribution.py`가 실패한다. 샌드박스가 에이전트의 `.claude/` 쓰기를 막는다. `core/.claude/settings.json`의 `--sha256`은 자리표시(`0`×64)이고 `init`이 진짜 값으로 쓴다.

## 길잡이

| 경로 | 무엇 |
| --- | --- |
| `baseline.py`, `core/`, `skills/` | v2 도구, 코어, 스킬 사본 원본 |
| `WORKFLOW.md`, `docs/agents/` | 단계별 스킬 표, Matt 스킬 설정 |
| `github/`, `ops/`, `team/` | v2 프로필 |
| `prompts/` | 셋업·리뷰·회고 프롬프트 |
| `REVIEW.md` | 리뷰 기준. 리뷰할 때만 읽는다 |
| `GLOSSARY.md` | 용어집. 새 용어는 여기에 먼저 쓴다 |
| `changelog.d/` | PR마다 하나씩 더하는 변경 항목. 태그를 낼 때 모은다 |

## 이 저장소의 규칙

- 상시 지시: 문서·쉬움 PR은 리뷰가 끝나면 `python3 -I .baseline/baseline.py enqueue <PR> <리뷰한 head>`로 머지 큐에 넣는다.
- PR마다 `changelog.d/YYYY-MM-DD-<slug>.md` 하나를 더한다. `- `로 시작하는 항목 하나, 1~3줄이다. 소비 레포가 손으로 옮길 일을 쓴다. `CHANGELOG.md`는 고치지 않는다. 태그를 낼 때 지난 태그 뒤 항목을 릴리스 노트 `docs/releases/v<판>.md`로 모으고 지운다. 같은 PR에서 `baseline.py`의 `VERSION`도 그 판으로 바꾼다.
- 같은 사실을 README, `docs/start.md`, `prompts/setup.md`에 적었으면 함께 고친다.
- 리뷰는 `origin/main` 판의 `prompts/review.md`·`.baseline/baseline.py`·`REVIEW.md`로 한다.
- 에이전트 도구의 문서를 근거로 쓰면 공식 문서 링크와 확인일을 적는다. 코어에 특정 도구·모델 이름을 넣지 않는다.
- 저장소 설정을 서버에 적용하지 않는다(`baseline.py github apply`는 소유자가 실행한다).

<!-- baseline:start -->
## 작업 방식

- 규칙은 repo-baseline의 [POLICY.md](https://github.com/minjunkim-labs/repo-baseline/blob/main/POLICY.md)다. 이 블록은 그 요약이다.
- 시작 전에 열린 PR과 Issue에서 같은 일을 찾는다. 있으면 그 PR을 잇거나 소유자에게 묻는다.
- 시작 전에 완료 기준을 정해 PR 본문 Summary에 쓴다. 완료 주장은 명령의 실제 출력이다.
- 리뷰 등급은 셋이다. 문서는 필수 CI만, 쉬움은 구현 대화를 물려받지 않는 하위 에이전트 리뷰 한 번, 어려움은 구현 대화를 물려받지 않는 새 세션 하나가 Spec·Standards와 보안 관점을 본 뒤 소유자 병합이다(POLICY §3).
- 등급은 `review-preflight`가 정하고 리뷰어는 올릴 수만 있다. `enqueue`는 어려움 PR을 넣지 않는다.
- 하위 에이전트·새 세션·headless 실행을 띄울 때는 POLICY §3의 모델 층과 effort를 사용자 전역 지시가 가리키는 층 표로 실제 모델로 바꾼다. 층은 내리지 않는다.
- 무엇을 만들고 무엇이라 부를지 정할 일이 크면 사람만 부르는 스킬(`grill-with-docs`, `wayfinder`, `to-spec`, `to-tickets`)의 이름을 대고 실행을 권한다.
- 이 블록은 repo-baseline이 관리한다. 고치지 않는다. 블록 밖은 프로젝트가 쓴다.

## 하지 않는 것

- 비밀값(`.env*`, 키, 토큰)을 읽거나 커밋하지 않는다. 커밋됐으면 먼저 키를 폐기한다.
- `main`에 직접 push하지 않는다. `enqueue`를 거치지 않고 병합하지 않는다.
- 어려움 PR(예: 돈, 인증·권한, 복구가 어려운 migration, workflow 권한, 에이전트 설정 폴더, `.baseline/`)을 병합하지 않는다.
- 우선순위·일정·내부 판단과 취약점 설명을 공개 Issue·PR·커밋에 쓰지 않는다.
- 브랜치 보호·저장소 설정·CI workflow를 사람 승인 없이 바꾸지 않는다.
<!-- baseline:end -->
