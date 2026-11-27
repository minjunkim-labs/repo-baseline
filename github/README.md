# github 프로필 (v2)

원격이 GitHub이면 켠다. POLICY §5가 조직 소유 공개 저장소, 브랜치 보호, 필수 CI, 머지 큐를 요구한다.

| 무엇 | 어디 |
| --- | --- |
| CI | [ci.yml](ci.yml)을 `.github/workflows/ci.yml`로 복사한다. 고칠 칸이 없다. ubuntu·macOS가 `.mise.toml`의 같은 판으로 돌고, `ci` job이 둘의 결과를 모은다 |
| 저장소 설정·상태 라벨 | `.baseline/baseline.py github plan`과 `github apply`. 공통값은 `baseline.py`의 `GITHUB_SETTINGS`·`LABELS`에 있다 |
| Dependabot | [dependabot.yml](dependabot.yml)을 `.github/dependabot.yml`로 복사하고, 패키지 관리자마다 [dependabot-ecosystem.yml](dependabot-ecosystem.yml)의 블록을 `updates:` 아래에 붙인다 |
| `SECURITY.md` | [SECURITY.md](SECURITY.md)를 저장소 루트로 복사하고 `OWNER/REPO`를 채운다. GitHub은 `.github/`, 루트, `docs/` 순서로 이 파일을 찾으니, 이미 있으면 그 파일에 합친다. `github apply`가 비공개 취약점 보고를 켠 뒤 병합한다 |
| `.coderabbit.yaml` | 아래 「CodeRabbit 설정」 |

## 저장소 설정 파일

`.github/repository-settings.json`에는 저장소마다 다른 값만 쓴다. 나머지는 공통값이고, 같은 자리에 쓴 값은 프로젝트 값이 이긴다(객체는 키마다 합치고, 목록은 통째로 바꾼다).

```json
{
  "repository": "<조직>/<이름>",
  "repository_id": 123456789,
  "expected": {
    "protection": {"required_status_checks": {"checks": [{"context": "ci", "app_id": 15368}]}},
    "allowed_actions": {"patterns_allowed": ["jdx/mise-action@*"]}
  }
}
```

- `repository_id`는 `gh api repos/<조직>/<이름> --jq .id`의 출력이다. `plan`은 이 값과 이름이 서버와 다르면 아무것도 읽지 않고 멈춘다.
- 필수 체크는 `ci` 한 개(GitHub Actions, `app_id` 15368)다. `ci` job이 실제 PR에서 한 번 성공한 뒤 적는다.
- `patterns_allowed`에는 workflow가 쓰는 GitHub 밖 action을 `owner/repo@*`로 적는다. [ci.yml](ci.yml)만 쓰면 `jdx/mise-action@*` 하나다.
- 기능을 쓸 수 없는 저장소는 `exceptions`에 `{"<경로>": {"status": "unsupported" 또는 "not_applicable", "reason": "...", "evidence": "..."}}`로 적고 `expected`에서 그 경로를 뺀다. 예외로 둘 수 있는 것은 `repository`를 뺀 항목 통째, `repository.security_and_analysis.<기능>.status`(`dependabot_security_updates`, `secret_scanning`, `secret_scanning_push_protection`), `actions.sha_pinning_required`다. 병합 방식과 저장소 정체는 예외로 둘 수 없다.

## plan과 apply

소유자가 자기 기기에서 한다. 에이전트는 `apply`를 돌리지 않는다(AGENTS.md 「하지 않는 것」).

```sh
python3 -I .baseline/baseline.py github plan
python3 -I .baseline/baseline.py github apply
```

- `plan`은 GitHub REST(`gh api`)로 읽기만 한다. 다른 값마다 `github: 차이: <경로>: <지금> -> <기준>`과 고치는 요청 `github: 계획: <메서드> <경로>`를 출력한다. 차이가 없으면 `github: 차이 없음: <저장소>`이고 종료 코드 0이다. 차이나 사람이 할 일이 있으면 1, 읽지 못하거나 설정 파일이 틀리면 2다.
- `apply`는 같은 계획을 쓰고 나서 다시 읽어 비교한다. 같으면 `github: 통과: <저장소> 설정과 라벨이 기준과 같다`다. 쓰다가 실패하면 이미 쓴 요청과 결과를 모르는 요청을 출력하고 멈춘다. 다시 하기 전에 `plan`을 본다.
- 하지 않는 것(`github: 사람이 할 일:` 줄): 공개 여부 변경, ruleset 지우기, 이름이 겹치는 ruleset, 기준이 기록하지 않는 브랜치 보호 값(서명 커밋, push 제한, 리뷰 우회·해제 목록)이 켜진 보호 덮어쓰기, 필수가 아닌 필드. CodeQL 고급 설정 기준이면 그 workflow가 돌 때까지 기본 설정을 끄지 않는다.
- `actions.allowed_actions`가 `selected`가 아니면 `allowed_actions` 목록은 쓰지도 보지도 않는다(GitHub이 그 정책에서는 목록을 두지 않는다). CodeQL 고급 설정 workflow는 `codeql_workflow.path`(`.github/workflows/<이름>.yml`)의 파일 이름으로 읽는다.
- 상태 라벨 5개(`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`, 뜻은 [WORKFLOW.md](../WORKFLOW.md))와 wayfinder 스킬이 쓰는 라벨 5개(`wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task`)는 없으면 만들고, 색이나 설명이 다르면 고친다. 대소문자만 다른 같은 이름은 기준 이름으로 바꾼다. 다른 라벨은 건드리지 않는다.

