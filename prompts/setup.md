# 셋업 프롬프트

이 파일 하나를 코딩 에이전트에게 첨부한다. 에이전트 도구(Claude Code·Codex·Cursor 등)는 무엇이든 된다.

---

이 저장소에 repo-baseline v2 코어를 적용해 줘. 아래 순서대로 하고, 끝나면 「완료 보고」 형식으로 보고해.

## 지킬 것

- 원본은 공개 저장소 `https://github.com/minjunkim-labs/repo-baseline`의 `main`이다. 저장소 밖 임시 폴더에 clone해서 읽는다. 아래 `<클론>`은 그 폴더다.
- 읽을 것은 원본의 `docs/start.md`, `POLICY.md`, `WORKFLOW.md`, (GitHub이면) `github/README.md`, (배포하는 앱이면) `ops/README.md`, (쓰기 권한자가 둘 이상이면) `team/README.md`뿐이다. 판 올리기면 그 사이 태그의 릴리스 노트(GitHub Releases)도 읽는다. `templates/`·`profiles/`의 v1 문서는 `github/README.md`가 가리키는 파일 말고는 읽지 않는다.
- 파일은 `baseline.py`의 `init`·`migrate`·`upgrade`가 쓴다. 관리 파일과 관리 블록(`<!-- baseline:start -->`~`<!-- baseline:end -->`)은 손으로 고치지 않는다. 그 밖에 이미 있는 파일은 덮어쓰지 않고 합친 뒤, 합친 내용을 보고한다.
- 비밀값 파일(`.env*`, 키)을 읽거나 만들거나 커밋하지 않는다.
- `main`에 직접 push하지 않는다. PR을 병합하지 않는다.
- 브랜치 보호·저장소 설정 같은 서버 쓰기(`github apply` 등)는 하지 않는다. 그것은 소유자가 자기 기기에서 한다.
- 모르는 명령을 지어내지 않는다. 확인할 수 없으면 `N/A: <이유>` 또는 "확인하지 않음"으로 적는다.

## 0. 무엇을 하는지 정한다

- `.baseline/`이 있으면 이미 v2다. 판 올리기를 한다: 작업 브랜치에서 `docs/start.md` 「판 올리기」대로 `python3 -I .baseline/baseline.py upgrade <판>`을 돌리고, 지난 판부터 올리는 판까지 각 태그의 릴리스 노트에 적힌 손으로 옮길 일은 다음 PR로 나눈다. 그 뒤 5·6단계를 한다.
- `.baseline/`이 없고 `AGENTS.md`·`CLAUDE.md`·`REVIEW.md`·`.claude/`·`.github/pull_request_template.md` 같은 코어 파일이 하나도 없으면 1a단계(`init`)다.
- 그 밖에는 1b단계(`migrate`)다. 옛 repo-baseline v1(`.github/repo-baseline.json`이 있거나 `templates/core`를 복사한 저장소)도 여기다.

## 1. 코어 쓰기

작업 브랜치를 먼저 만든다.

### 1a. init

`python3 -I <클론>/baseline.py init .`을 돌린다. 이미 있는 파일 때문에 멈추면 1b로 간다.

### 1b. migrate

1. `python3 -I <클론>/baseline.py migrate .`을 돌리고 출력 전체를 보고에 붙인다.
2. 「막힘」 줄이 있으면 각 줄이 시키는 대로 푼다. 프로젝트 내용을 지우거나 옮겨야 풀리는 막힘(같은 이름 스킬, 프로젝트 내용이 있는 관리 파일)은 풀지 말고 소유자에게 묻는다.
3. 막힘이 없으면 `--apply`를 붙여 다시 돌린다.
4. 「확인」 줄은 하나씩 처리하고 무엇을 했는지 보고한다. CI workflow를 바꾸라는 줄은 3단계에서 한다.

## 2. 칸 채우기

1. `AGENTS.md`
   - 프로젝트 이름과 한 줄 설명: README와 코드에서 읽는다.
   - 명령 4칸(setup/check/test/build): 프로젝트의 빌드 파일(`package.json`, `Makefile`, `go.mod`, `Cargo.toml`, `pyproject.toml`, Gradle·Xcode 설정 등)에서 찾는다. `.baseline/commands.json`에 쓴다. 값은 argv 배열(`["npm", "test"]`)이다. 셸 문법(`&&`, 파이프, 환경 변수)이 있으면 `["sh", "-c", "<명령>"]`, 없는 칸은 문자열 `"N/A: <이유>"`다. `AGENTS.md`의 칸은 `check`가 알려 주는 줄로 맞춘다. 각 명령을 `python3 -I .baseline/baseline.py run <이름>`으로 실제로 돌린다. 없거나 돌릴 수 없으면 `N/A: <이유>`. `migrate`가 만든 초안이 있으면 그것을 확인한다.
   - check 칸이 비면 포매터·린터를 새로 고르지 말고, 있는 도구만 적는다. 새 도구 도입은 제안으로 보고한다.
   - 길잡이 표: 주요 디렉터리와 역할.
   - 코드에서 알 수 없는 것만 쓴다. `budget`은 200줄 이상이면 실패한다.
