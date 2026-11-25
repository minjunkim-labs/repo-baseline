# 새 프로젝트 시작

프로젝트에 v2 코어를 적용한다. Python 3.9 이상이 필요하다. 아직 `.baseline/`이 없는 v1 저장소의 판 올리기는 [v1 판 이 문서](https://github.com/minjunkim-labs/repo-baseline/blob/d2360f6e8b5ec81638d3132a9b92ac73ec2f6649/docs/start.md)를 따른다.

## 1. 코어 쓰기

프로젝트 루트에서 실행한다.

```bash
git rev-parse --git-dir >/dev/null 2>&1 || git init   # 빈 프로젝트면 저장소부터 만든다
git clone --depth 1 https://github.com/minjunkim-labs/repo-baseline /tmp/repo-baseline
python3 -I /tmp/repo-baseline/baseline.py init .
```

- `init`은 코어 파일이 하나라도 이미 있으면 아무것도 쓰지 않고 그 파일 이름을 대고 멈춘다. 그때는 `migrate`를 쓴다.
- `.gitignore`는 덮어쓰지 않는다. 비밀값 줄(`.env`, `.env.*`, `!.env.example`, `*.pem`, `*.key`, `*.p12`) 중 빠진 것만 더한다.
- `CLAUDE.md`는 `@AGENTS.md` 한 줄인 관리 파일이다. Claude Code는 `CLAUDE.md`가 있으면 그것을 읽으므로 이 한 줄로 `AGENTS.md`를 읽게 한다. 지우거나 고치면 `check`가 실패한다.

### 이미 파일이 있는 저장소

```bash
python3 -I /tmp/repo-baseline/baseline.py migrate .
```

- 계획만 출력하고 아무것도 쓰지 않는다. 「막힘」 줄이 있으면 그것을 먼저 푼다(같은 이름 스킬, 프로젝트 내용이 있는 관리 파일 등).
- 막힘이 없으면 `--apply`를 붙여 다시 돌린다. `CLAUDE.md`의 내용은 `AGENTS.md`로 옮기고, 옛 `AGENTS.md`의 명령 칸은 `commands.json` 초안이 된다. 「확인」 줄(CI가 `check`를 돌리게 고치기, 옛 manifest 지우기 등)은 손으로 한다.

## 2. AGENTS.md 채우기

- 첫 줄 제목과 한 줄 설명.
- 명령 4칸: setup, check(포맷·린트·타입 등 결정적 검사), test, build. 없는 칸은 `N/A: <이유>`다. 같은 값을 `.baseline/commands.json`에도 쓴다. 두 곳이 다르면 `check`가 고칠 줄을 알려 준다. 각 명령을 `python3 -I .baseline/baseline.py run <이름>`으로 한 번씩 돌려 본다.
- 길잡이 표: 주요 경로와 설명.
- `<!-- baseline:start -->`와 `<!-- baseline:end -->` 사이 관리 블록은 고치지 않는다.

에이전트가 매 세션 읽는 파일이다. 코드에서 알 수 없는 것만 쓴다. `budget`은 200줄 이상이면 실패한다.

## 3. REVIEW.md 채우기

관리 블록 밖의 「민감한 파일」 절에 인증·결제·권한·migration 경로를 적는다([POLICY.md](../POLICY.md) §4). 없으면 "없음(확인한 범위: …)"이다. 「코딩 기준」「배운 규칙」은 사용자가 승인한 것만 더한다.

## 4. 확인

```bash
python3 -I .baseline/baseline.py check
python3 -I .baseline/baseline.py budget
python3 -I .baseline/baseline.py doctor   # 이 기기의 설정을 본다. 저장소 파일은 바꾸지 않는다
git status --short   # 비밀값 파일이 스테이징되지 않았다
```

`check`는 관리 파일·블록·스킬 사본의 해시, 명령 칸, `.gitignore`의 비밀값 줄을 본다. `check: 통과`가 나와야 한다.

## 5. 첫 PR

브랜치를 만들고 커밋한 뒤 PR을 연다. 본문은 `.github/pull_request_template.md`의 칸을 채운다.

- Summary: 코어 적용. 완료 기준: `check`·`budget`이 통과한다. 전에 통과하던 프로젝트 명령은 그대로 통과한다.
- Evidence: 4단계와 명령 4칸을 돌린 결과. 돌리지 않은 칸과 이유.
- Merge Danger: 등급은 `review-preflight`의 출력을 쓴다. 코어는 `.baseline/`과 `.claude/`(에이전트 설정 폴더)를 쓰므로 첫 PR은 어려움이다. 민감한 파일 칸에 걸린 경로를 적는다.
- Review: 리뷰어가 채운다. [prompts/review.md](../prompts/review.md)로 새 세션이 리뷰하고 보안 관점으로 한 번 더 본다. 리뷰하는 기기에 repo-baseline 클론과 Python 3.9 이상이 필요하다.

어려움 PR은 소유자가 병합한다(POLICY §3).

## 판 올리기

repo-baseline이 태그(`v<판>`)를 내면 소비 레포에서 판을 올린다.

```bash
python3 -I .baseline/baseline.py upgrade <판>   # 예: 2.0.0
```

- 관리 블록·관리 파일·스킬 사본을 그 태그 판으로 바꾸고 `baseline.json`을 갱신한다. 소비 레포에서 고친 관리 블록이 있으면 멈추고 diff를 보인다.
- 손으로 옮길 일은 [changelog.d/](../changelog.d/)와 그 태그의 릴리스 노트에 있다. 지난 판 뒤의 항목을 읽고 옮긴다.
- 결과 PR은 바뀐 관리 파일·블록·스킬 사본이 모두 그 태그의 기록과 같으면 upgrade 예외로 쉬움이다. 손으로 옮긴 일처럼 프로젝트 칸이 함께 바뀌면 일반 규칙을 따르니, 그 일은 다음 PR로 나눈다(POLICY §3).

## 다음

- GitHub에 올리면 [github 프로필](../github/)을 켠다.
- 배포하는 앱이면 [ops 프로필](../ops/)을 켠다.
- 쓰기 권한자가 둘 이상이면 [team 프로필](../team/)을 본다.
- 단계마다 쓰는 스킬은 [WORKFLOW.md](../WORKFLOW.md)다.
- 에이전트에게 맡기려면 [prompts/setup.md](../prompts/setup.md)를 첨부한다.
