"""repo-baseline v2: copy the core into a repo and check that it still matches.

Python 3.9+ standard library only. Run with `python3 -I`. In a consumer repo every command
runs from the pinned copy `.baseline/baseline.py`.
"""
import argparse
import ast
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from urllib.parse import quote

VERSION = "2.0.0-dev"
START, END = b"<!-- baseline:start -->\n", b"<!-- baseline:end -->\n"
# The hashes of this version. check trusts these, not only baseline.json, so editing a managed
# file together with baseline.json still fails. test_baseline.py keeps them equal to core/.
MANAGED = {
    ".gitattributes": {"sha256": "d60f352d0db1404c70afb4bb8b2ca3fd1c610572aa40720e8a0b7baa7885418c"},
    "AGENTS.md": {"block_sha256": "5a0264145665fe22598322b9a6c3bbf0f9f96c2c2ffd0b281e948ceb112ef8f1"},
    "CLAUDE.md": {"sha256": "336cc4fbf19beaada7ccf9986414fa91851a8d7a07dfb3ccbe800a69eed0ab49"},
    "REVIEW.md": {"block_sha256": "39e2509ce32401929e7fc6cd8cd5639dfb96e2b0d823813128f11032d44684d7"},
    ".github/pull_request_template.md": {"sha256": "11a271edeca42572a39a609c9b739a08ab9258c9509e23020a1a4d586df48f02"},
    ".claude/hooks/allow_enqueue.py": {"sha256": "b8c387181b4ba1b13ee24074018642e985908d6333aa7c486e6863a083d6d546"},
}
COMMANDS = ("setup", "check", "test", "build")
DEFAULT_COMMANDS = {
    "setup": "N/A: 아직 정하지 않았다",
    "check": ["python3", "-I", ".baseline/baseline.py", "check"],
    "test": "N/A: 아직 정하지 않았다",
    "build": "N/A: 아직 정하지 않았다",
}
# Shell syntax only through `sh -c`, so every command runs the same on macOS, Linux and WSL2.
OTHER_SHELLS = {"bash", "zsh", "fish", "ksh", "dash", "csh", "tcsh"}
BUDGET_LINES, BUDGET_BYTES = 60, 4000
# What an easy-PR reviewer reads before the diff. prompts/review.md lives in repo-baseline only.
REVIEW_READ, REVIEW_BYTES = ("AGENTS.md", "REVIEW.md", "prompts/review.md"), 13000
MAX_READ = 1 << 20

# review-preflight
BASELINE_REPO, TAG = "minjunkim-labs/repo-baseline", "v{}"
BOT = "dependabot[bot]"
INSTRUCTIONS = {"AGENTS.MD", "CLAUDE.MD", "REVIEW.MD"}
DOC_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")
AGENT_DIRS = {".claude", ".agents", ".codex", ".cursor"}
# shortcut: common manifest and lockfile names only; add a name when a repo's Dependabot touches another.
MANIFESTS = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock",
    "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile", "Pipfile.lock", "setup.py", "setup.cfg",
    "Gemfile", "Gemfile.lock", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "composer.json", "composer.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "gradle.lockfile", "libs.versions.toml",
    "gradle-wrapper.properties", "Package.swift", "Package.resolved", "Podfile", "Podfile.lock",
    "pubspec.yaml", "pubspec.lock", "mix.exs", "mix.lock", "packages.lock.json", "Directory.Packages.props",
}
# enqueue
GRADES = ("문서", "쉬움", "어려움")
STANDING = "- 상시 지시:"
STANDING_COMMAND = "`python3 -I .baseline/baseline.py enqueue <PR> <리뷰한 head>`"
SHA_RE = re.compile(r"[0-9a-f]{40}")
PASSED = {"success", "neutral", "skipped"}
PR_QUERY = ("query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest("
            "number:$number){id body createdAt userContentEdits(last:100){nodes{editedAt editor{__typename}}}}}}")
ENQUEUE = ("mutation($id:ID!,$sha:GitObjectID!){enqueuePullRequest(input:{pullRequestId:$id,expectedHeadOid:$sha})"
           "{mergeQueueEntry{position}}}")
HASH_RE = re.compile(r"\b[0-9a-f]{32,}\b|sha(?:1|256|384|512)-[A-Za-z0-9+/]+=*")
VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