2. `REVIEW.md` 「민감한 파일」: 인증·결제·권한·migration 경로를 코드에서 찾아 적는다. 못 찾으면 "없음(확인한 범위: …)".

## 3. GitHub 프로필 (원격이 GitHub일 때만)

`git remote -v`가 GitHub를 가리키지 않으면 이 단계를 건너뛰고 보고에 적는다.

1. 원본의 `github/README.md`를 읽고 따른다. 값은 거기 적힌 공통값을 쓰고 새로 고르지 않는다.
2. 이 PR에서는 파일로 두는 것만 한다: `github/ci.yml`을 `.github/workflows/ci.yml`로 복사한다(이미 workflow가 있으면 `check`를 돌리게 합친다). Dependabot·`SECURITY.md`·`.coderabbit.yaml`은 `github/README.md`의 표가 가리키는 대로 복사한다.
3. `.github/repository-settings.json`은 이 PR에 넣지 않는다. `github/README.md`의 「새 저장소 순서」대로 `ci`가 실제 PR에서 한 번 성공한 뒤 따로 PR로 더한다. 보고에 이 다음 일을 적는다.
4. `github plan`·`github apply`는 돌리지 않는다. 소유자가 실행할 명령을 보고에 적는다.

## 4. ops 프로필 (배포하는 앱일 때만)

저장소가 배포해서 사람이 쓰는 앱(웹, 서버, 모바일, 게임)이 아니면 이 단계를 건너뛰고 보고에 적는다. 판단이 애매하면 소유자에게 묻는다.

1. 원본의 `ops/README.md` 「켜기」를 따른다(`docs/agents/ops.md` 복사, `baseline.json`의 `profiles`, 길잡이 한 줄). 빼는 도구가 분명하면(예: 웹 도메인이 없으면 Cloudflare) 그 README대로 `뺀 도구:` 줄을 쓴다.
2. SDK는 설치하지 않는다. 아직 배포하지 않았으면 처음 배포하는 PR에서 한다. 이미 배포한 앱이면 이 PR이 병합된 뒤 SDK와 감시 등록만 하는 PR을 따로 연다. 보고에 이 다음 일을 적는다.

## 5. 검증

모두 실제로 돌리고 출력을 보고에 붙인다.

- `python3 -I .baseline/baseline.py check`: `check: 통과`가 나온다. 관리 파일, 명령 칸과 `commands.json`, `.gitignore`의 비밀값 줄, (ops를 켰으면) `docs/agents/ops.md`를 본다.
- `python3 -I .baseline/baseline.py budget`: 실패하지 않는다.
- 명령 4칸: 각각 `run` 결과(성공·실패) 또는 `N/A: <이유>`.
- `git status`: 비밀값 파일이 스테이징되지 않았다.
- GitHub 프로필을 했으면: workflow 파일의 YAML이 파싱된다(쓸 수 있는 도구로). 확인하지 못했으면 그렇게 적는다.

## 6. PR 열기

커밋하고 PR을 연다. 본문은 `.github/pull_request_template.md`의 칸을 채운다.

- Summary: 코어 적용(했으면 GitHub·ops 프로필도). 완료 기준: `check`·`budget`이 통과한다, 비밀값이 스테이징되지 않았다, (GitHub 프로필을 했으면) workflow YAML이 파싱된다. 전에 통과하던 프로젝트 명령은 그대로 통과한다. `Closes #`는 원본 Issue가 없으면 지운다.
- Evidence: 5단계 출력. 확인하지 않은 범위.
- Merge Danger: `python3 -I .baseline/baseline.py review-preflight <PR>`의 등급과 민감한 파일. 코어는 `.baseline/`과 `.claude/`를 쓰므로 처음 적용과 migrate는 어려움이다. 판 올리기는 upgrade 예외에 맞으면 쉬움이다.
- Review: 비워 둔다. 리뷰는 다른 컨텍스트가 원본 저장소의 `prompts/review.md`로 한다.

## 완료 보고

아래 형식으로 짧게 보고한다.

```
적용: 코어 [init|migrate|판 올리기(<판>)] / GitHub 프로필 [완료|건너뜀(이유)] / ops 프로필 [완료|건너뜀(이유)]
PR: <링크>
명령 4칸: setup=<결과> check=<결과> test=<결과> build=<결과>
합친 기존 파일: <없음|목록>
등급: <문서|쉬움|어려움(민감한 파일)>
소유자가 할 일: <github plan·apply, 리뷰 요청, 병합>
제안(반영 안 함): <새 린터 등>
확인하지 않은 것: <목록>
```
