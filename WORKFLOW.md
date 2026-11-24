# 작업 흐름

v2 저장소에서 단계마다 쓰는 스킬, 실행 위치마다 적용되는 것, 클라우드 환경과 샌드박스 설정이다. 규칙은 [POLICY.md](POLICY.md)가 정한다.

## 단계별 스킬

Matt Pocock 스킬이 뼈대이고, pstack은 Matt가 비우는 칸에만 쓴다. (사람)은 사람만 부르는 스킬(`disable-model-invocation`)이다. 에이전트는 이름을 대고 실행을 권한다.

| 단계 | 쓸 스킬 | 쓰지 않는 것 |
| --- | --- | --- |
| 접수·설계 | 작은 diff는 바로 구현. 크면 Matt `grill-with-docs`(사람), 세션 하나를 넘으면 `wayfinder`(사람). 인터페이스는 `codebase-design` | pstack `architect`(겹침) |
| 스펙·티켓 | `to-spec` → `to-tickets`(사람). spec이 원본 Issue다. 티켓은 GitHub blocked-by 관계와 상태 라벨을 쓴다 | |
| 구현 | spec 뒤에는 티켓마다 새 세션. `tdd`, 버그면 먼저 `diagnosing-bugs` | Matt `implement`·`implement-spec`(같은 세션 리뷰가 POLICY §3과 부딪힘), pstack `tdd`(겹침), `poteto-mode`(흐름·병합 단계가 뼈대와 부딪힘) |
| 검증 | 화면·게임처럼 돌려 봐야 하는 앱만 pstack `create-verification-skill` | |
| 리뷰 | `prompts/review.md`가 Matt `code-review`에 두 축을 맡긴다. 어려움 PR이면 pstack `blast-radius`(영향 범위), `interrogate`(보안 관점) | |
| PR 본문 | Matt `pr`, 칸은 PR 템플릿 | pstack `ketchup`·`show-me-your-work` |
| 회고 | `prompts/retro.md` | pstack `correct`는 선택 |

Matt 스킬은 트래커·라벨·도메인 문서 설정을 `docs/agents/`에서 읽는다. `/setup-matt-pocock-skills`가 만드는 파일(`issue-tracker.md`는 GitHub, `triage-labels.md`는 아래 상태 라벨 5개, `domain.md`는 루트 `GLOSSARY.md`와 `docs/adr/`)을 고정한 판의 seed 그대로 둔 관리 파일이다.

| 상태 라벨 | 뜻 |
| --- | --- |
| `needs-triage` | 아직 분류하지 않았다 |
| `needs-info` | 답이나 자료를 기다린다 |
| `ready-for-agent` | 범위와 완료 기준이 정해져 에이전트가 시작할 수 있다(막힘 관계는 따로 본다) |
| `ready-for-human` | 사람이 해야 한다 |
| `wontfix` | 하지 않는다 |

라벨은 소유자가 `python3 -I .baseline/baseline.py github apply`로 만든다([github 프로필](github/README.md)).

## 스킬 사본

