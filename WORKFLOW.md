# 작업 흐름

v2 저장소에서 단계마다 쓰는 스킬, 실행 위치마다 적용되는 것, 클라우드 환경과 샌드박스 설정이다. 규칙은 [POLICY.md](POLICY.md)가 정한다.

## 단계별 스킬

Matt Pocock 스킬이 뼈대이고, pstack은 Matt가 비우는 칸에만 쓴다. (사람)은 사람만 부르는 스킬(`disable-model-invocation`)이다. 에이전트는 이름을 대고 실행을 권한다. 도구가 스킬을 불러오지 못하면 그 스킬의 `SKILL.md`를 직접 읽고 따른다. 사람만 부르는 스킬은 사람이 그렇게 시킨다.

| 단계 | 쓸 스킬 | 쓰지 않는 것 |
| --- | --- | --- |
| 접수·설계 | 작은 diff는 바로 구현. 크면 Matt `grill-with-docs`(사람), 세션 하나를 넘으면 `wayfinder`(사람). 인터페이스는 `codebase-design` | pstack `architect`(겹침) |
| 스펙·티켓 | `to-spec` → `to-tickets`(사람). spec이 원본 Issue다. spec Issue에는 상태 라벨을 두지 않고(`to-spec`이 붙이는 `ready-for-agent`는 뗀다), 티켓 PR은 `Closes #<티켓>`으로 자기 티켓을 닫고, 마지막으로 병합하는 티켓 PR만 큐에 넣기 전에 `Closes #<spec>`을 더 적는다(티켓을 나란히 돌리면 마지막 PR은 병합 순서로 정해진다). 티켓은 GitHub blocked-by 관계와 상태 라벨을 쓴다 | |
| 구현 | spec 뒤에는 티켓마다 새 세션. 막힘이 없는 티켓은 세션을 나란히 띄운다(세션마다 worktree·PR). `tdd`, 버그면 먼저 `diagnosing-bugs` | Matt `implement`·`implement-spec`(구현 세션이 리뷰를 짜고 판정하며 결과를 PR에 남기지 않아 POLICY §3 리뷰를 대신하지 못함. 함께 쓰면 리뷰가 두 번 돈다), pstack `tdd`(겹침), `poteto-mode`(흐름·병합 단계가 뼈대와 부딪힘) |
| 검증 | 바뀐 동작을 직접 돌려 보고 Evidence 「실행 확인」에 쓴다(POLICY §2). 돌리는 법이 까다로운 앱(화면·게임 등)은 그 절차를 pstack `create-verification-skill`(사람)로 프로젝트 스킬에 남긴다 | |
| 리뷰 | `prompts/review.md`가 Matt `code-review`에 두 축을 맡긴다. 어려움 PR은 같은 새 세션이 보안 관점까지 본다. pstack `blast-radius`(사람, 영향 범위)·`interrogate`(사람, 보안 관점)는 소유자가 원할 때만 | |
| PR 본문 | 칸은 PR 템플릿이 정한다. Matt `pr`은 글쓰기 지침으로만 쓴다 | pstack `ketchup`·`show-me-your-work` |
| 회고 | `prompts/retro.md` | pstack `correct`는 선택 |

pstack 스킬에 적힌 Cursor 경로는 다른 도구에서 바꿔 읽는다. `create-verification-skill`이 만드는 `.cursor/skills/verify-<app>/`는 `.claude/skills/verify-<app>/`에 두고, 그 `SKILL.md` 경로를 프로젝트 `AGENTS.md` 길잡이 표에 한 줄로 적는다(`.agents/skills/`만 읽는 도구도 찾게). 이 스킬은 프로젝트만의 스킬이다. `arena`가 읽는 `~/.cursor/rules/pstack-models.mdc`가 없으면 스킬에 적힌 기본값을 쓴다.

