# repo-baseline

1인·소규모 팀이 언어·스택·에이전트 도구(어떤 코딩 에이전트든)와 관계없이 바로 안전하게 개발을 시작하게 하는 최소 기준이다.
코어는 `baseline.py init`이 프로젝트에 복사하는 파일 묶음과 한 쪽짜리 규칙([POLICY.md](POLICY.md))이다. 파일은 `AGENTS.md`(명령 4칸과 관리 블록), `CLAUDE.md`(`@AGENTS.md` 한 줄), `REVIEW.md`, PR 템플릿, `.baseline/`(도구와 명령), `.claude/`(Stop 훅·`enqueue` 허용 훅과 스킬 사본), `docs/agents/`, `.mise.toml`, `.gitattributes`이고, `.gitignore`에는 빠진 비밀값 줄만 더한다. 코어는 GitHub도 에이전트도 없이 사람 혼자 써도 맞는 규칙만 둔다. 프로필은 두 층이다. 기본 프로필은 켜는 조건이 대개 참이라 조건에 맞으면 켠다. 빼려면 `AGENTS.md`에 이유를 적는다. 선택 프로필은 이유가 있을 때만 켠다.

## 코어 적용 3단계

1. 이 저장소를 받는다(공개, 인증 불필요): `git clone https://github.com/minjunkim-labs/repo-baseline`
2. 새 저장소면 `python3 -I <클론>/baseline.py init <프로젝트>`, 이미 파일이 있는 저장소면 `python3 -I <클론>/baseline.py migrate <프로젝트>`로 계획을 보고 `--apply`를 붙여 다시 돌린다. Python 3.9 이상이 필요하다.
3. `AGENTS.md`의 명령 4칸(setup/check/test/build)을 `.baseline/commands.json`과 같게 채우고 `REVIEW.md` 「민감한 파일」을 채운다. `python3 -I .baseline/baseline.py check`가 통과하면 첫 PR을 연다.

명령과 첫 PR은 [docs/start.md](docs/start.md)에 있다. 에이전트에게 맡기려면 [prompts/setup.md](prompts/setup.md) 하나를 첨부한다. 단계마다 쓰는 스킬과 실행 위치는 [WORKFLOW.md](WORKFLOW.md)다.

## 프로필

| 층 | 프로필 | 언제 켜는가 |
| --- | --- | --- |
| 기본 | [github](github/) | GitHub에 올리면 켠다(POLICY §5가 브랜치 보호·필수 CI·머지 큐를 요구한다). 작업의 원본은 GitHub Issue다. CI 파일 하나와 `github plan`·`apply`(저장소 설정, 상태 라벨) |
| 기본 | [ops](ops/) | 배포해서 사람이 쓰는 앱이면 켠다. 보안·에러 추적·제품 분석·감시 도구를 모두 쓰고, 빼는 도구만 이유와 함께 적는다. 조직에서 한 번 켤 것과 소비 레포마다 할 것, 비밀값 이름 |
| 선택 | [team](team/) | 쓰기 권한자가 2명 이상. CODEOWNERS와 사람 승인 |

Matt Pocock 스킬과 pstack은 v2에서 프로필이 아니라 코어다. `init`이 판을 고정한 스킬 사본을 `.claude/skills/`에 두고, 어느 단계에 무엇을 쓰는지는 [WORKFLOW.md](WORKFLOW.md)가 정한다.

v1 저장소(`.baseline/`이 없는 곳)는 옮길 때까지 [templates/](templates/)와 [profiles/](profiles/)의 v1 판을 쓴다. v1에만 있는 것은 [linear](profiles/linear/)(Issue 목록만으로 계획하기 불편할 때), [pr-conventions](profiles/pr-conventions/)(PR 형식을 CI로 검사), [hash-copy](profiles/hash-copy/)(파일을 해시로 고정해 복사하는 도구)다.

PR을 열면 [prompts/review.md](prompts/review.md)로 리뷰한다. 리뷰 등급은 셋이고 `review-preflight`가 정한다(POLICY §3). 문서는 필수 CI만, 쉬움은 구현 대화를 물려받지 않는 하위 에이전트 리뷰 한 번, 어려움은 새 세션 리뷰와 보안 관점 리뷰 뒤 소유자 병합이다. 리뷰하는 기기에는 이 저장소의 클론과 Python 3.9 이상이 있어야 한다.
회고는 정기 실행하지 않는다. 같은 지적이 반복될 때 [prompts/retro.md](prompts/retro.md)를 실행한다.

## 적용 중인 프로젝트

동기화 PR을 받는 저장소 목록은 [tools/consumers.json](tools/consumers.json)이다. 이 표는 적용 현황이고, 동기화 대상 목록이 아니다. 2026-11-18 기준으로 아래 여섯 곳 모두 코어(`AGENTS.md`·`REVIEW.md`·PR 템플릿)와 github 프로필(`.github/repository-settings.json`)이 있다. 이 저장소도 같은 구성을 쓴다. 서버 설정이 파일과 맞는지는 소유자가 `tools/apply_github_settings.py` 계획 모드로 확인한다. repo-office 연결은 `docs/agents/office.md`가 있는 곳이다.

| 프로젝트 | 저장소 | repo-office |
| --- | --- | --- |
| Smallnext | `minjunkim-labs/smallnext` | 연결 |
| BGLike | `minjunkim-labs/BGLike` | 연결 |
| Runstir | `minjunkim-labs/mobile-runtime` | 연결 |
| answer-desk | `minjunkim-labs/answer-desk` | 없음 |
| portfolio | `minjunkim-labs/portfolio` | 없음 |
| repo-office | `minjunkim-labs/repo-office` | 해당 없음 |

## 그 밖에

- 비밀값은 이 저장소에 두지 않는다. 보안 문제 보고는 [SECURITY.md](SECURITY.md).
- 변경 기록: [changelog.d/](changelog.d/)(2026-11-17부터, PR마다 파일 하나)와 [CHANGELOG.md](CHANGELOG.md)(그 전). 재설계 전 기록은 [CHANGELOG-2026.md](https://github.com/minjunkim-labs/repo-baseline/blob/c3f6d569871f51b83c1405dee34db6850a0b30e3/docs/archive/CHANGELOG-2026.md)(지운 보관 문서의 마지막 판).
