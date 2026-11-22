# 프로젝트 이름

한 줄로 이 저장소가 무엇인지 쓴다.

## 명령

`python3 -I .baseline/baseline.py run <이름>`으로 부른다. 이 칸은 `.baseline/commands.json`과 같아야 한다.

- setup: `N/A: 아직 정하지 않았다`
- check: `python3 -I .baseline/baseline.py check`
- test: `N/A: 아직 정하지 않았다`
- build: `N/A: 아직 정하지 않았다`

## 길잡이

| 경로 | 무엇 |
| --- | --- |
| `CONTEXT.md` | 용어집 |
| `docs/adr/` | 결정 기록(ADR) |

<!-- baseline:start -->
## 작업 방식

- 시작 전에 완료 기준을 정한다. 완료 주장은 명령의 실제 출력이다.
- 이 블록은 repo-baseline이 관리한다. 고치지 않는다. 블록 밖은 프로젝트가 쓴다.

## 하지 않는 것

- 비밀값(`.env*`, 키, 토큰)을 읽거나 커밋하지 않는다.
- `main`에 직접 push하지 않는다.
- 브랜치 보호·저장소 설정·CI workflow를 사람 승인 없이 바꾸지 않는다.
<!-- baseline:end -->