Matt 스킬은 트래커·라벨·도메인 문서 설정을 `docs/agents/`에서 읽는다. `/setup-matt-pocock-skills`가 만드는 파일(`issue-tracker.md`는 GitHub, `triage-labels.md`는 아래 상태 라벨 5개, `domain.md`는 루트 `GLOSSARY.md`와 `docs/adr/`)을 고정한 판의 seed 그대로 둔 관리 파일이다.

| 상태 라벨 | 뜻 |
| --- | --- |
| `needs-triage` | 아직 분류하지 않았다 |
| `needs-info` | 답이나 자료를 기다린다 |
| `ready-for-agent` | 범위와 완료 기준이 정해져 에이전트가 시작할 수 있다(막힘 관계는 따로 본다) |
| `ready-for-human` | 사람이 해야 한다 |
| `wontfix` | 하지 않는다 |

라벨은 소유자가 `python3 -I .baseline/baseline.py github apply`로 만든다([github 프로필](github/README.md)). wayfinder가 쓰는 `wayfinder:*` 라벨 5개도 함께 만든다.

### pstack 절

pstack을 쓰는 저장소는 `AGENTS.md`의 관리 블록 밖에 아래 절을 붙인다. pstack을 부르지 않으면 아무 일도 하지 않고, 누가 부르면 기본 동작(병합 등)을 막는다. repo-baseline 클론이 없는 세션도 읽도록 글을 그대로 옮긴다.

```markdown
## pstack

pstack 스킬은 사람이 요청할 때만 쓴다. 이 저장소의 규칙이 pstack 기본 동작보다 먼저다.

- `poteto-mode`의 Shipping playbook과 병합·auto-merge 단계는 쓰지 않는다. 병합은 POLICY §5대로 한다.
- `correct`는 제안까지만 한다. 사람이 고른 것만 반영한다.
- 판단 규칙은 `AGENTS.md`가 아니라 `REVIEW.md` 「배운 규칙」에 둔다.
- `create-verification-skill`의 결과는 에이전트 도구가 읽는 저장소 스킬 경로(Claude `.claude/skills/`, Codex·Cursor `.agents/skills/`)에 두고, 실행 명령을 `AGENTS.md`의 check·test에 잇는다. 그 경로는 에이전트 설정 폴더라서 그 PR은 되돌리기 어려움이고 소유자가 병합한다(POLICY §4).
- `interrogate`·`blast-radius`는 리뷰에 관점을 더할 뿐이다. 리뷰는 그대로 새 세션에서 `prompts/review.md`로 받는다.
- 서로 다른 모델로 검토하지 않았으면 그 사실을 보고에 적는다.
```

### 계획 도구(Linear)