- 위 표의 스킬과 그 스킬이 부르는 스킬만 판을 고정한 사본으로 `.claude/skills/`에 둔다. 목록, 출처, 판, 의존 스킬(`requires`)은 [skills/skills.lock.json](skills/skills.lock.json)에 있다. 플러그인 대신 사본을 쓰는 까닭은 클라우드 세션과 Projects 스레드가 저장소 settings의 플러그인을 불러오지 않고 `.claude/skills/`는 읽기 때문이다.
- 원본은 이 저장소의 `skills/`다. 스킬마다 출처의 LICENSE(Matt는 저장소 루트, pstack은 `pstack/LICENSE`, 둘 다 MIT)를 함께 둔다. `init`이 `.claude/skills/`로 복사하고, `check`는 사본이 이 판의 해시와 다르거나 사본 폴더에 없는 파일이 있으면 실패한다. 프로젝트만의 스킬은 다른 이름의 폴더에 둔다.
- 갱신 기준은 출처마다 lock에 있다. 태그가 있는 출처(Matt)는 나온 지 `days`(7)일이 지난 가장 새 태그를 받는다. 태그 날짜는 태그 객체의 날짜이고, 자기 날짜가 없는 가벼운 태그(lightweight)는 받지 않는다. 고정한 커밋보다 앞서지 않는 태그는 건너뛴다. 태그가 없는 출처(pstack의 `cursor/plugins`)는 `branch`에서 `days`일보다 오래된 마지막 커밋을 받고, `plugin.json`의 `version`과 커밋 SHA를 함께 적는다. 판은 앞으로만 간다. 우리 스킬의 바이트가 그대로면 받지 않는다.
- 한 출처의 스킬은 한 판으로 함께 바뀐다. 그래서 `requires`는 같은 출처의 스킬만 적을 수 있다.
- `requires`는 그 스킬이 실행하라고 부르는 스킬이다(예: `blast-radius` → `arena`·`unslop`, `interrogate` → `arena`·`in-your-own-words`). "per the X skill"처럼 참고로만 가리키는 스킬(`arena`가 가리키는 `poteto-mode`, principle 스킬)은 복사하지 않는다. lock에 스킬을 더하면 새 판이 없어도 `skills-bump`가 고정한 판에서 받는다.

### 갱신하는 법

1. `.github/workflows/skills-bump.yml`이 주 1회 `python3 -I baseline.py skills-bump --check`를 돌린다. 새 판이 있으면 Issue 「skills-bump: 새 스킬 판」을 열거나 본문을 바꾼다. 모델은 쓰지 않는다.
2. 로컬 세션이 repo-baseline 클론에서 `python3 -I baseline.py skills-bump`를 돌린다. `skills/`, `.claude/skills/`, lock, `baseline.py`의 `MANAGED`, `.baseline/`, `.claude/settings.json`의 고정 해시를 바꾼다. 받은 바이트는 REST 트리의 blob SHA와 맞춰 본다. symlink·submodule과 1MiB 넘는 파일은 받지 않는다. 바꿀 스킬 폴더에 커밋하지 않은 변경(추적하지 않는 파일 포함)이 있거나, 쓰는 경로에 symlink가 있으면 아무것도 쓰지 않고 멈춘다.
3. 그 세션이 PR을 연다. 민감한 파일을 바꾸므로 어려움이고, 소유자가 diff를 읽고 병합한다. 바뀐 스킬이 위 표나 POLICY와 어긋나면(예: 같은 세션 리뷰, 병합 단계 추가) PR 본문에 적는다.

