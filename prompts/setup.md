# 셋업 프롬프트

이 파일 하나를 코딩 에이전트에게 첨부한다. 에이전트 도구(Claude Code·Codex·Cursor 등)는 무엇이든 된다.

---

이 저장소에 repo-baseline v2 코어를 적용해 줘. 아래 순서대로 하고, 끝나면 「완료 보고」 형식으로 보고해.

## 지킬 것

- 원본은 공개 저장소 `https://github.com/minjunkim-labs/repo-baseline`의 태그 `v2.1.1`(또는 소유자가 정한 더 새 태그)이다. 저장소 밖의 새 임시 폴더에 받는다: `B="$(mktemp -d)/repo-baseline" && git clone --depth 1 --branch v2.1.1 https://github.com/minjunkim-labs/repo-baseline "$B"`. 소유자가 더 새 태그를 정했으면 `--branch`의 값을 그 태그로 바꾼다. 아래 `B`는 이 클론이다. 이미 있는 폴더(예: `/tmp/repo-baseline`)를 원본으로 쓰지 않는다.
- 읽을 것은 원본의 `docs/start.md`, `POLICY.md`, (GitHub이면) `github/README.md`, (배포하는 앱이면) `ops/README.md`, (쓰기 권한자가 둘 이상이면) `team/README.md`뿐이다. 판 올리기면 지금 판과 새 판 사이의 `docs/releases/v*.md`도 읽는다. `templates/`·`profiles/`·`tools/`는 v1 도구라 읽지 않는다. 예외: `github/README.md`가 가리키는 `templates/github/` 파일(Dependabot, `SECURITY.md`, `.coderabbit.yaml`)은 읽고 복사한다. 이름이 낯설면 `GLOSSARY.md`를 읽는다.
- 관리 블록(`<!-- baseline:start -->`~`<!-- baseline:end -->`)과 관리 파일은 고치지 않는다. 고치면 `check`가 실패한다. `docs/agents/`의 Matt 스킬 설정 세 파일(`issue-tracker.md`·`domain.md`·`triage-labels.md`)은 시작 파일이라 고쳐도 된다. 같은 폴더의 `LICENSE`는 관리 파일이고, ops 프로필의 `ops.md`는 `check`가 본다. `.gitattributes`는 맨 앞 줄 아래에만 더한다.
- `migrate` 막힘은 원본 `docs/start.md` 2절의 표대로 푼다. 프로젝트 내용을 옮기기 전에는 어떤 파일도 지우지 않고, 관리 블록이 있는 파일(`AGENTS.md`, `REVIEW.md`)과 `CLAUDE.md`는 지우지 않는다. 옮길 곳이 분명하지 않으면 소유자에게 묻는다.
- 비밀값 파일(`.env*`, 키)을 읽거나 만들거나 커밋하지 않는다.
- `main`에 직접 push하지 않는다. PR을 병합하지 않는다.
- 서버 쓰기(`github apply`, 브랜치 보호·저장소 설정)는 하지 않는다. 소유자가 자기 기기에서 한다.
- 개인 설정을 바꾸지 않는다. `doctor`가 출력한 고치는 명령 가운데 개인 설정을 바꾸는 것은 보고만 한다.
- 모르는 명령을 지어내지 않는다. 확인할 수 없으면 `N/A: <이유>` 또는 "확인하지 않음"으로 적는다.

## 0. 어느 경우인가

작업 브랜치를 만든 뒤 고른다.

- `.baseline/baseline.json`이 있으면 이미 v2다. 판 올리기(4절)를 한다.
- 코어 파일(`AGENTS.md`, `REVIEW.md`, `CLAUDE.md`, `.gitattributes`, `.mise.toml`, `.github/pull_request_template.md`, `.claude/`, `docs/agents/`)이 하나도 없으면 새 저장소(1절)다.
- 그 밖에는 이미 있는 저장소(2절)다. v1 소비 레포도 여기다.

## 1. 새 저장소

1. `python3 -I "$B/baseline.py" init .`
2. 원본 `docs/start.md` 1절대로 블록 밖의 칸을 채운다.
   - `AGENTS.md`: 제목과 한 줄 설명(README와 코드에서 읽는다), 길잡이 표. 코드에서 알 수 없는 것만 쓴다.
   - 명령 4칸(setup/check/test/build): 빌드 파일(`package.json`, `Makefile`, `go.mod`, `Cargo.toml`, `pyproject.toml`, Gradle·Xcode 설정 등)에서 찾아 `.baseline/commands.json`에 argv 배열로 쓰고, `AGENTS.md` 「명령」 줄을 `check`가 출력하는 한 줄로 맞춘다. 각 명령을 `python3 -I .baseline/baseline.py run <이름>`으로 돌린다. 없거나 돌릴 수 없으면 `"N/A: <이유>"`. 포매터·린터를 새로 고르지 않는다. 새 도구는 제안으로 보고한다.
   - `.mise.toml`: 빌드 파일이나 CI가 정한 툴체인 판만 옮긴다. 정한 판이 없으면 비워 둔다.
   - `REVIEW.md` 「민감한 파일」: 인증·결제·권한·migration 경로를 코드에서 찾아 적는다. 못 찾으면 "없음(확인한 범위: …)".

## 2. 이미 있는 저장소

