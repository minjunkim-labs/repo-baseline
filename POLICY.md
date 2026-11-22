# 규칙

repo-baseline v2를 쓰는 모든 저장소의 규칙이다. 도구·모델·스택을 고르지 않는다. 각 저장소의 `AGENTS.md`·`REVIEW.md`가 이 규칙을 그 저장소에 맞게 채운다.

옮기는 동안: `.baseline/`이 없는 저장소(v1, 이 저장소 포함)는 [v1 판 규칙](https://github.com/minjunkim-labs/repo-baseline/blob/4b556dd2a893efddae2805d3533ee80d5d2862e7/POLICY.md)을 따른다. v1 문서가 가리키는 `POLICY.md`의 절도 그 판의 절이다.

## 1. 트렁크

- 기준 브랜치는 `main` 하나다. 장기 브랜치는 두지 않는다.
- 작업 브랜치는 짧게 산다. 병합은 squash 하나이고, 병합하면 브랜치를 지운다.
- PR은 작게 만든다. 되돌리기는 revert 한 번이어야 한다.
- 끝나지 않은 기능은 꺼진 피처 플래그 뒤에 두고 `main`에 넣는다. 플래그마다 담당자, 켜는 조건, 지우는 조건을 적는다. 쓰는 곳이 없으면 플래그 체계를 새로 만들지 않는다.

## 2. 완료

- 완료는 주장이 아니라 명령의 실제 출력이다. 명령은 `.baseline/commands.json`의 setup·check·test·build이고, `AGENTS.md`의 명령 칸이 그 사본이다. 없는 칸은 `N/A: <이유>`다. 사람, 훅, CI가 모두 `python3 -I .baseline/baseline.py run <명령>`으로 부른다.
- 시작 전에 완료 기준을 정해 PR 본문 Summary에 쓴다. Evidence에는 실행한 명령과 결과, 확인하지 않은 범위를 쓴다.
- 반복되는 결정적 작업은 스크립트와 CI가 한다. 에이전트는 판단만 한다.

## 3. 리뷰 등급

| 등급 | 조건 | 리뷰 | 병합 |
| --- | --- | --- | --- |
| 문서 | 바뀐 파일이 모두 문서이고, 지침 파일(`AGENTS.md`, `CLAUDE.md`, `REVIEW.md`), `prompts/`, 스킬, 관리 블록, 민감한 파일이 아니다 | 없음. 필수 CI만 | 에이전트가 `enqueue`로 넣는다 |
| 쉬움 | 되돌리기 쉬움이고 민감한 파일을 건드리지 않는다. 아래 두 예외도 쉬움이다 | 구현 대화를 물려받지 않는 하위 에이전트 한 번 | 에이전트가 `enqueue`로 넣는다 |
| 어려움 | 되돌리기 어려움이거나 민감한 파일·관리 블록을 건드린다 | 새 세션 리뷰와 새 세션 보안 관점 리뷰. 다른 모델 패밀리 리뷰는 선택 | 소유자가 diff를 읽고 GitHub 화면에서 큐에 넣는다 |

쉬움이 되는 두 예외:

- upgrade PR: 바뀐 관리 파일·블록·스킬 사본의 sha256이 모두 그 baseline 태그의 기록과 같다. 그 바이트는 baseline 저장소에서 사람이 이미 읽었다. 하나라도 다르거나 프로젝트 칸이 함께 바뀌면 일반 규칙을 따른다.
- Dependabot minor·patch 묶음 PR: 작성자와 모든 커밋이 `dependabot[bot]`이고, 바뀐 줄이 manifest·lockfile의 버전·해시뿐이고, 업데이트가 모두 minor·patch다. 다른 사람이 push했거나 major·새 의존성이 있으면 일반 규칙을 따른다.

판정과 진행:

- 등급은 `baseline.py review-preflight`가 바뀐 경로, 관리 블록 해시, 위 예외로 먼저 정한다. 리뷰어는 리뷰 보고의 「등급」 칸으로 올릴 수 있고 내릴 수 없다. `enqueue`는 두 등급 가운데 높은 쪽을 쓴다.
- 등급을 정하는 입력(`AGENTS.md`의 상시 지시 줄, `REVIEW.md`의 「민감한 파일」 절)은 PR 트리가 아니라 base(`main`)에서 읽는다. upgrade 예외의 sha256은 baseline 저장소의 그 태그에서 읽는다. 상시 지시 줄을 만들거나 넓히는 변경과 「민감한 파일」 줄을 지우는 변경은 어려움이다.
- 리뷰어에게는 리뷰 프롬프트 경로와 PR 링크만 준다. 기준은 저장소의 `REVIEW.md`이고, Spec(완료 기준)과 Standards(`REVIEW.md`) 두 축으로 따로 본다.
- 확실한 결함은 리뷰어가 고쳐 커밋한다. 리뷰는 최대 3라운드이고, 2라운드부터는 바뀐 부분만 본다.
- 리뷰 봇은 어려움 PR에서만 요청한다. 외부 리뷰의 지적은 리뷰어가 받아들일지 판정한 것만 센다.
- 리뷰어는 PR 본문 Review 칸의 「리뷰한 head」「등급」「남은 지적」을 채운다. `enqueue`가 이 세 칸을 읽는다.

## 4. 되돌리기와 민감한 파일

되돌리기 쉬움·어려움은 "망가지면 누가 무엇을 잃나"로 정한다. 작성자가 아니라 diff로 정하고, 애매하면 어려움이다.

- 되돌리기 어려움: 돈, 계정 접근, 다른 사람 데이터의 노출. 데이터 삭제나 복구가 어려운 migration. 비밀값·인증·권한을 넓히는 변경. 새 workflow 쓰기 권한. 대량 발송. 영향 범위가 넓거나 복구가 불확실함. 아래 민감한 파일.
- 되돌리기 쉬움: 위에 하나도 해당하지 않음.

민감한 파일(권한·돈·자동화·리뷰를 바꾸는 파일):

| 경로 | 무엇 |
| --- | --- |
| `.github/workflows/**` | CI workflow |
| 저장소·CI 설정 | 예: `.github/dependabot.yml`, `CODEOWNERS` |
| 의존성 manifest·lockfile | 위 Dependabot 예외에서만 민감한 파일로 보지 않는다 |
| 에이전트 설정 폴더와 `.mcp.json` | `.claude/`·`.agents/`·`.codex/`·`.cursor/` 같은 폴더(하위 폴더 포함)와 `.mcp.json` |
| `.baseline/` 전체 | 등급, 큐 넣기, 검사를 정한다 |
| `.mise.toml` | 툴체인 판 |
| 저장소가 정한 경로 | 인증, 결제, 권한, migration 등. `REVIEW.md`의 「민감한 파일」 절에 적는다 |

PR 본문 Merge Danger에 등급, 영향 범위, 되돌리는 법, 걸린 민감한 파일을 적는다.

## 5. 병합

- 상시 지시: 코어 `AGENTS.md`의 한 줄이다. 문서·쉬움 PR은 에이전트가 `python3 -I .baseline/baseline.py enqueue <PR> <리뷰한 head>`로 머지 큐에 넣는다. 소유자가 그 저장소에서 끄려면 이 줄을 지운다.
- `enqueue`는 넣기 직전에 등급, PR이 fork가 아니고 작성자와 모든 커밋 작성자(GitHub이 커밋 이메일로 이은 계정)가 쓰기 권한이 있는 계정(Dependabot 예외는 `dependabot[bot]`)인지, head가 그 SHA인지, 필수 CI 통과, (쉬움이면) 리뷰 보고의 「리뷰한 head」·「등급」·「남은 지적: 없음」과 보고 뒤에 판정하지 않은 외부 리뷰가 없음을 다시 계산하고 `expectedHeadOid`로 넣는다. 하나라도 맞지 않으면 넣지 않고 이유를 출력한다. 어려움 등급은 늘 거부하고, 건너뛰는 옵션은 없다.
- 코어 `.claude/settings.json`은 되돌릴 수 없는 일(비밀값 읽기, `main`·강제 push, `git reset --hard`·`git clean`, 저장소 설정 쓰기, `enqueue` 밖의 병합)을 deny로 막고 ask는 두지 않는다. `enqueue`의 allow 규칙은 두지 않는다. 자동 모드가 버리고, 규칙은 어떤 코드가 도는지 보지 못한다. 대신 `PreToolUse` 훅(`.claude/hooks/allow_enqueue.py`)이 `enqueue <번호> <40자 SHA>` 꼴이고 사본의 sha256이 `settings.json`에 고정한 값과 같을 때만 허용한다. `enqueue`는 GraphQL을 쓰므로 로컬 전용이다.
- 에이전트가 머지 큐에 넣는 길은 `enqueue` 하나다. 어려움 PR은 소유자가 GitHub 화면에서 넣는다(§3). `gh pr merge`, 큐를 우회하는 병합, 자동 병합은 쓰지 않는다(저장소 설정 `allow_auto_merge: false`).
- 큐는 최신 `main` 위에서 필수 CI를 다시 돌리고 squash로 병합한다. 그래서 PR에 base를 합치지 않고 최신 브랜치 요구(`strict`)는 끈다. head가 바뀌면 다시 리뷰한다.
- GitHub 저장소는 조직이 소유한 공개 저장소로 두고 PR 필수, 필수 CI, 머지 큐, force push·삭제 금지를 켠다. 머지 큐를 그 경우에만 쓸 수 있기 때문이다([문서](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue), 2026-11-16 확인).
- 클라우드 에이전트에게 주는 비밀값에는 병합 권한이 없다.

남는 틈:

- `enqueue`는 리뷰 보고의 글을 읽을 뿐이다. 다른 컨텍스트가 실제로 리뷰했는지는 기계로 증명하지 못한다. 문서·쉬움 등급에서만 생기고, 필수 CI·머지 큐·revert가 뒤를 받친다.
- "어려움 PR은 사람이 병합"은 서버가 막지 않는다. 에이전트가 소유자 계정의 `gh` 토큰을 쓰기 때문이다. 로컬 deny와 `enqueue`의 거부가 막지만 우회할 수 있고, 일부러 한 우회는 규칙 위반이다. 서버에서 막아야 하면 에이전트용 봇 계정과 `CODEOWNERS` 필수 리뷰를 쓴다.

## 6. 회고

- 같은 리뷰 지적이 두 번 나오면 환경으로 옮긴다. 회고는 필요할 때 [prompts/retro.md](prompts/retro.md)로 한다.
- 장치는 사고가 난 뒤에 더한다. 되돌림(revert·핫픽스)이 생기면 그 층에만 검사를 더한다. 지표는 되돌림 수 하나다.
- 서로 어긋나거나 쓸모없어진 규칙을 지우는 제안도 한다. 제안 중 사용자가 고른 것만 반영한다.

## 7. 비밀값

- 비밀값(`.env*`, 키, 토큰, 인증서)은 읽거나 커밋하지 않는다. 에이전트 설정의 거부 규칙에 넣는다. GitHub에서는 push protection이 2차 방어다.
- 장기 키는 소유자 기기에만 둔다. 클라우드 에이전트 환경에 두지 않는다.
- 비밀값이 커밋되면 먼저 키를 폐기하고 새로 발급한다.
- 취약점 제보는 비공개 경로(예: GitHub 비공개 취약점 보고)로 받는다.

## 8. 작업 추적

- 작업의 원본은 GitHub Issue 한 곳이다. 계획 도구(예: Linear)는 Issue와 동기화로만 붙인다.
- 우선순위·일정·내부 판단과 취약점 설명은 공개 Issue·PR·커밋에 적지 않는다.
- PR 본문에 원본 Issue를 닫는 키워드와 함께 적는다. 예: `Closes #12`.

## 9. 바닥

완화하지 않는 것이다. 다른 규칙과 부딪히면 이 절이 먼저다.

- `main` 보호: PR 필수, 필수 CI, 머지 큐, force push·삭제 금지. 서버가 막는다.
- 비밀값을 읽거나 커밋하지 않는다(§7).
- 돈, 인증·권한, 복구가 어려운 데이터 migration, workflow 쓰기 권한, 에이전트 설정 폴더, `.baseline/`를 건드리는 PR은 사람이 diff를 읽고 병합한다. §3의 upgrade 예외만 이 줄의 예외다. 그 바이트는 baseline 저장소에서 사람이 읽었고, 해시는 그 태그에서 읽는다.
- 우선순위·일정·내부 판단과 취약점 설명을 공개 Issue·PR·커밋에 적지 않는다.
- 브랜치 보호·저장소 설정·CI workflow를 사람 승인 없이 바꾸지 않는다.