def read_file(root, rel):
    """check and budget read a PR tree in CI: regular files only, at most MAX_READ bytes.
    No symlink anywhere on the way: git ignores a symlinked .gitattributes, a linked .github moves the
    PR template, and a link to /dev/zero never ends."""
    path = root
    for part in Path(rel).parts:
        path = path / part
        if path.is_symlink():
            raise OSError("없거나 일반 파일이 아니다(symlink는 안 된다)")
    if not path.is_file():
        raise OSError("없거나 일반 파일이 아니다(symlink는 안 된다)")
    with path.open("rb") as f:
        data = f.read(MAX_READ + 1)
    if len(data) > MAX_READ:
        raise OSError(f"{MAX_READ}바이트를 넘는다")
    return data


def dump_json(obj):
    """Same bytes on every OS: sorted keys, LF, one final newline."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def block(data):
    """The bytes between the managed-block markers, or None unless there is exactly one block."""
    lines = data.splitlines(keepends=True)
    if lines.count(START) != 1 or lines.count(END) != 1:
        return None
    start, end = lines.index(START), lines.index(END)
    return b"".join(lines[start + 1:end]) if start < end else None


def digest(data, kind):
    if kind == "sha256":
        return sha256(data)
    inner = block(data)
    return None if inner is None else sha256(inner)


def repo_root():
    # No resolve(): a symlinked .baseline/baseline.py must not move the root (check then refuses it).
    here = Path(os.path.abspath(__file__)).parent
    return here.parent if here.name == ".baseline" else Path.cwd()


def command_problem(name, value):
    if isinstance(value, str):
        return None if value.startswith("N/A: ") and len(value) > 5 else f"{name}: 문자열이면 'N/A: <이유>'여야 한다"
    if not isinstance(value, list) or not value or not all(isinstance(a, str) and a for a in value):
        return f"{name}: 빈 문자열이 없는 argv 배열이어야 한다"
    if Path(value[0]).name in OTHER_SHELLS:
        return f"{name}: 셸은 [\"sh\", \"-c\", ...]로만 쓴다"
    return None


def command_line(name, value):
    return f"- {name}: `{value if isinstance(value, str) else shlex.join(value)}`"


def load_commands(root):
    """(commands, problems). Problems are messages; commands is None when the file is unusable."""
    try:
        commands = json.loads(read_file(root, ".baseline/commands.json"))
    except (OSError, ValueError) as error:
        return None, [f"commands.json을 읽지 못했다: {error}"]
    if not isinstance(commands, dict):
        return None, ["commands.json은 객체여야 한다"]
    problems = []
    for name in COMMANDS:
        problem = f"commands.json에 {name}이 없다" if name not in commands else command_problem(name, commands[name])
        if problem:
            problems.append(problem)
    return commands, problems


def cmd_init(args):
    target = Path(args.path)
    core = Path(__file__).resolve().parent / "core"
    if not target.is_dir():
        sys.exit(f"init: 폴더가 아니다: {target}")
    if not core.is_dir():
        sys.exit("init: core/가 없다. repo-baseline 클론의 baseline.py로 돌린다")
    files = {p.relative_to(core).as_posix(): p.read_bytes() for p in sorted(core.rglob("*")) if p.is_file()}
    files[".baseline/baseline.py"] = Path(__file__).read_bytes()
    files[".baseline/commands.json"] = dump_json(DEFAULT_COMMANDS)
    files[".baseline/baseline.json"] = dump_json({"version": VERSION, "profiles": [], "managed": MANAGED})
    # Writing through a symlink (even a broken one) lands outside the repo, so stop before any write.
    links = set()
    for rel in files:
        path = target
        for part in (".", *Path(rel).parts):
            path = path / part
            if path.is_symlink():
                links.add(path.as_posix())
    links = sorted(links)
    if links:
        sys.exit("init: symlink는 따라가지 않는다: " + ", ".join(links))
    existing = sorted(rel for rel in files if (target / rel).exists())
    if existing:
        sys.exit("init: 이미 있다(기존 저장소는 migrate로 옮긴다): " + ", ".join(existing))
    for rel, data in files.items():
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_bytes(data)
        print(f"init: {rel}")
    return 0


def cmd_check(args):
    root = repo_root()
    problems = []
    if Path(os.path.abspath(__file__)).parent.name == ".baseline":
        try:
            read_file(root, ".baseline/baseline.py")
        except OSError as error:
            problems.append(f".baseline/baseline.py: {error}")
    try:
        recorded = json.loads(read_file(root, ".baseline/baseline.json"))
    except (OSError, ValueError) as error:
        problems.append(f"baseline.json을 읽지 못했다: {error}")
    else:
        if not isinstance(recorded, dict):
            problems.append("baseline.json은 객체여야 한다")
        elif recorded.get("version") != VERSION:
            problems.append(f"baseline.json의 판 {recorded.get('version')!r}이 baseline.py의 판 {VERSION!r}과 다르다")
        if isinstance(recorded, dict) and recorded.get("managed") != MANAGED:
            problems.append("baseline.json의 관리 해시가 baseline.py 안의 해시와 다르다")
    for rel, expected in MANAGED.items():
        (kind, want), = expected.items()
        try:
            got = digest(read_file(root, rel), kind)
        except OSError as error:
            problems.append(f"{rel}: {error}")
            continue
        if got is None:
            problems.append(f"{rel}: 관리 블록 표시가 하나씩 있어야 한다")
        elif got != want:
            problems.append(f"{rel}: {'관리 블록이' if kind == 'block_sha256' else '파일이'} 이 판과 다르다")
    commands, command_problems = load_commands(root)
    problems += command_problems
    if commands is not None:
        try:
            lines = read_file(root, "AGENTS.md").decode("utf-8").splitlines()
        except (OSError, ValueError):
            lines = []
        for name in COMMANDS:
            if name not in commands:
                continue
            found = [line for line in lines if line.startswith(f"- {name}: ")]
            if found != [command_line(name, commands[name])]:
                problems.append(f"AGENTS.md 명령 칸 {name}이 commands.json과 다르다. 이 한 줄이어야 한다: "
                                + command_line(name, commands[name]))
    for problem in problems:
        print(f"check: {problem}", file=sys.stderr)
    if problems:
        return 1
    print("check: 통과")
    return 0


def cmd_run(args):
    root = repo_root()
    commands, problems = load_commands(root)
    if commands is None:
        sys.exit(f"run: {problems[0]}")
    if args.name not in commands:
        sys.exit(f"run: commands.json에 {args.name}이 없다")
    value = commands[args.name]
    problem = command_problem(args.name, value)
    if problem:
        sys.exit(f"run: {problem}")
    if isinstance(value, str):
        print(f"run: {args.name}은 {value}")
        return 0
    try:
        return subprocess.run(value, cwd=root).returncode
    except OSError as error:
        sys.exit(f"run: {args.name}을 시작하지 못했다: {error}")


def cmd_budget(args):
    root = repo_root()
    read = {}
    for rel in REVIEW_READ:
        if rel.startswith("prompts/") and not (root / rel).exists() and not (root / rel).is_symlink():
            continue
        try:
            read[rel] = read_file(root, rel)
        except OSError as error:
            sys.exit(f"budget: {rel}: {error}")
    data = read["AGENTS.md"]
    lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    reviewer = sum(map(len, read.values()))
    print(f"budget: AGENTS.md {lines}줄(상한 {BUDGET_LINES}), {len(data)}바이트(상한 {BUDGET_BYTES})")
    print(f"budget: 리뷰어 읽기 {reviewer}바이트(상한 {REVIEW_BYTES}): {', '.join(read)}")
    if lines > BUDGET_LINES or len(data) > BUDGET_BYTES or reviewer > REVIEW_BYTES:
        print("budget: 상한을 넘었다", file=sys.stderr)
        return 1
    return 0


def gh_api(path, raw=False):
    """GitHub REST through `gh api`. Never GraphQL: the cloud sessions' proxy blocks it.
    raw returns file bytes, or None when the file is not there."""
    accept = "application/vnd.github.raw+json" if raw else "application/vnd.github+json"
    result = subprocess.run(["gh", "api", "-H", f"Accept: {accept}", path], capture_output=True)
    if result.returncode:
        if raw and b"(HTTP 404)" in result.stderr:
            return None
        raise OSError(f"gh api {path}: {result.stderr.decode('utf-8', 'replace').strip()}")
    if len(result.stdout) > MAX_READ * 32:
        raise OSError(f"gh api {path}: 응답이 너무 크다")
    if raw:
        if len(result.stdout) > MAX_READ:
            raise OSError(f"{path}: {MAX_READ}바이트를 넘는다")
        return result.stdout
    return json.loads(result.stdout)


def pages(path, key=None):
    """Every item of a paginated REST list (key: the list inside an object response)."""
    items, page = [], 1
    while True:
        data = gh_api(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        chunk = data.get(key) if key else data
        if not isinstance(chunk, list):
            raise ValueError(f"{path}: 목록이 아니다")
        items += chunk
        if len(chunk) < 100:
            return items
        page += 1


def contents(repo, rel, ref):
    return gh_api(f"repos/{repo}/contents/{quote(rel)}?ref={quote(ref)}", raw=True)


def secret_names(paths):
    """(hits, examples): any folder or file name starting with .env is a hit, except .env.example files."""
    hits, examples = set(), set()
    for path in paths:
        *folders, name = path.split("/")
        if any(f.startswith(".env") for f in folders) or (name.startswith(".env") and name != ".env.example"):
            hits.add(path)
        elif name == ".env.example":
            examples.add(path)
    return sorted(hits), sorted(examples)


def is_manifest(name):
    return name in MANIFESTS or fnmatch.fnmatchcase(name, "requirements*.txt") or name.endswith(".csproj")


def is_sensitive(path, patterns):
    parts = path.split("/")
    return (parts[-1] in {".mcp.json", ".mise.toml", "CODEOWNERS"} or is_manifest(parts[-1])
            or any(part in AGENT_DIRS or part in {".github", ".baseline"} for part in parts)
            or any(fnmatch.fnmatchcase(path, p) or path.startswith(p.rstrip("*").rstrip("/") + "/")
                   for p in patterns))


def is_doc(path):
    name = path.rsplit("/", 1)[-1]
    return (name.endswith(DOC_SUFFIXES) and name.upper() not in INSTRUCTIONS and name != "SKILL.md"
            and path not in MANAGED and not path.startswith("prompts/") and "skills" not in path.split("/"))


def outside(data):
    """The bytes around the managed block, which the project writes."""
    if data is None or block(data) is None:
        return data
    lines = data.splitlines(keepends=True)
    return b"".join(lines[:lines.index(START) + 1] + lines[lines.index(END):])


def section(data, title):
    """Non-empty lines of a `## title` section outside the managed block."""
    found, inside = [], False
    for line in (outside(data) or b"").decode("utf-8", "replace").splitlines():
        if line.startswith("## "):
            inside = line == f"## {title}"
        elif inside and line.strip():
            found.append(line.strip())
    return found


def sensitive_patterns(review):
    """The `path` globs in REVIEW.md 「민감한 파일」, in list items or prose: a missed path lowers the grade."""
    return [p for line in section(review, "민감한 파일") for p in re.findall(r"`([^`]+)`", line)]


def embedded_managed(source):
    """MANAGED of a baseline.py, read with ast. The tag's code is never run."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == ["MANAGED"]:
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return None
            if isinstance(value, dict) and all(isinstance(v, dict) and len(v) == 1 and
                                               next(iter(v)) in ("sha256", "block_sha256") for v in value.values()):
                return value
    return None


