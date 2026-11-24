# team 프로필 (v2)

선택 프로필이다. 쓰기 권한이 있는 사람이 둘 이상일 때 켠다. 민감한 파일(POLICY §4)을 바꾸는 PR에 정해진 사람의 승인을 받게 한다. 혼자면 켜지 않는다. CODEOWNERS 승인을 필수로 하면 혼자서는 병합하지 못한다. v1 저장소는 [profiles/team/](../profiles/team/)를 따른다.

## 켜는 법

1. [CODEOWNERS](CODEOWNERS)를 `.github/CODEOWNERS`로 복사한다.
2. `@REPLACE-OWNERS`를 쓰기 권한이 있는 두 명 이상, 또는 GitHub 팀(`@org/team`)으로 바꾼다. 팀은 보이는(visible) 팀이어야 하고 저장소에 직접 쓰기 권한이 있어야 한다. 아니면 GitHub이 그 줄을 무시한다.
3. 프로젝트의 의존성 manifest·lockfile과 `REVIEW.md` 「민감한 파일」 절의 경로를 더한다.
4. 1~3을 PR로 열어 기본 브랜치에 병합한다. CODEOWNERS가 기본 브랜치에 없으면 코드 소유자 승인을 요구해도 승인할 사람이 없다.
5. `.github/repository-settings.json`의 `expected.protection.required_pull_request_reviews`에 `"required_approving_review_count": 1`(또는 2)과 `"require_code_owner_reviews": true`를 쓴다.
6. 소유자가 `python3 -I .baseline/baseline.py github plan`을 읽고 `github apply`로 적용한다([github 프로필](../github/README.md)).

승인이 필수가 되면 `enqueue`로 넣은 PR도 승인이 있어야 큐가 병합한다. 리뷰 등급(POLICY §3)은 그대로이고, 승인은 그 위에 서버가 거는 조건이다.
