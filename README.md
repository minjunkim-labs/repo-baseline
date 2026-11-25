# repo-baseline

1인·소규모 팀이 언어·스택·에이전트 도구(어떤 코딩 에이전트든)와 관계없이 바로 안전하게 개발을 시작하게 하는 최소 기준이다.
규칙은 한 쪽짜리 [POLICY.md](POLICY.md)다. 도구는 표준 라이브러리만 쓰는 `baseline.py` 하나다(Python 3.9 이상). 코어(`core/`)를 저장소에 복사하고, 복사한 파일이 그 판과 같은지 `check`가 본다.

## 시작

- 새 저장소: `python3 -I <repo-baseline 클론>/baseline.py init .`
- 이미 있는 저장소(v1 소비 레포 포함): `python3 -I <repo-baseline 클론>/baseline.py migrate .`로 충돌과 계획을 보고, 막힘을 푼 뒤 `--apply`.
- 판 올리기: `python3 -I .baseline/baseline.py upgrade v<X.Y.Z>`

순서와 확인 명령은 [docs/start.md](docs/start.md)에 있다. 에이전트에게 맡기려면 [prompts/setup.md](prompts/setup.md) 하나를 첨부한다.

## 명령

소비 레포에서는 고정한 사본 `.baseline/baseline.py`로 부른다: `python3 -I .baseline/baseline.py <명령>`. `init`·`migrate`는 아직 사본이 없으므로 repo-baseline 클론의 `baseline.py`로 부른다.

| 명령 | 하는 일 |
| --- | --- |
| `init <경로>` | 빈 저장소에 코어를 복사하고 `.gitignore`에 비밀값 줄을 더한다. 코어 파일이 하나라도 있으면 아무것도 쓰지 않고 `migrate`를 가리킨다 |
| `migrate <경로> [--apply]` | 기존 저장소의 충돌(막힘·확인), 쓸 계획, `commands.json` 초안을 출력한다. 막힘이 없을 때만 `--apply`가 쓴다 |
| `upgrade <태그>` | 관리 블록·관리 파일·`.gitattributes` 맨 앞 줄·스킬 사본을 그 태그 판으로 바꾼다. 시작 파일은 건드리지 않는다. 관리 블록을 고쳐 두었으면 diff를 출력하고 멈춘다. `gh`로 태그를 읽는다 |
| `check` | 관리 파일·블록·`.gitattributes` 맨 앞 줄이 이 판과 같은지, `AGENTS.md` 명령 칸이 `.baseline/commands.json`과 같은지, `.gitignore`가 비밀값 파일을 무시하는지 본다. ops 프로필을 켰으면 `docs/agents/ops.md`도 본다 |
| `run <setup\|check\|test\|build>` | `commands.json`의 명령을 돌린다. `.mise.toml`에 판이 있으면 `mise exec`로 돈다 |
| `doctor` | 이 기기가 기준과 다른 곳(도구 판, WSL, 같은 이름 개인 스킬, `autoMode.environment`, `.mise.toml` 신뢰 등)과 고치는 명령을 출력한다 |
| `review-preflight <PR>` | GitHub REST로 PR의 리뷰 등급(문서·쉬움·어려움)과 이유, diff 명령을 출력한다 |
| `review-report <PR> --file <파일>` | 리뷰어가 스레드 판정에 답하고 PR 본문의 Review 칸을 쓴다 |
| `enqueue <PR> <리뷰한 head>` | 문서·쉬움 PR을 다시 확인하고 머지 큐에 넣는다. 어려움 PR은 넣지 않는다. 로컬 전용 |
| `budget` | `AGENTS.md`·`REVIEW.md`·`prompts/review.md` 크기를 공식 문서의 상한과 비교한다 |
| `skills-bump [--check]` | 스킬 출처마다 7일 지난 새 판으로 사본을 바꾼다. repo-baseline 전용 |
| `github <plan\|apply>` | 저장소 설정과 상태 라벨을 기준과 비교한다. `apply`는 소유자만 한다 |

## 코어와 프로필

코어는 `AGENTS.md`·`REVIEW.md`(관리 블록), `CLAUDE.md`(`@AGENTS.md` 한 줄), PR 템플릿, `.gitattributes`(맨 앞 줄만 관리), `.mise.toml`, Stop 훅과 `enqueue` 허용 훅, Matt 스킬 설정 `docs/agents/`(시작 파일), 판을 고정한 스킬 사본 `.claude/skills/`, `.baseline/`이다. 파일마다 저장소가 고칠 수 있는 범위는 [GLOSSARY.md](GLOSSARY.md)(관리 파일, 관리 블록, 시작 파일, 앞줄 관리 파일)에 있다. 단계별로 쓰는 스킬은 [WORKFLOW.md](WORKFLOW.md)에 있다.

| 층 | 프로필 | 언제 켜는가 |
| --- | --- | --- |
| 기본 | [github](github/) | GitHub에 올리면 켠다. POLICY §5가 조직 소유 공개 저장소, 브랜치 보호, 필수 CI, 머지 큐를 요구한다 |
| 기본 | [ops](ops/) | 배포해서 사람이 쓰는 앱이면 켠다. 빼는 도구만 이유와 함께 적는다 |
| 선택 | [team](team/) | 쓰기 권한이 있는 사람이 둘 이상이면 켠다. CODEOWNERS와 사람 승인 |

PR을 열면 [prompts/review.md](prompts/review.md)로 리뷰한다. 등급은 `review-preflight`가 정한다. 문서는 필수 CI만, 쉬움은 하위 에이전트 리뷰 한 번, 어려움은 새 세션 리뷰와 보안 관점 리뷰 뒤 소유자가 병합한다(POLICY §3). 같은 지적이 반복되면 [prompts/retro.md](prompts/retro.md)를 실행한다.

`templates/`, `profiles/`, `tools/`는 v1 도구다. v1 소비 레포가 다 옮기면 지운다. 그때까지 `tools/sync_consumers.py`는 돌리지 않는다.

## 적용 중인 프로젝트

2026-11-25 기준으로 아래 다섯 곳은 v1이다. 저장소마다 PR 하나로 `migrate`를 써서 v2로 옮긴다. 이 저장소는 v2 코어를 쓴다.

| 프로젝트 | 저장소 | 옮기는 Issue |
| --- | --- | --- |
| answer-desk | `minjunkim-labs/answer-desk` | #186 |
| portfolio | `minjunkim-labs/portfolio` | #193 |
| Runstir | `minjunkim-labs/mobile-runtime` | #194 |
| Smallnext | `minjunkim-labs/smallnext` | #195 |
| BGLike | `minjunkim-labs/BGLike` | #196 |

## 그 밖에

- 비밀값은 이 저장소에 두지 않는다. 보안 문제 보고는 [SECURITY.md](SECURITY.md).
- 변경 기록: 태그마다 [docs/releases/](docs/releases/), 지난 태그 뒤 PR마다 `changelog.d/`(태그를 내면 비운다), 2026-11-17 전은 [CHANGELOG.md](CHANGELOG.md). 재설계 전 기록은 [CHANGELOG-2026.md](https://github.com/minjunkim-labs/repo-baseline/blob/c3f6d569871f51b83c1405dee34db6850a0b30e3/docs/archive/CHANGELOG-2026.md)(지운 보관 문서의 마지막 판).