def upgrade_problem(paths, old, new):
    """None when every changed path holds the bytes recorded by the baseline tag that the PR's
    baseline.json names. old/new read a path at base/head."""
    try:
        before, after = json.loads(old(".baseline/baseline.json") or b""), json.loads(new(".baseline/baseline.json") or b"")
    except ValueError:
        return "baseline.json을 읽지 못했다"
    if not isinstance(before, dict) or not isinstance(after, dict) or not isinstance(after.get("version"), str):
        return "baseline.json이 객체가 아니거나 판이 없다"
    version = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", after["version"])
    current = re.match(r"(\d+)\.(\d+)\.(\d+)", str(before.get("version")))
    if not version:
        return f"판 {after['version']!r}이 X.Y.Z가 아니다"
    if current and (tuple(map(int, version.groups())) < tuple(map(int, current.groups()))
                    or before.get("version") == after["version"]):
        return "판을 올리지 않는다"
    tag = TAG.format(after["version"])
    try:  # a tag only (a branch can have the same name), and one that main already holds
        target = gh_api(f"repos/{BASELINE_REPO}/git/ref/tags/{tag}")["object"]
        if target["type"] == "tag":
            target = gh_api(f"repos/{BASELINE_REPO}/git/tags/{target['sha']}")["object"]
        if target["type"] != "commit":
            return f"태그 {tag}가 커밋을 가리키지 않는다"
        if gh_api(f"repos/{BASELINE_REPO}/compare/{target['sha']}...main")["status"] not in ("ahead", "identical"):
            return f"태그 {tag}가 {BASELINE_REPO} main에 없는 커밋이다"
    except (OSError, KeyError, TypeError) as error:
        return f"태그 {tag}를 읽지 못했다: {error}"
    source = contents(BASELINE_REPO, "baseline.py", target["sha"])
    managed = embedded_managed(source) if source is not None else None
    if managed is None:
        return f"{BASELINE_REPO}의 태그 {tag}에서 baseline.py의 관리 해시를 읽지 못했다"
    want = {".baseline/baseline.py": source,
            ".baseline/baseline.json": dump_json(dict(before, version=after["version"], managed=managed))}
    for path in sorted(paths):
        data = new(path)
        if path in want:
            same = data == want[path]
        elif path in managed and data is not None:
            (kind, hash_), = managed[path].items()
            same = digest(data, kind) == hash_ and (kind == "sha256" or outside(data) == outside(old(path)))
        else:
            same = False
        if not same:
            return f"{path}: 태그 {tag}의 기록과 다르다"
    return None


