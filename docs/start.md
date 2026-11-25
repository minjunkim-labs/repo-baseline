# 시작

새 저장소는 `init`, 이미 있는 저장소는 `migrate`로 코어를 적용한다. 판 올리기는 `upgrade`다. 모두 Python 3.9 이상의 `python3`만 있으면 된다. 명령 표는 [README](../README.md#명령)에 있다.

## 0. 원본 받기

적용할 태그를 저장소 밖에 받는다. 공개 저장소라 인증이 필요 없다.

```bash
git clone --depth 1 --branch v2.0.0 https://github.com/minjunkim-labs/repo-baseline /tmp/repo-baseline
```

아래 `B`는 이 클론이다: `B=/tmp/repo-baseline`.

## 1. 새 저장소

프로젝트 루트에서 실행한다.

```bash
git rev-parse --git-dir >/dev/null 2>&1 || git init
python3 -I "$B/baseline.py" init .
python3 -I .baseline/baseline.py check
```

`init`은 코어 파일이 하나라도 이미 있으면 아무것도 쓰지 않고 멈춘다. 그때는 2절 `migrate`를 쓴다.

복사한 뒤 블록 밖의 칸을 채운다. 관리 블록(`<!-- baseline:start -->`부터 `<!-- baseline:end -->`까지)과 관리 파일은 고치지 않는다. 고치면 `check`가 실패한다.

- `AGENTS.md`: 제목과 한 줄 설명, 길잡이 표. 코드에서 알 수 없는 것만 쓴다. `budget`은 200줄 이상이면 실패한다.
- 명령 4칸(setup/check/test/build): `.baseline/commands.json`에 argv 배열로 쓴다. 셸 문법이 필요하면 `["sh", "-c", "..."]`로 쓰고, 없는 칸은 `"N/A: <이유>"`다. `AGENTS.md` 「명령」의 줄은 `check`가 출력하는 한 줄과 글자까지 같게 고친다. 각 명령을 `python3 -I .baseline/baseline.py run <이름>`으로 한 번씩 돌려 본다.
- `.mise.toml`: 툴체인 판(예: `node = "22.12.0"`). 판이 있으면 `run`이 `mise exec`로 돈다. mise가 다루지 못하는 도구는 `AGENTS.md` 길잡이에 판과 설치법을 쓴다.
- `REVIEW.md`: 「민감한 파일」(인증·결제·권한·migration 경로, [POLICY.md](../POLICY.md) §4). 「코딩 기준」과 「배운 규칙」은 비워 둔다.

## 2. 이미 있는 저장소

v1 소비 레포도 이 방법으로 옮긴다. 작업 브랜치에서 실행한다.

```bash
python3 -I "$B/baseline.py" migrate .
```

아무것도 쓰지 않고 세 가지를 출력한다.

- 충돌: `막힘`은 풀어야 `--apply`가 쓴다. `확인`은 사람이 볼 일이다(CI에서 `check`를 돌리게 고치기, 옛 hash-copy manifest 지우기, 도구별 지침 파일 옮기기 등).
- 계획: 새로 쓰거나 고칠 파일. `CLAUDE.md`의 내용은 `AGENTS.md` 블록 밖으로 옮기고 `CLAUDE.md`는 `@AGENTS.md` 한 줄이 된다.
- `commands.json` 초안: 기존 `AGENTS.md` 명령 칸에서 만든다. 사람이 확인한다.

막힘을 하나씩 푼 뒤 다시 돌린다. 관리 파일 자리(`docs/agents/*`, `.gitattributes` 등)에 프로젝트 내용이 있으면 `migrate`는 덮어쓰지 않고 막힘으로 보고한다. 그 내용을 어디로 옮길지는 아직 정하지 않았다([#175](https://github.com/minjunkim-labs/repo-baseline/issues/175)). 에이전트는 정하지 말고 소유자에게 묻는다.

막힘이 없으면 쓴다.

```bash
python3 -I "$B/baseline.py" migrate . --apply
python3 -I .baseline/baseline.py check
```

`check`가 실패하면 출력이 가리키는 파일을 고친다. 대개 `commands.json` 초안과 `AGENTS.md` 명령 칸이 어긋난 경우다. 그 뒤 1절의 칸 채우기를 확인한다.

## 3. 확인

```bash
python3 -I .baseline/baseline.py check
python3 -I .baseline/baseline.py run test
python3 -I .baseline/baseline.py budget
python3 -I .baseline/baseline.py doctor
```

- `check`·`budget`은 `통과`나 상한 안의 크기를 출력해야 한다.
- `doctor`는 저장소가 아니라 이 기기를 본다. 문제마다 고치는 명령을 출력한다. 개인 설정을 바꾸는 명령(예: 같은 이름의 개인 스킬 지우기)은 소유자가 정한다. 다른 기기에서 다시 돌릴 때마다 본다.
- Git이 `.env`·`.env.*`를 무시하는지 본다: `git check-ignore -q .env && git check-ignore -q .env.local && echo ignored`.

## 4. GitHub

원격이 GitHub이면 [github 프로필](../github/README.md)을 켠다.

- [github/ci.yml](../github/ci.yml)을 `.github/workflows/ci.yml`로 복사한다. ubuntu·macOS에서 `run setup`, `check`, `budget`, `run check`, `run test`를 돈다. 고칠 칸이 없다.
- `.github/repository-settings.json`에 저장소마다 다른 값만 쓴다.
- 소유자가 최신 기본 브랜치에서 `python3 -I .baseline/baseline.py github plan`을 읽고 `github apply`로 적용한다. 에이전트는 `apply`를 돌리지 않는다.
- Dependabot, `SECURITY.md`, `.coderabbit.yaml`은 github 프로필 README의 표대로 복사한다.

배포하는 앱이면 [ops 프로필](../ops/README.md), 쓰기 권한자가 둘 이상이면 [team 프로필](../team/README.md)을 켠다.

## 5. 첫 PR

본문은 `.github/pull_request_template.md` 양식이다. Summary에 완료 기준을 쓰고, Evidence에 3절 명령의 실제 출력을 붙인다.

코어는 `.baseline/`과 에이전트 설정 폴더(`.claude/`)를 더하므로 이 PR은 어려움이다. 새 세션 리뷰와 보안 관점 리뷰 뒤 소유자가 병합한다(POLICY §3). 리뷰는 [prompts/review.md](../prompts/review.md)로 하고, 등급은 `review-preflight`가 정한다.

## 판 올리기

새 태그가 나오면 소비 레포에서 실행한다. `gh`가 로그인되어 있어야 한다(태그를 GitHub REST로 읽는다).

```bash
python3 -I .baseline/baseline.py upgrade v<X.Y.Z>
python3 -I .baseline/baseline.py check
```

- 관리 블록을 고쳐 두었으면 아무것도 쓰지 않고 diff를 출력한 뒤 멈춘다. 그 수정을 repo-baseline에 반영할지 소유자에게 묻는다.
- 지금 판과 새 판 사이 태그의 릴리스 노트([docs/releases/](releases/))에서 소비 레포가 손으로 옮길 일을 한다.
- 관리 바이트만 바꾼 PR은 `review-preflight`가 upgrade 예외로 쉬움으로 본다. 손으로 다른 파일을 고쳤으면 그 파일로 등급이 정해진다.