1. `python3 -I "$B/baseline.py" migrate .`을 돌리고 출력(충돌, 계획, `commands.json` 초안)을 보고에 붙인다.
2. 막힘을 원본 `docs/start.md` 2절의 표대로 하나씩 푼다.
3. 막힘이 없으면 `python3 -I "$B/baseline.py" migrate . --apply`. 막힘이 남았거나 `--apply`가 실패(종료 코드가 0이 아님)하면 4·5번도 하지 않고 여기서 멈춘 뒤, 남은 막힘이나 오류와 고친 것을 보고한다. `--apply`가 실패했을 때의 복구 방법은 원본 `docs/start.md` 2절에 있다. 적용 전 작업 트리가 깨끗했던 경우만 그대로 따르고, 아니면 소유자에게 묻는다.
4. `commands.json` 초안을 1절 2번의 명령 4칸 기준으로 확인하고, 돌려 본 결과로 고친다.
5. 확인 줄을 처리한다. CI workflow는 3절에서 고친다. 옛 hash-copy manifest(`.github/repo-baseline.json`)는 그 check를 부르는 CI 단계와 함께 지운다. 도구별 지침 파일은 내용을 `AGENTS.md`로 옮기고 지운다. 관리 블록과 겹치는 절은 비교한 뒤 지운다. `.gitattributes`에 코어 줄을 넣었다고 알리면 `git add --renormalize .`을 커밋한다. v1 ops 블록(`<!-- repo-baseline:ops -->`)이 있으면 지우고, 배포하는 앱이면 3절의 ops 프로필을 켠다.

## 3. 프로필

- GitHub(`git remote -v`가 GitHub을 가리킬 때): 원본 `github/README.md`대로 `github/ci.yml`을 `.github/workflows/ci.yml`로 복사하고(기존 CI가 있으면 `check`를 돌리는 단계를 합친다), `.github/repository-settings.json`에 저장소마다 다른 값만 쓴다. Dependabot, `SECURITY.md`, `.coderabbit.yaml`은 그 README의 표를 따른다. `github plan`·`github apply`는 소유자가 할 일로 보고에 적는다.
- ops(배포해서 사람이 쓰는 앱일 때): 원본 `ops/README.md` 「켜기」를 따른다. SDK는 설치하지 않는다. 판단이 애매하면 소유자에게 묻는다.
- team(쓰기 권한자가 둘 이상일 때): 원본 `team/README.md`를 따른다.

## 4. 판 올리기

1. `.baseline/baseline.json`의 `version`을 적어 둔다.
2. `python3 -I .baseline/baseline.py upgrade v<X.Y.Z>`. 관리 블록을 고쳐 두었으면 도구가 diff를 출력하고 멈춘다. 그때는 diff를 보고하고, 그 수정을 repo-baseline에 반영할지 소유자에게 묻는다.
3. 1번 판과 새 판 사이 태그의 `docs/releases/v*.md`에서 소비 레포가 손으로 옮길 일을 한다.

## 5. 검증

모두 실제로 돌리고 출력을 보고에 붙인다.

- `python3 -I .baseline/baseline.py check`: `check: 통과`. `.gitignore`가 비밀값 파일을 무시하지 않으면 여기서 실패한다.
- `python3 -I .baseline/baseline.py run <setup|check|test|build>`: 각각 결과 또는 `N/A: <이유>`.
- `python3 -I .baseline/baseline.py budget`: 상한을 넘지 않는다.
- `python3 -I .baseline/baseline.py doctor`: 출력 전체. 이 기기의 문제는 고치는 명령과 함께 보고한다.
- `git status`: 비밀값 파일이 스테이징되지 않았다.
- GitHub 프로필을 했으면: workflow 파일의 YAML이 파싱된다(쓸 수 있는 도구로). 확인하지 못했으면 그렇게 적는다.

## 6. PR 열기

커밋하고 PR을 연다. 본문은 `.github/pull_request_template.md` 양식이다.

- Summary: 한 일(새 저장소·옮기기·판 올리기, 켠 프로필). 완료 기준: `check`·`budget`이 통과한다(`check`는 `.gitignore`의 비밀값 줄도 본다), 명령 4칸이 돈다, 비밀값이 스테이징되지 않았다. 전에 통과하던 프로젝트 명령은 그대로 통과한다.
- Evidence: 5절 출력. 확인하지 않은 범위.
- 등급: 1·2절은 `.baseline/`과 `.claude/`를 더하므로 어려움이다. 4절에서 관리 바이트만 바꿨으면 `review-preflight`가 쉬움으로 볼 수 있다.
- Review: 비워 둔다. 리뷰는 다른 컨텍스트가 원본의 `prompts/review.md`로 한다.

## 완료 보고

```
적용: [새 저장소|옮기기|판 올리기(이전 판 → 새 판)] / GitHub [완료|건너뜀(이유)] / ops [완료|건너뜀(이유)] / team [완료|건너뜀(이유)]
PR: <링크>
명령 4칸: setup=<결과> check=<결과> test=<결과> build=<결과>
migrate 막힘: <없음|푼 것과 남은 것>
doctor: <통과|문제와 고치는 명령>
등급: <문서|쉬움|어려움(이유)>
소유자가 할 일: <github plan·apply, 남은 막힘의 결정, 리뷰 요청, 병합>
제안(반영 안 함): <새 린터 등>
확인하지 않은 것: <목록>
```