def bump_problem(patch):
    """None when each changed line only swaps a version or a hash and no major version changes."""
    if not patch:
        return "diff가 없다(바이너리이거나 너무 크다)"
    removed, added = [], []

    def pair():
        if len(removed) != len(added):
            return "더하거나 지운 줄이 있다(새 의존성 등)"
        for old, new in zip(removed, added):
            old, new = HASH_RE.sub("#", old), HASH_RE.sub("#", new)
            before, after = VERSION_RE.findall(old), VERSION_RE.findall(new)
            if VERSION_RE.sub("V", old) != VERSION_RE.sub("V", new) or len(before) != len(after):
                return f"버전·해시 밖의 변경: {new.strip()}"
            if any(a.split(".")[0] != b.split(".")[0] for a, b in zip(before, after)):
                return f"major 업데이트: {new.strip()}"
        removed.clear()
        added.clear()
        return None

    for line in patch.splitlines() + [""]:
        if line.startswith("-") and not added:
            removed.append(line[1:])
            continue
        if line.startswith("+"):
            added.append(line[1:])
            continue
        problem = pair()
        if problem:
            return problem
        if line.startswith("-"):
            removed.append(line[1:])
    return None


def dependabot_problem(repo, pr, fork, files):
    """None when the PR author login and every push to the head branch are dependabot[bot] (git author
    names are free text, so they do not count) and the PR only bumps minor or patch versions."""
    if pr["user"]["login"] != BOT:
        return f"작성자가 {BOT}이 아니다"
    if fork:
        return "fork PR이다"
    # One page only: this endpoint pages by cursor and ignores `page`, so pages() would loop forever.
    pushes = gh_api(f"repos/{repo}/activity?ref={quote(pr['head']['ref'], safe='')}&per_page=100")
    if not isinstance(pushes, list) or len(pushes) >= 100:
        return "head 브랜치의 push 기록을 다 읽지 못했다(100개 이상)"
    if not any(p.get("after") == pr["head"]["sha"] for p in pushes) or any(
            (p.get("actor") or {}).get("login") != BOT for p in pushes):
        return f"head 브랜치에 {BOT}이 아닌 push가 있거나 head를 push한 기록이 없다"
    for f in files:
        name = f["filename"].rsplit("/", 1)[-1]
        if not is_manifest(name) or f.get("status") != "modified":
            return f"{f['filename']}: manifest·lockfile 수정이 아니다"
        problem = bump_problem(f.get("patch"))
        if problem:
            return f"{f['filename']}: {problem}"
    return None


