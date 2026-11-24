# 프로젝트 이름

한 줄로 이 저장소가 무엇인지 쓴다.

## 명령

`python3 -I .baseline/baseline.py run test`처럼 부른다. 이 칸은 `.baseline/commands.json`과 같아야 한다.

- setup: `N/A: 아직 정하지 않았다`
- check: `python3 -I .baseline/baseline.py check`
- test: `N/A: 아직 정하지 않았다`
- build: `N/A: 아직 정하지 않았다`

## 길잡이

| 경로 | 무엇 |
| --- | --- |
| `GLOSSARY.md` | 용어집. 새 용어는 여기에 먼저 쓴다 |
| `docs/agents/` | Matt 스킬이 읽는 트래커·라벨·도메인 문서 설정 |
| `docs/adr/` | 결정 기록(ADR) |
| `.mise.toml` | 툴체인 판. `run`이 이 판으로 돈다. mise 밖 도구는 이 아래에 판과 설치법을 쓴다 |
| `REVIEW.md` | 리뷰 기준. 리뷰할 때만 읽는다 |

## 병합

- 상시 지시: 문서·쉬움 PR은 리뷰가 끝나면 `python3 -I .baseline/baseline.py enqueue <PR> <리뷰한 head>`로 머지 큐에 넣는다. 소유자가 끄려면 이 줄을 지운다.

<!-- baseline:start -->
## 작업 방식

- 규칙은 repo-baseline의 [POLICY.md](https://github.com/minjunkim-labs/repo-baseline/blob/main/POLICY.md)다. 이 블록은 그 요약이다.
- 시작 전에 완료 기준을 정해 PR 본문 Summary에 쓴다. 완료 주장은 명령의 실제 출력이다.
- 리뷰 등급은 셋이다. 문서는 필수 CI만, 쉬움은 구현 대화를 물려받지 않는 하위 에이전트 리뷰 한 번, 어려움은 새 세션 리뷰와 보안 관점 리뷰 뒤 소유자 병합이다(POLICY §3).
- 등급은 `review-preflight`가 정하고 리뷰어는 올릴 수만 있다. `enqueue`는 어려움 PR을 넣지 않는다.
- 무엇을 만들고 무엇이라 부를지 정할 일이 크면 사람만 부르는 스킬(`grill-with-docs`, `wayfinder`, `to-spec`, `to-tickets`)의 이름을 대고 실행을 권한다.
- 이 블록은 repo-baseline이 관리한다. 고치지 않는다. 블록 밖은 프로젝트가 쓴다.

## 하지 않는 것

- 비밀값(`.env*`, 키, 토큰)을 읽거나 커밋하지 않는다. 커밋됐으면 먼저 키를 폐기한다.
- `main`에 직접 push하지 않는다. `enqueue`를 거치지 않고 병합하지 않는다.
- 어려움 PR(예: 돈, 인증·권한, 복구가 어려운 migration, workflow 권한, 에이전트 설정 폴더, `.baseline/`)을 병합하지 않는다.
- 우선순위·일정·내부 판단과 취약점 설명을 공개 Issue·PR·커밋에 쓰지 않는다.
- 브랜치 보호·저장소 설정·CI workflow를 사람 승인 없이 바꾸지 않는다.
<!-- baseline:end -->