GitHub Issue가 원본이다(POLICY §8). 목표·완료 조건·결정 기록·열림과 닫힘·하위 Issue·차단 관계와 상태 라벨은 Issue에 둔다. Linear를 쓰면 Linear의 GitHub Issues 동기화로만 붙이고, 사이클·프로젝트·공개하지 않을 판단만 Linear에 둔다. 차단 관계는 동기화되지 않는다. 제목·설명·우선순위·동기화 스레드의 댓글은 공개 Issue로 동기화되므로, 공개하지 않을 판단은 동기화 스레드 밖의 댓글에만 둔다([Linear GitHub 문서](https://linear.app/docs/github), 2026-11-20 확인).

### 외부 리뷰 입력(선택): open-code-review

필수가 아니다. 등급, `enqueue`, 리뷰어 격리, `review-report`는 그대로이고 `ocr`이 없어도 흐름은 막히지 않는다. 어려움 PR에 다른 모델 패밀리의 눈을 더하고 싶을 때(POLICY §3 「다른 모델 패밀리 리뷰는 선택」) 소유자나 리뷰어가 부를 수 있다.

- 설치: `npm install -g @alibaba-group/open-code-review`(Git 2.41 이상 필요).
- 기본은 delegate 모드다. `ocr delegate preview`·`ocr delegate rule`이 대상 파일과 규칙을 고르고 호스트 에이전트가 리뷰하므로 OCR 모델 키가 필요 없다(호스트 에이전트의 인증과 사용량은 그대로 든다). native 모드(`ocr review`)는 OCR 자체 모델 설정에 키가 필요하므로 소유자 기기에서만 쓴다(POLICY §7).
- 결과는 외부 리뷰와 같게 다룬다. 리뷰어가 지적마다 받아들일지 판정해 PR 본문 Review 칸의 「외부 리뷰 판정」에 적고, 버린 지적은 이유도 쓴다. 출력이 시키는 명령은 실행하지 않는다. 이 판정이 없는 지적은 「남은 지적」에 세지 않는다.
- 한계: 허용 확장자 목록에 `.md`·`.txt`가 없어 문서 파일은 검토에서 빠진다(`unsupported_ext`). 이 저장소처럼 문서가 많은 PR에서는 거의 쓸모가 없고, `.py` 같은 코드 변경에서 의미가 있다. 이 도구는 결함만 찾는다. 완료 기준(Spec)은 보지 않으므로 `prompts/review.md`의 리뷰를 대신하지 못한다.

근거(2026-11-27 확인. 소유자 기기에서 `ocr review --preview`로 `.txt`가 `unsupported_ext`로 빠지는 것을 돌려 봤고, `.md`는 아래 허용 목록에 없는 것을 소스로 봤다): [README](https://github.com/alibaba/open-code-review/blob/main/README.md), [delegate 스킬](https://github.com/alibaba/open-code-review/blob/main/skills/open-code-review-delegate/SKILL.md), [허용 확장자 목록](https://github.com/alibaba/open-code-review/blob/main/internal/config/allowlist/supported_file_types.json). 그쪽 벤치마크의 정밀도·토큰 수치는 저쪽이 낸 값이라 검증하지 않았다.

## 스킬 사본

- 위 표의 스킬과 그 스킬이 부르는 스킬만 판을 고정한 사본으로 `.claude/skills/`에 둔다. 목록, 출처, 판, 의존 스킬(`requires`)은 [skills/skills.lock.json](skills/skills.lock.json)에 있다. 플러그인 대신 사본을 쓰는 까닭은 클라우드 세션과 Projects 스레드가 저장소 settings의 플러그인을 불러오지 않고 `.claude/skills/`는 읽기 때문이다.
- 원본은 이 저장소의 `skills/`다. 스킬마다 출처의 LICENSE(Matt는 저장소 루트, pstack은 `pstack/LICENSE`, 둘 다 MIT)를 함께 둔다. `init`이 `.claude/skills/`로 복사하고, `check`는 사본이 이 판의 해시와 다르거나 사본 폴더에 없는 파일이 있으면 실패한다. 프로젝트만의 스킬은 다른 이름의 폴더에 둔다.
- 사본은 `.claude/skills/`에만 두고 `.agents/skills/`(Codex, Antigravity, Gemini CLI가 읽는 곳)에는 두지 않는다. 이 스킬들은 도구마다 전역에도 깔려 있는 경우가 많아, 저장소 사본을 더하면 같은 이름이 둘 이상 생기고 판이 갈린다. 판의 기준은 이 사본과 lock이다. 로컬에서는 같은 이름의 전역 스킬이 대신 불릴 수 있으니, 전역 설치도 lock의 판(Matt는 태그)에 맞춘다. 스킬을 불러오지 못하는 도구는 위 「단계별 스킬」대로 `SKILL.md`를 직접 읽는다. 스킬이 없어 실제로 막힌 일이 생기면 다시 본다(POLICY §6).
- 갱신 기준은 출처마다 lock에 있다. 태그가 있는 출처(Matt)는 나온 지 `days`(7)일이 지난 가장 새 태그를 받는다. 태그 날짜는 태그 객체의 날짜이고, 자기 날짜가 없는 가벼운 태그(lightweight)는 받지 않는다. 고정한 커밋보다 앞서지 않는 태그는 건너뛴다. 태그가 없는 출처(pstack의 `cursor/plugins`)는 `branch`에서 `days`일보다 오래된 마지막 커밋을 받고, `plugin.json`의 `version`과 커밋 SHA를 함께 적는다. 판은 앞으로만 간다. 우리 스킬의 바이트가 그대로면 받지 않는다.
- 한 출처의 스킬은 한 판으로 함께 바뀐다. 그래서 `requires`는 같은 출처의 스킬만 적을 수 있다.
- `requires`는 그 스킬이 실행하라고 부르는 스킬이다(예: `blast-radius` → `arena`·`unslop`, `interrogate` → `arena`·`in-your-own-words`). "per the X skill"처럼 참고로만 가리키는 스킬(`arena`가 가리키는 `poteto-mode`, principle 스킬)은 복사하지 않는다. lock에 스킬을 더하면 새 판이 없어도 `skills-bump`가 고정한 판에서 받는다.

### 갱신하는 법

1. `.github/workflows/skills-bump.yml`이 주 1회 `python3 -I baseline.py skills-bump --check`를 돌린다. 새 판이 있으면 Issue 「skills-bump: 새 스킬 판」을 열거나 본문을 바꾼다. 모델은 쓰지 않는다.
2. 소유자가 repo-baseline 클론에서 `python3 -I baseline.py skills-bump`를 돌린다(에이전트 샌드박스는 `.claude/` 쓰기를 막는다). `skills/`, `.claude/skills/`, lock, `baseline.py`의 `MANAGED`, `.baseline/`, `.claude/settings.json`의 고정 해시를 바꾼다. 받은 바이트는 REST 트리의 blob SHA와 맞춰 본다. symlink·submodule과 1MiB 넘는 파일은 받지 않는다. 바꿀 스킬 폴더에 커밋하지 않은 변경(추적하지 않는 파일 포함)이 있거나, 쓰는 경로에 symlink가 있으면 아무것도 쓰지 않고 멈춘다.
3. 그 세션이 PR을 연다. 민감한 파일을 바꾸므로 어려움이고, 소유자가 diff를 읽고 병합한다. 바뀐 스킬이 위 표나 POLICY와 어긋나면(예: 같은 세션 리뷰, 병합 단계 추가) PR 본문에 적는다.

workflow가 PR까지 열지 않는 까닭(2026-11-23 실측, #182): `workflow_dispatch`로 띄운 CI의 `ci` check run은 그 커밋에서 성공했지만 PR의 check 목록에 들어가지 않아 PR이 `BLOCKED`로 남았다. 이 저장소는 GitHub Actions가 PR을 만들지 못하게 되어 있다(`can_approve_pull_request_reviews: false`). 앱 토큰 같은 장기 비밀값은 더하지 않는다.

## 실행 위치마다 적용되는 것

도구는 고르지 않는다. 흐름은 어느 도구로 해도 막히지 않아야 하고, 실행 위치의 종류로 규칙을 정한다. 종류는 두 축으로 나눈다. 어디서 도는가(내 기기, 클라우드)와 세션이 몇 개인가(하나, 여럿)다. 폰이나 웹에서 지시해도 실행이 내 기기에서 되면(원격 연결) 내 기기다. 모든 단계는 클라우드 없이 내 기기만으로 끝낼 수 있어야 한다. 리뷰처럼 구현과 다른 컨텍스트가 필요한 단계는 내 기기에서 세션을 나눈다(로컬 다중). 클라우드 칸은 같은 단계를 다른 곳에서 하는 선택이다. 도구에 어떤 칸이 없으면 그 단계를 내 기기에서 한다.

| | 세션 하나 | 세션 여럿 |
| --- | --- | --- |
| 내 기기 | 로컬 단독 | 로컬 다중: 한 세션이 하위 에이전트나 다른 세션(worktree)을 띄운다 |
| 클라우드 | 클라우드 단독: 제공자의 환경이 저장소 하나를 받아 작업한다 | 클라우드 다중: 한 작업이나 화면이 클라우드 세션 여러 개를 띄운다 |

다중에서 보는 것은 두 가지다. 세션마다 아래 표의 무엇(지침, 스킬, deny·훅, GitHub, 비밀값)을 받는가, 리뷰하는 세션이 구현 대화에서 떨어져 있는가(POLICY §3)다. 세션을 띄우고 추적하는 코디네이터가 있는지는 규칙을 바꾸지 않는다. 다중의 세션은 각각 같은 줄의 단독 칸을 따른다.

### 도구별로 확인한 것

`?`는 공식 문서에서 찾지 못한 것이다. 되는 것으로 보지 않는다. 「로컬」 줄은 원격 연결을 포함한다.

| 도구·위치 | 지침 파일 | 저장소 스킬 폴더 | 저장소 deny·훅 | GitHub | 비밀값 |
| --- | --- | --- | --- | --- | --- |
| Claude Code 로컬 | `CLAUDE.md`(`@AGENTS.md`) | `.claude/skills/` | `.claude/settings.json` 적용 | 로컬 `gh` 전부 | 내 기기 |
| Claude Code 클라우드 단독 | 같음 | 같음 | 적용 | 브랜치 push·REST 됨. GraphQL(`gh pr`·`gh issue` 포함), 태그 push, 브랜치 삭제는 프록시가 거부 | 클라우드 환경 |
| Claude Code 클라우드 다중(Projects 스레드) | 같음 | 같음. 이름이 `.`으로 시작하는 저장소가 있거나 자체 호스팅 환경이면 불러오지 않는다 | 적용 안 됨 | 같음 | 클라우드 환경 |
| Codex 로컬 | `AGENTS.md`(`CLAUDE.md`는 fallback 설정 때만) | `.agents/skills/` | `.codex/`(신뢰한 프로젝트만) | 로컬 | 내 기기 |
| Codex 클라우드 단독 | `AGENTS.md` | `.agents/skills/` | ? | push·PR 됨, `gh`·GraphQL ? | network secret은 자리표시자만 보임 |
| Cursor 로컬 | `AGENTS.md`, `.cursor/rules/`(CLI는 `CLAUDE.md`도) | `.agents/`·`.cursor/`·`.claude/`·`.codex/`의 `skills/` | `.cursor/hooks.json`, `.cursor/cli.json` deny, `.cursor/sandbox.json` | 로컬 | 내 기기 |
| Cursor 로컬(Remote Control, 자체 워커) | 로컬과 같음 | ? | 프로젝트 훅 실행 | 로컬 | 기기 인증 |
| Cursor 클라우드 | `AGENTS.md` | 저장소 폴더는 ?, 내 기기의 `~/.agents/skills/`·동기화하지 않은 스킬은 안 감 | `.cursor/hooks.json`의 command 훅만, deny ? | push·PR 됨(좁은 토큰), GraphQL ? | 대시보드 Secrets. Environment Variable은 에이전트에 보임 |
| Grok CLI 로컬 | `AGENTS.md`·`CLAUDE.md` 등 모두 | `.grok/`·`.agents/`·`.claude/`·`.cursor/`의 `skills/` | `.grok/` 설정·훅과 `.claude/settings.json` deny·훅(신뢰 폴더) | 로컬 | 환경 변수를 모두 물려받는 것이 기본 |
| Grok 클라우드(Grok Bot) | ? | ? | 저장소 설정 없음(앱 설정의 규칙) | ?(코딩은 Cursor Cloud Agents에 넘김) | Vault·secret 카드, 모델에 안 보임 |
| Antigravity 로컬 | `AGENTS.md`, `GEMINI.md`, `.agents/rules/` | `.agents/skills/` | `.agents/hooks.json`, deny는 전역 설정만 | ? | ? |
| Gemini CLI 로컬 | `GEMINI.md`(`context.fileName`으로 `AGENTS.md`) | `.gemini/`·`.agents/`의 `skills/` | `.gemini/settings.json`·훅(신뢰 폴더) | ? | `.env`는 신뢰 폴더만 |
| Antigravity 클라우드(Remote Agents) | ? | 내 기기 스킬은 안 감, 저장소 ? | permissions는 원격 설정 | OAuth로 clone, push·PR ? | OAuth 토큰만 |
| Jules 클라우드 | `AGENTS.md` | ? | ? | GitHub 앱으로 브랜치 push, API는 `AUTO_CREATE_PR`일 때만 PR(기본은 만들지 않음), `gh` ? | 시크릿 설정 없음 |

클라우드 다중은 도구마다 모양이 다르다. Claude는 Projects, Cursor는 Agents Window와 클라우드 하위 에이전트, Codex는 한 작업 안의 하위 에이전트, Grok Bot은 주 Bot이 다른 Bot을 조율, Antigravity는 remote project의 대화 목록이다.

로컬 다중에서 Claude Code가 세션마다 주는 것:

- 데스크톱 앱이 worktree에서 띄운 세션은 settings·훅·스킬·하위 에이전트 정의·`.mcp.json`을 main checkout 루트에서 읽고, 훅도 그 루트에서 돈다. `CLAUDE.md`와 `.claude/rules/`는 worktree에서 읽는다. 그래서 PR이 바꾼 settings·훅·스킬은 그 PR의 worktree 세션에 적용되지 않는다. 코어 훅은 작업 중인 worktree를 훅 입력의 `cwd`로 찾는다.
- 하위 에이전트는 부모 대화의 권한 규칙을 물려받고, settings 파일의 훅도 하위 에이전트 안에서 돈다. 보통 하위 에이전트는 받은 프롬프트로 새로 시작한다. fork는 부모의 대화 기록 전체를 물려받으므로 구현 대화에서 떨어져 있지 않다.

근거(2026-11-24 확인, 「2026-11-25 확인」 표시는 그날): Claude [Claude projects](https://code.claude.com/docs/en/claude-projects)·[Cloud environments](https://code.claude.com/docs/en/cloud-environments)·[Settings](https://code.claude.com/docs/en/settings), 2026-11-25 확인 [Worktrees](https://code.claude.com/docs/en/worktrees) 「What worktrees share with the main checkout」·[Subagents](https://code.claude.com/docs/en/sub-agents) 「Fork the current conversation」·[Cloud environments](https://code.claude.com/docs/en/cloud-environments) 「GitHub proxy」. Codex [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)·[Skills](https://learn.chatgpt.com/docs/build-skills)·[Rules](https://learn.chatgpt.com/docs/agent-configuration/rules)·[Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments)·[Remote connections](https://learn.chatgpt.com/docs/remote-connections), 2026-11-25 확인 [Codex Cloud](https://learn.chatgpt.com/docs/cloud). Cursor [Rules](https://cursor.com/docs/rules)·[Skills](https://cursor.com/docs/skills)·[Hooks](https://cursor.com/docs/hooks)·[CLI permissions](https://cursor.com/docs/cli/reference/permissions)·[Cloud agent setup](https://cursor.com/docs/cloud-agent/setup)·[GitHub](https://cursor.com/docs/integrations/github), 2026-11-25 확인 [Skills](https://cursor.com/docs/skills) 「Cloud Agents」. Grok CLI에 딸린 사용자 가이드(`~/.grok/docs/user-guide/` 08·10·12·22번), [Grok Bot](https://docs.x.ai/grok-bot/how-grok-bot-works)·[승인과 보안](https://docs.x.ai/grok-bot/approvals-security-and-privacy). Google [Antigravity rules](https://antigravity.google/docs/rules)·[skills](https://antigravity.google/docs/skills)·[hooks](https://antigravity.google/docs/hooks)·[remote agents](https://antigravity.google/docs/remote-agents), [Gemini CLI GEMINI.md](https://geminicli.com/docs/cli/gemini-md/)·[skills](https://geminicli.com/docs/cli/skills/), [Jules](https://jules.google/docs/), 2026-11-25 확인 [Jules API](https://jules.google/docs/api/reference/) `automationMode`.

### v2에 주는 뜻

- 지침의 원본은 `AGENTS.md` 하나로 맞다. 표에서 확인된 도구는 모두 읽거나 읽게 설정할 수 있고, Gemini CLI만 `context.fileName` 설정이 필요하다. `?`인 곳(Grok Bot, Antigravity 클라우드)은 저장소 지침이 적용된다고 보지 않고 로컬에서 한다.
- 스킬 사본은 `.claude/skills/`에만 있다. Codex, Antigravity, Gemini CLI는 이 폴더를 읽는다고 문서가 말하지 않는다. 이 도구들이 함께 읽는 곳은 `.agents/skills/`다. 사본을 어디에 둘지는 아직 정하지 않았다.
- 저장소 deny·훅은 도구마다 형식이 다르고, 코어는 `.claude/settings.json`만 둔다. 로컬에서는 Claude Code와 Grok CLI만 이 파일을 적용하고, 클라우드는 대부분 적용하지 않거나 문서가 없다. 어느 위치에서나 남는 바닥은 서버(브랜치 보호, 필수 CI, 머지 큐)와 `enqueue` 자신의 검사다. 그래서 check는 CI가 반드시 다시 돌린다.
- 클라우드에서 브랜치 push와 PR이 된다고 확인된 것은 Claude, Codex, Cursor, Jules다. Grok Bot과 Antigravity 클라우드는 문서가 없으니 로컬에서 한다. Claude 클라우드에서는 GraphQL을 쓰는 `gh pr`·`gh issue`가 실패하고, 다른 도구는 문서가 없다. 그래서 Issue를 만들고 고치는 스펙·티켓 단계는 내 기기에서 한다. `enqueue`는 로컬 전용으로 둔다. 클라우드에서도 도는 명령(`check`, `review-preflight`, `budget`)은 GitHub REST만 쓴다.
- 태그 push는 Claude 클라우드가 거부하고 다른 도구는 문서가 없다. 태그는 소유자가 내 기기에서 낸다.
- 비밀값이 필요한 일과 큐 넣기는 내 기기에서 한다. 클라우드에는 병합 권한이 없는 비밀값만 둔다(POLICY §7).
- 흐름은 다중에 기대지 않는다. 쓰더라도 세션마다 위 단독 칸을 따른다. 리뷰를 맡기는 세션이 구현 대화를 물려받는지(fork 등)는 도구마다 확인한다.

## 클라우드 환경 설정

- setup script는 mise를 설치하고 `python3 -I .baseline/baseline.py run setup`을 부른다. `run setup`은 `.mise.toml`에 판이 있으면 `mise install`을 먼저 하고, 다른 `run`은 `mise exec`로 그 판을 쓴다.

```bash
#!/bin/bash
set -euo pipefail
# doctor와 같게 판을 고정한다. .mise.toml의 min_version 이상으로 둔다.
curl -fsSL https://mise.run | MISE_VERSION=v2026.11.9 MISE_INSTALL_PATH=/usr/local/bin/mise sh
if [ -f .baseline/baseline.py ]; then python3 -I .baseline/baseline.py run setup; fi
```

- setup script는 Ubuntu 24.04에서 root로 돈다. 그때 저장소가 현재 폴더에 있는지는 문서가 말하지 않는다. 없으면 `run setup`은 세션 안에서 부른다. 근거: [Cloud environments](https://code.claude.com/docs/en/cloud-environments) 「Setup scripts」(2026-11-24 확인). 이 스크립트를 클라우드에서 돌려 보지는 않았다.
- mise와 도구를 받으려면 허용 도메인에 `mise.run`과 GitHub 릴리스, 도구의 배포처가 있어야 한다.
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