def pr_target(pr, remote):
    match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)/?", pr)
    if match:
        return match.group(1), match.group(2)
    if not pr.isdigit():
        raise ValueError("PR은 번호나 https://github.com/<owner>/<repo>/pull/<번호>다")
    url = subprocess.run(["git", "remote", "get-url", remote], capture_output=True, text=True).stdout.strip()
    match = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$", url)
    if not match:
        raise ValueError(f"remote {remote}가 GitHub 저장소가 아니다: {url!r}")
    return match.group(1), pr


def preflight(repo, number, remote):
    """The report, or None when the head or base moved during the run."""
    pr = gh_api(f"repos/{repo}/pulls/{number}")
    head, base = pr["head"]["sha"], pr["base"]["sha"]
    fork = (pr["head"].get("repo") or {}).get("full_name") != pr["base"]["repo"]["full_name"]
    files = pages(f"repos/{repo}/pulls/{number}/files")
    commits = pages(f"repos/{repo}/pulls/{number}/commits")
    if len(files) >= 3000 or len(commits) >= 250:
        raise OSError("REST가 보여 주는 한도(파일 3000개, 커밋 250개)에 닿아 다 볼 수 없다")
    paths = {p for f in files for p in (f["filename"], f.get("previous_filename")) if p}
    names = set(paths)
    for commit in commits:  # a .env added and renamed inside the PR shows only in its commit
        changed = pages(f"repos/{repo}/commits/{commit['sha']}", "files")
        if len(changed) >= 3000:
            raise OSError(f"커밋 {commit['sha']}의 파일이 REST 한도(3000개)에 닿아 다 볼 수 없다")
        names |= {p for f in changed for p in (f["filename"], f.get("previous_filename")) if p}
    hits, examples = secret_names(names)
    # The contents API follows symlinks, so the bytes alone cannot show a link or a submodule.
    # Both sides count: a PR that turns a link into a file changes what the link used to reach.
    linked = set()
    for sha in (base, head):
        tree = gh_api(f"repos/{repo}/git/trees/{sha}?recursive=1")
        if tree.get("truncated"):
            raise OSError("트리가 커서 REST가 다 보여 주지 않는다")
        linked |= {e["path"] for e in tree["tree"] if e["mode"] in ("120000", "160000")}
    links = sorted({q for p in paths for q in ("/".join(p.split("/")[:i + 1]) for i in range(p.count("/") + 1))
                    if q in linked})
    report = {"pr": int(number), "fork": fork, "head": head, "base": base, "branch": pr["head"]["ref"],
              "author": pr["user"]["login"], "base_branch": pr["base"]["ref"],
              "secret_hits": hits, "unreviewed_examples": examples, "grade": None, "reasons": [],
              "fetch_argv": None, "diff_argv": None}
    if not hits:
        # Grade inputs come from base: the PR cannot list itself out of the sensitive paths.
        cache = {}

        def read(ref):
            def get(rel):
                if (rel, ref) not in cache:
                    cache[rel, ref] = contents(repo, rel, ref)
                return cache[rel, ref]
            return get
        old, new = read(base), read(head)
        patterns = sensitive_patterns(old("REVIEW.md"))
        reasons = [f"민감한 파일: {p}" for p in sorted(paths) if is_sensitive(p, patterns)]
        reasons += [f"symlink·submodule: {p}" for p in links]
        reasons += [f"출력할 수 없는 문자가 있는 경로: {json.dumps(p)}" for p in sorted(paths) if not p.isprintable()]
        for rel, spec in MANAGED.items():
            (kind, _), = spec.items()
            if rel in paths and (kind == "sha256" or old(rel) is None or new(rel) is None
                                 or block(old(rel)) != block(new(rel))):
                reasons.append(f"관리 {'블록' if kind == 'block_sha256' else '파일'}: {rel}")
        if "AGENTS.md" in paths:
            before = set((old("AGENTS.md") or b"").decode("utf-8", "replace").splitlines())
            if any(("enqueue" in line or "상시 지시" in line) and line not in before
                   for line in (new("AGENTS.md") or b"").decode("utf-8", "replace").splitlines()):
                reasons.append("상시 지시 줄을 만들거나 바꿨다: AGENTS.md")
        if "REVIEW.md" in paths and set(patterns) - set(sensitive_patterns(new("REVIEW.md"))):
            reasons.append("「민감한 파일」 경로를 지웠다: REVIEW.md")
        exceptions = []
        if reasons and ".baseline/baseline.json" in paths:
            exceptions.append(("upgrade", upgrade_problem(paths, old, new)))
        if reasons and pr["user"]["login"] == BOT:
            exceptions.append(("Dependabot", dependabot_problem(repo, pr, fork, files)))
        passed = [name for name, problem in exceptions if problem is None and not links]
        if passed:
            report["grade"], reasons = "쉬움", [f"{passed[0]} 예외"]
        else:
            report["grade"] = "어려움" if reasons else "문서" if all(map(is_doc, paths)) else "쉬움"
            reasons += [f"{name} 예외 아님: {problem}" for name, problem in exceptions]
        report["reasons"] = reasons
        report["fetch_argv"] = ["git", "fetch", "--no-tags", remote, base,
                                f"+refs/pull/{number}/head:refs/review-preflight/{remote}/pr/{number}"]
        report["diff_argv"] = ["git", "diff", f"{base}...{head}", "--", ".", ":!.env*", ":!**/.env*"]
    now = gh_api(f"repos/{repo}/pulls/{number}")
    if now["head"]["sha"] != head or now["base"]["sha"] != base:
        return None
    return report