새 저장소 순서: 조직 아래 공개 저장소를 만든다 → `init`과 [ci.yml](ci.yml)을 PR 하나로 연다(소유자가 화면에서 병합) → 위 설정 파일을 PR로 더한다 → 소유자가 `plan`을 읽고 `apply`를 돌린다 → `plan`이 `차이 없음`을 출력한다.

## 선택: Claude GitHub 앱과 PR auto-fix

Projects 스레드나 클라우드 세션이 CI 실패와 리뷰 지적을 PR에서 바로 고치게 하려면 켠다. 켜지 않아도 코어는 돈다.

- PR auto-fix(`/autofix-pr`)는 Claude GitHub 앱이 그 저장소에 설치되어 있어야 돈다. 앱을 설치할 저장소와 권한은 소유자가 정한다. 앱 권한은 저장소 설정이라 `github apply`가 다루지 않는다.
- 고친 커밋도 head를 바꾸므로 다시 리뷰한 뒤 `enqueue`한다(POLICY §5).
- 근거: [Use Claude Code in the cloud](https://code.claude.com/docs/en/claude-code-on-the-web) 「GitHub authentication options」「Auto-fix pull requests」(2026-11-24 확인). 이 저장소에서 켜 보지는 않았다.

## CodeRabbit 설정

[.coderabbit.yaml](.coderabbit.yaml)은 리뷰 언어를 한국어(`ko-KR`)로 정하고 자동 리뷰를 끈다(`reviews.auto_review.enabled: false`). 리뷰 봇은 어려움 PR에서만 PR을 연 세션이 요청한다(POLICY §3). 근거 문서와 확인일은 파일 주석에 있다. `inheritance: true`라 이 파일에 없는 키는 바로 아래 설정 단계(Central YAML이 없으면 CodeRabbit 웹 설정)를 따른다. 저장소마다 다른 값이 없는 공통 파일이다.

- 저장소 루트에 CodeRabbit 설정 파일이 없으면 그대로 복사한다. `cmp <repo-baseline>/github/.coderabbit.yaml .coderabbit.yaml`이 아무것도 출력하지 않아야 한다.
- `.coderabbit.yaml`이 이미 있으면 `language: "ko-KR"` 줄과 `reviews.auto_review.enabled: false`만 합친다.
- `.coderabbit.yml`이나 `.coderabbit.config.ts`가 있으면 넣지 않고 PR 본문에 적어 소유자에게 남긴다. YAML 파일이 있으면 CodeRabbit은 `.coderabbit.config.ts`를 무시한다([configuration-overview](https://docs.coderabbit.ai/guides/configuration-overview), 2026-11-16 확인).
- 어긋나면(문서·쉬움 PR에 리뷰가 붙거나 언어가 다르면) CodeRabbit 웹의 조직 global override를 소유자가 본다. 그 값이 저장소 YAML보다 우선한다(같은 문서).

## 조직 설정

저장소를 조직으로 옮기기 전에 소유자가 화면에서 한 번 맞춘다. `github apply`는 저장소 설정만 다룬다. 조직은 무료 플랜이면 된다(2026-11-16 `minjunkim-labs`에서 맞춤). 무료 조직은 조직 ruleset을 강제하지 않아서 공통값은 `GITHUB_SETTINGS`에 둔다.

| 화면 | 값 |
| --- | --- |
| Settings → Advanced Security → Configurations | 새 구성 하나: 시크릿 스캔과 push 보호, CodeQL default setup, Dependency graph, Dependabot 알림과 보안 업데이트, 비공개 취약점 보고를 Enabled. 새 Public 저장소의 기본값으로 두고 강제하지 않는다(강제하면 `github apply`가 설정을 바꾸지 못한다) |
| Settings → Member privileges | 저장소 만들기·공개 여부 변경·삭제와 이전·GitHub App 설치·팀 만들기를 끈다. 기본 권한은 Read |
| Settings → Actions → General | 외부 기여자 workflow는 모두 승인, Workflow permissions는 Read, Actions의 PR 만들기·승인은 끈다 |
| Settings → Authentication security | 2FA 필수. 켜기 전에 2FA가 없는 외부 협력자를 본다(조직에서 빠진다) |

개인 계정 저장소는 `gh api --method POST repos/<개인>/<이름>/transfer -f new_owner=<조직>`으로 옮긴다(소유자만). 옮기면 시크릿 스캔, push 보호, CodeQL default setup이 꺼지므로 `github apply`로 다시 켠다.