workflow가 PR까지 열지 않는 까닭(2026-11-23 실측, #182): `workflow_dispatch`로 띄운 CI의 `ci` check run은 그 커밋에서 성공했지만 PR의 check 목록에 들어가지 않아 PR이 `BLOCKED`로 남았다. 이 저장소는 GitHub Actions가 PR을 만들지 못하게 되어 있다(`can_approve_pull_request_reviews: false`). 앱 토큰 같은 장기 비밀값은 더하지 않는다.

## 실행 위치마다 적용되는 것

| | 로컬 세션 | 저장소 하나인 클라우드 세션 | Projects 클라우드 스레드 | Projects의 내 컴퓨터 스레드(Remote Control) |
| --- | --- | --- | --- | --- |
| `CLAUDE.md`·`.claude/skills/` | 읽음 | 읽음 | 읽음 | 읽음 |
| 저장소 `.claude/settings.json`의 deny·훅 | 적용 | 적용 | 적용 안 됨 | 적용 |
| 저장소 settings의 플러그인 | 설치 | 설치 안 됨 | 불러오지 않음 | 설치 |
| GitHub GraphQL(`gh pr`, `gh issue`, 큐 넣기) | 됨 | 프록시가 막음 | 프록시가 막음 | 됨 |
| check | 훅 | 훅 | CI가 대신 | 훅 |

근거: [Claude projects](https://code.claude.com/docs/en/claude-projects), [Cloud environments](https://code.claude.com/docs/en/cloud-environments) 「GitHub proxy」, [Settings](https://code.claude.com/docs/en/settings) (2026-11-22 확인, #175).

- 기본 경로는 로컬 세션과 저장소 하나인 클라우드 세션이다. Projects 클라우드 스레드에는 deny와 훅이 없어서 서버(브랜치 보호, 필수 CI)와 판정 모델이 안전을 맡는다. 비밀값이 필요한 일과 큐 넣기는 내 컴퓨터 스레드나 로컬 세션에서 한다.
- 클라우드에서도 도는 명령(`check`, `review-preflight`, `budget`)은 GitHub REST만 쓴다. `enqueue`는 로컬 전용이다.

## 클라우드 환경 설정

- setup script는 mise를 설치하고 `python3 -I .baseline/baseline.py run setup`을 부른다.
- 허용 도메인은 GitHub과 그 스택의 패키지 저장소만 둔다.
- network secret에는 병합 권한이 없는 것만 둔다. 장기 키는 소유자 기기에만 둔다(POLICY §7).

## 샌드박스 예시(선택)

코어에 넣지 않는다. 오래 혼자 도는 로컬 세션에서 쓸 때 프로젝트나 개인 settings에 더한다. macOS·Linux·WSL2에서 돌고, Linux·WSL2는 `bubblewrap`·`socat`이 필요하다. 샌드박스는 기본으로 `~/.ssh`를 막지 않는다. `denyRead`는 Bash 명령만 막고 Read 도구는 막지 않으므로 코어 settings의 `Read(**/.env*)` deny는 그대로 둔다. 근거: [Sandboxing](https://code.claude.com/docs/en/sandboxing), [Sandbox path prefixes](https://code.claude.com/docs/en/settings-reference#sandbox-path-prefixes) (2026-11-23 확인).

```json
{
  "sandbox": {
    "enabled": true,
    "enableWeakerNetworkIsolation": true,
    "filesystem": {
      "denyRead": ["~/.ssh", "~/.aws", "./**/.env*"]
    },
    "network": {
      "allowedDomains": ["github.com", "api.github.com", "objects.githubusercontent.com"]
    }
  }
}
```

`allowedDomains`에는 그 스택의 패키지 저장소를 더한다.

macOS 샌드박스는 시스템의 인증서 확인 서비스(trustd)를 막는다. 그래서 Go로 만든 `gh`가 TLS 검증에 실패하고(`x509: OSStatus -26276`), `gh`를 부르는 `baseline.py`의 `review-preflight`·`enqueue`·`github plan`도 실패한다. 위 예시의 `enableWeakerNetworkIsolation: true`가 그 서비스를 연다. 2026-11-24에 macOS에서 `gh api`, `gh pr view`, `baseline.py review-preflight`가 샌드박스 안에서 권한 확인 없이 도는 것을 확인했다. 대가로 샌드박스 안의 명령이 trustd에 닿는다. `excludedCommands`의 `gh *`는 `gh`를 직접 부를 때만 맞고 `baseline.py` 안의 `gh`에는 맞지 않으므로 대신 쓰지 않는다. 엄격 모드(`allowUnsandboxedCommands: false`, 데스크톱 앱의 「엄격한 샌드박스 모드」)는 그래도 끈다. 엄격 모드는 샌드박스가 막은 명령을 묻지 않고 막는다. 끄면 그 명령을 샌드박스 밖에서 다시 실행할 수 있고, 그때 보통의 권한 확인을 거친다. 근거: [Sandboxing](https://code.claude.com/docs/en/sandboxing) 「Go-based CLIs fail TLS verification on macOS」, [All settings](https://code.claude.com/docs/en/settings-reference) `sandbox.enableWeakerNetworkIsolation`(2026-11-24 확인).