def cmd_review_preflight(args):
    try:
        report = preflight(*pr_target(args.pr, args.remote), args.remote)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"review-preflight: 실행 실패: {error}", file=sys.stderr)
        return 2
    if report is None:
        print("review-preflight: head나 base가 실행 중에 바뀌었다. 다시 실행한다.", file=sys.stderr)
        return 2
    code = 1 if report["secret_hits"] else 0
    if args.json:
        print(json.dumps(report))  # ASCII only, so a non-UTF-8 stdout cannot fail after the checks
        return code
    print(f"PR: {report['pr']}  fork: {'예' if report['fork'] else '아니요'}  branch: {report['branch']}")
    print(f"head: {report['head']}")
    print(f"base: {report['base']}")
    show = lambda paths: ", ".join(p if p.isprintable() else json.dumps(p) for p in paths)  # noqa: E731
    print("미검토(.env.example): " + (show(report["unreviewed_examples"]) or "없음"))
    if code:
        print("리뷰 미완(비밀값 파일): " + show(report["secret_hits"]))
        return code
    print(f"등급: {report['grade']}")
    for reason in report["reasons"]:
        print(f"이유: {show([reason])}")
    print("fetch: " + shlex.join(report["fetch_argv"]))
    print("diff: " + shlex.join(report["diff_argv"]) + "  (저장소 루트에서)")
    return 0


