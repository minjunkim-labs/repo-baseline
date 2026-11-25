- v2: `docs/agents/`의 `issue-tracker.md`·`domain.md`·`triage-labels.md`는 시작 파일이 됐다. 고쳐 써도 `check`가 실패하지 않고 `upgrade`가 덮어쓰지 않는다. `.gitattributes`는 맨 앞의 `* text=auto eol=lf` 줄만 관리하니, 그 아래에 저장소의 규칙(binary, LFS)을 더한다. `migrate`가 그 줄을 넣었으면 `git add --renormalize .`을 커밋한다.
  새 판의 코어 줄과 똑같은 저장소 줄이 코어 줄 바로 아래에 있으면, `upgrade`는 그 줄을 코어 줄로 본다. 판을 올린 뒤 `.gitattributes`의 diff를 확인한다.