def gh_graphql(query, **fields):
    """GitHub GraphQL. Only enqueue uses it: the merge queue has no REST endpoint, and cloud proxies block it."""
    argv = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in fields.items():
        argv += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    result = subprocess.run(argv, capture_output=True)
    data = json.loads(result.stdout or b"{}") if not result.returncode else {}
    if result.returncode or data.get("errors") or "data" not in data:
        raise OSError(f"gh api graphql: {data.get('errors') or result.stderr.decode('utf-8', 'replace').strip()}")
    return data["data"]


def review_fields(body):
    """The `## Review` fields enqueue reads, each from exactly one `name: value` line."""
    lines = section(body.encode("utf-8"), "Review")
    fields = {}
    for name in ("리뷰한 head", "등급", "남은 지적"):
        values = [line[len(name) + 1:].strip().strip("`") for line in lines if line.startswith(f"{name}:")]
        fields[name] = values[0] if len(values) == 1 else None if not values else ""
    return fields


def required_checks(repo, branch):
    """(context, app id or None) pairs that branch protection and rulesets require on the base branch."""
    need = set()
    protection = (gh_api(f"repos/{repo}/branches/{quote(branch, safe='')}").get("protection") or {})
    checks = protection.get("required_status_checks") or {}
    need |= {(c["context"], c.get("app_id")) for c in checks.get("checks") or []}
    need |= {(c, None) for c in checks.get("contexts") or [] if all(c != n for n, _ in need)}
    for rule in pages(f"repos/{repo}/rules/branches/{quote(branch, safe='')}"):
        if rule.get("type") == "required_status_checks":
            need |= {(c["context"], c.get("integration_id")) for c in rule["parameters"]["required_status_checks"]}
    return need


def ci_problems(repo, sha, need):
    if not need:
        return ["필수 CI가 정해져 있지 않다"]
    runs = pages(f"repos/{repo}/commits/{sha}/check-runs?filter=latest", "check_runs")
    statuses = {s["context"]: s["state"] for s in pages(f"repos/{repo}/commits/{sha}/status", "statuses")}
    problems = []
    for context, app in sorted(need, key=lambda n: (n[0], str(n[1]))):
        mine = [r for r in runs if r["name"] == context and (app in (None, -1) or (r.get("app") or {}).get("id") == app)]
        if mine:
            run = max(mine, key=lambda r: r["id"])
            if run["status"] != "completed" or run["conclusion"] not in PASSED:
                problems.append(f"필수 CI {context}: {run['conclusion'] or run['status']}")
        elif app in (None, -1) and context in statuses:
            if statuses[context] != "success":
                problems.append(f"필수 CI {context}: {statuses[context]}")
        else:
            problems.append(f"필수 CI {context}: 결과가 없다")
    return problems


def account_problems(repo, report, commits):
    """The author and every commit author must be able to push (Dependabot PRs: dependabot[bot] only)."""
    allowed = {}

    def can_push(login):
        if login not in allowed:
            allowed[login] = (login == BOT if report["author"] == BOT else
                              gh_api(f"repos/{repo}/collaborators/{quote(login, safe='')}/permission")
                              .get("permission") in ("admin", "write"))
        return allowed[login]
    problems = [] if can_push(report["author"]) else [f"작성자 {report['author']}에게 쓰기 권한이 없다"]
    for commit in commits:
        login = (commit.get("author") or {}).get("login")
        if not login:
            problems.append(f"커밋 {commit['sha'][:7]}의 작성자를 GitHub 계정으로 알 수 없다")
        elif not can_push(login):
            problems.append(f"커밋 {commit['sha'][:7]}의 작성자 {login}에게 쓰기 권한이 없다")
    return problems


def external_reviews(repo, number, reported):
    """Reviews and comments written or edited after the review report: nobody judged them."""
    items = [(r.get("submitted_at"), r) for r in pages(f"repos/{repo}/pulls/{number}/reviews")]
    for path in (f"pulls/{number}/comments", f"issues/{number}/comments"):
        items += [(max(c["created_at"], c.get("updated_at") or ""), c) for c in pages(f"repos/{repo}/{path}")]
    return sorted({(item.get("user") or {}).get("login") or "ghost" for at, item in items if at and at > reported})


def enqueue_problems(repo, number, sha, remote):
    """(PR node id, reasons not to queue). The checks POLICY §5 lists, all recomputed now."""
    report = preflight(repo, number, remote)
    if report is None:
        return None, ["head나 base가 실행 중에 바뀌었다"]
    if report["secret_hits"]:
        return None, ["비밀값 파일 이름: " + ", ".join(json.dumps(p) for p in report["secret_hits"])]
    owner, name = repo.split("/")
    pr = gh_graphql(PR_QUERY, owner=owner, name=name, number=int(number))["repository"]["pullRequest"]
    problems = [] if report["head"] == sha else [f"head가 {sha}가 아니라 {report['head']}다"]
    if report["fork"]:
        problems.append("fork PR이다")
    agents = (contents(repo, "AGENTS.md", report["base"]) or b"").decode("utf-8", "replace").splitlines()
    if not any(line.startswith(STANDING) and STANDING_COMMAND in line for line in agents):
        problems.append("base의 AGENTS.md에 상시 지시 줄이 없다")
    problems += account_problems(repo, report, pages(f"repos/{repo}/pulls/{number}/commits"))
    fields = review_fields(pr["body"] or "")
    if fields["등급"] is not None and fields["등급"] not in GRADES:
        problems.append(f"「등급」이 {'·'.join(GRADES)} 중 하나가 아니다")
    grade = max(report["grade"], fields["등급"] if fields["등급"] in GRADES else "문서", key=GRADES.index)
    if grade == "어려움":
        problems.append("어려움 등급이다(소유자가 GitHub 화면에서 넣는다)")
    if grade == "쉬움" and fields["리뷰한 head"] != sha:
        problems.append(f"리뷰 보고의 「리뷰한 head」가 {sha}가 아니다")
    if (grade == "쉬움" or fields["남은 지적"] is not None) and fields["남은 지적"] != "없음":
        problems.append("리뷰 보고의 「남은 지적」이 「없음」 한 줄이 아니다")
    problems += ci_problems(repo, report["head"], required_checks(repo, report["base_branch"]))
    # The report's time is the last body edit by a person: bots (CodeRabbit) also rewrite the body.
    edits = [e["editedAt"] for e in pr["userContentEdits"]["nodes"] if (e.get("editor") or {}).get("__typename") == "User"]
    late = external_reviews(repo, number, max(edits, default=pr["createdAt"]))
    if late:
        problems.append("리뷰 보고 뒤의 판정하지 않은 외부 리뷰: " + ", ".join(late))
    return pr["id"], problems


def cmd_enqueue(args):
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        print("enqueue: 클라우드 세션에서는 넣지 않는다. 프록시가 GraphQL(큐 넣기)을 막는다. 로컬 세션에서 부른다.",
              file=sys.stderr)
        return 2
    if not SHA_RE.fullmatch(args.sha):
        print("enqueue: SHA는 40자 소문자 hex다", file=sys.stderr)
        return 2
    try:
        repo, number = pr_target(args.pr, args.remote)
        node, problems = enqueue_problems(repo, number, args.sha, args.remote)
        if problems:
            for problem in problems:
                print(f"enqueue: 넣지 않는다: {problem if problem.isprintable() else json.dumps(problem)}")
            return 1
        gh_graphql(ENQUEUE, id=node, sha=args.sha)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"enqueue: 실행 실패: {error}", file=sys.stderr)
        return 2
    print(f"enqueue: {repo}#{number}을 {args.sha}로 머지 큐에 넣었다")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="baseline.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="빈 저장소에 코어를 복사한다").add_argument("path")
    sub.add_parser("check", help="관리 파일·블록과 명령 칸이 이 판과 같은지 본다")
    sub.add_parser("run", help="commands.json의 명령을 돌린다").add_argument("name", choices=COMMANDS)
    sub.add_parser("budget", help="AGENTS.md와 리뷰어가 읽는 글의 크기를 잰다")
    preflight_parser = sub.add_parser("review-preflight", help="REST로 PR의 등급과 리뷰 전 확인을 출력한다")
    preflight_parser.add_argument("pr", help="PR URL 또는 번호")
    preflight_parser.add_argument("--remote", default="origin", help="base 저장소의 remote(번호만 줄 때)")
    preflight_parser.add_argument("--json", action="store_true", help="JSON 한 개로 출력한다")
    enqueue_parser = sub.add_parser("enqueue", help="문서·쉬움 PR을 다시 확인하고 머지 큐에 넣는다(로컬 전용)")
    enqueue_parser.add_argument("pr", help="PR URL 또는 번호")
    enqueue_parser.add_argument("sha", help="리뷰한 head(40자 SHA)")
    enqueue_parser.add_argument("--remote", default="origin", help="base 저장소의 remote(번호만 줄 때)")
    args = parser.parse_args(argv)
    return {"init": cmd_init, "check": cmd_check, "run": cmd_run, "budget": cmd_budget,
            "review-preflight": cmd_review_preflight, "enqueue": cmd_enqueue}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
