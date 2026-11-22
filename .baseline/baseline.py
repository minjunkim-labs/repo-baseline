"""repo-baseline v2: copy the core into a repo and check that it still matches.

Python 3.9+ standard library only. Run with `python3 -I`. In a consumer repo every command
runs from the pinned copy `.baseline/baseline.py`.
"""
import argparse
import ast
from datetime import datetime, timedelta, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
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
    ".claude/hooks/allow_enqueue.py": {"sha256": "55b4aeb5b60231948c9f6fe5190878ce9955114d4a8d87e55be33d9f27f3b5e7"},
    ".claude/hooks/check.py": {"sha256": "6b27ea25423c46e4cd0acd2510b7b4b1d0ee6ae6f38f8f4307a37ce6b1b3b758"},
    "docs/agents/issue-tracker.md": {"sha256": "6fdb3e9b00b7b0b115ecac3b1c00e3790f637f190abf598815368722c0a94692"},
    "docs/agents/triage-labels.md": {"sha256": "ae512af838c78b8750471c42cd2b20fa32319553e61d84c9a23d171b40ce14aa"},
    "docs/agents/domain.md": {"sha256": "593a7042218689f1d24df89df14eaf0a20e19e0d0a7d479a01947ac78f0784b9"},
    "docs/agents/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/blast-radius/LICENSE": {"sha256": "bc957ca6bee02792566a1a028d105e02e247c6e77cf057061674273da77b200e"},
    ".claude/skills/blast-radius/SKILL.md": {"sha256": "4248d03e22365207d2e5f90c9542720f80a88a6b42fd542ef88dde3cf9f9223f"},
    ".claude/skills/code-review/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/code-review/SKILL.md": {"sha256": "9c921a8d88138a41401d8897ca1bb852088ab1b7b605cdd04edc13e3e8aab6dd"},
    ".claude/skills/code-review/agents/openai.yaml": {"sha256": "8229ca854e11dc8e6aef2131ee03f31fb1561cf905fab9ccc325180cf3331352"},
    ".claude/skills/codebase-design/DEEPENING.md": {"sha256": "f3dd099ce99289bd213914d8ee3e2429b78309c3957ca4583f7659551b1d53c1"},
    ".claude/skills/codebase-design/DESIGN-IT-TWICE.md": {"sha256": "c222ab5a82e0405672eb9062d62496139a08828e45d07fc5f18e4952c10fac1a"},
    ".claude/skills/codebase-design/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/codebase-design/SKILL.md": {"sha256": "2c20617f87ec8af6a434859f381b2f061a69b530444e74eb39e78bb016a6d1e2"},
    ".claude/skills/codebase-design/agents/openai.yaml": {"sha256": "edebc9e4fcfe102114012575eaa9600b9b5fd08c311664f389c36e7bc717740f"},
    ".claude/skills/create-verification-skill/LICENSE": {"sha256": "bc957ca6bee02792566a1a028d105e02e247c6e77cf057061674273da77b200e"},
    ".claude/skills/create-verification-skill/SKILL.md": {"sha256": "d353973547bf8ad8977eca645f4cd4feaed0d32f4b43d1448f906b0a76c4d694"},
    ".claude/skills/create-verification-skill/references/feature-map-example/README.md": {"sha256": "cb7bd782cf89968a4ba3d58a5151db837430db92d19a6f52a906973b77b516ba"},
    ".claude/skills/create-verification-skill/references/feature-map-example/create-note.md": {"sha256": "644a44c74f35d38c2feb7cd05a0121fdebbb623e8dc376c185b565a581d1ccf7"},
    ".claude/skills/create-verification-skill/references/feature-map-example/search.md": {"sha256": "6e87b9e7f2791a7776ba1bb83f371cd285c306c67f19d245cc4dd6ca3015c823"},
    ".claude/skills/diagnosing-bugs/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/diagnosing-bugs/SKILL.md": {"sha256": "849198df88cdb65fd0d97236604c1fca7ff2f22d2f705f9724a800d0266b118d"},
    ".claude/skills/diagnosing-bugs/agents/openai.yaml": {"sha256": "3e430dbe4334a87597488c060cb3dc3786bb00c9182877d6f5ec41f62490e90b"},
    ".claude/skills/diagnosing-bugs/scripts/hitl-loop.template.sh": {"sha256": "35103539fc36873eea36074769ad454f9379d6fc8b2dc0e26ce987fd3bfe5503"},
    ".claude/skills/domain-modeling/ADR-FORMAT.md": {"sha256": "944c92aa790e8fbdc9199640b170979abb8a34ba8d0fe18c2a01a63bce140ca0"},
    ".claude/skills/domain-modeling/GLOSSARY-FORMAT.md": {"sha256": "21dcc40cdec8e151a829b98ab1517c1867bc444e3665134a98c6983411996801"},
    ".claude/skills/domain-modeling/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/domain-modeling/SKILL.md": {"sha256": "7b925d7b1e341a2eeae33ad68a8a8c0ab889a38ddd22a7598e4c240e5a7556a3"},
    ".claude/skills/domain-modeling/agents/openai.yaml": {"sha256": "f6bf2aa996c6e6f53fdd0708e18a0d16a56aed8322cca59fedbe3c0d2c75f06b"},
    ".claude/skills/grill-with-docs/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/grill-with-docs/SKILL.md": {"sha256": "7de372c13488f1ee96cc11cd8907b56b6809cc93eef776eeddd37de6b6cbe3fe"},
    ".claude/skills/grill-with-docs/agents/openai.yaml": {"sha256": "94cd0ab161fb468a836349f5ed482ba58ce8e709a05c57ce533d739dbd35cca9"},
    ".claude/skills/grilling/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/grilling/SKILL.md": {"sha256": "a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2"},
    ".claude/skills/grilling/agents/openai.yaml": {"sha256": "1411d7df7d99b7e621a1ff8283c8133cc2464be63d064e52d8ce169c6800ee9b"},
    ".claude/skills/interrogate/LICENSE": {"sha256": "bc957ca6bee02792566a1a028d105e02e247c6e77cf057061674273da77b200e"},
    ".claude/skills/interrogate/SKILL.md": {"sha256": "3f3c2e9b8cf6b180dba9f32a4aff85e5691b09805232468e37a0ba45437a9984"},
    ".claude/skills/maintain-verification-skill/LICENSE": {"sha256": "bc957ca6bee02792566a1a028d105e02e247c6e77cf057061674273da77b200e"},
    ".claude/skills/maintain-verification-skill/SKILL.md": {"sha256": "515c0eaa054b3f6be1b1fb06f2c2f173c80fddb58bbcac57576f89c479bc68e8"},
    ".claude/skills/pr/CREDITS.md": {"sha256": "a7a087127665d7298a72280ef6e19c41ad8404523712a788c8dc3ab414bc2497"},
    ".claude/skills/pr/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/pr/SKILL.md": {"sha256": "ab63f1cf78647389edcd386c9427c5dfca27ed2836930c24773ffee834c19bcd"},
    ".claude/skills/pr/agents/openai.yaml": {"sha256": "2295b586624db4ef546f3fd4695492f039d941a46d8a1593a702ce3ca511b8ad"},
    ".claude/skills/prototype/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/prototype/LOGIC.md": {"sha256": "f61c7d249e786a79ef289018901c348271e1798dd0b0bc5607b5c6f4d4a01ab9"},
    ".claude/skills/prototype/SKILL.md": {"sha256": "714de632d116bb73f65cdb5a882db15b9369a6713b9a47c0fad827848f0bfbe3"},
    ".claude/skills/prototype/UI.md": {"sha256": "723211e878acbc7b6ff09755263f3295cde724ba902ff0064da41eed51d45ad3"},
    ".claude/skills/prototype/agents/openai.yaml": {"sha256": "5af65e43ab41a350436697b81e27b7f848d36782043b73c322bb2c9fa9cc55dc"},
    ".claude/skills/research/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/research/SKILL.md": {"sha256": "1f629e18ab899412683bc6a1c4efb4339999e27c2fdac328f26ee10a8c031d33"},
    ".claude/skills/research/agents/openai.yaml": {"sha256": "9b4c470d63221c1f68f22df70b83e2f12401b317babe0d1b7b5f24a974474d0d"},
    ".claude/skills/tdd/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/tdd/SKILL.md": {"sha256": "5505d25bbaa8fc14a79e4d20163936958992a2995b7f1dd1d6197edc9ed722e0"},
    ".claude/skills/tdd/agents/openai.yaml": {"sha256": "ea6f01cf1b8c06a4b0f5b649d74b1b8ce8685e72af1b38d70d877693e092af0b"},
    ".claude/skills/tdd/mocking.md": {"sha256": "3ceb807fdf4a47d6a93d4d9a891e5ba6d362a6247bd08adc451feebfc17361ef"},
    ".claude/skills/tdd/tests.md": {"sha256": "859f9e592c188fda4fc7277dd180e4ce9c7a2e13f6efe1f6f29eccc9d28c106a"},
    ".claude/skills/to-spec/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/to-spec/SKILL.md": {"sha256": "43ad9cf318e5e7d3d1fa360253a37021796dc87a0c2e595ad262661a10f85088"},
    ".claude/skills/to-spec/agents/openai.yaml": {"sha256": "1c5b4d1e3d8e52287ef19cc2742fdbbfae1914ac75d33af3e4c8174f08cc55bb"},
    ".claude/skills/to-tickets/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/to-tickets/SKILL.md": {"sha256": "56ec23c5b2782785d4e65bff9e315b6d3aeb4ef977c174a219e99489fada1995"},
    ".claude/skills/to-tickets/agents/openai.yaml": {"sha256": "21bc6215fffcd7614e9f772bb1760e87cc5fc7dcc707e7d282bc9414267a6090"},
    ".claude/skills/wayfinder/LICENSE": {"sha256": "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5"},
    ".claude/skills/wayfinder/SKILL.md": {"sha256": "0c9fa96791aebf3b7d654cf35c6aadde97d81f57c17b07d13b27c14d9c46561f"},
    ".claude/skills/wayfinder/agents/openai.yaml": {"sha256": "88bc81a11a6d52ac67aeaa76b8b619e387020d47c5133a4dd4927fd15c4ad073"},
}
SKILLS = ".claude/skills/"  # skill copies: managed files whose source is skills/ (skills-bump)
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


def source(rel):
    """Where repo-baseline keeps a managed file: skill copies in skills/, the rest in core/."""
    here = Path(__file__).resolve().parent
    return here / "skills" / rel[len(SKILLS):] if rel.startswith(SKILLS) else here / "core" / rel


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
    files.update({rel: source(rel).read_bytes() for rel in MANAGED if rel.startswith(SKILLS)})
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
    # A file added to a skill copy changes the skill too. Other folders in .claude/skills/ are the project's.
    for name in sorted({rel[len(SKILLS):].split("/")[0] for rel in MANAGED if rel.startswith(SKILLS)}):
        for folder, dirs, names in os.walk(root / SKILLS / name):
            for entry in names + [d for d in dirs if Path(folder, d).is_symlink()]:
                rel = Path(folder, entry).relative_to(root).as_posix()
                if rel not in MANAGED:
                    problems.append(f"{rel}: 이 판의 스킬 사본에 없는 파일이다")
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
        at = [i for i, line in enumerate(lines) if line.startswith(f"{name}:")]
        fields[name] = lines[at[0]][len(name) + 1:].strip().strip("`") if len(at) == 1 else None if not at else ""
        if len(at) == 1 and at[0] + 1 < len(lines) and lines[at[0] + 1].startswith(("-", "*")):
            fields[name] += " (목록이 이어진다)"  # 「남은 지적: 없음」 followed by a list is not 없음
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
        status = statuses.get(context) if app in (None, -1) else None
        if not mine and status is None:
            problems.append(f"필수 CI {context}: 결과가 없다")
            continue
        if mine:
            run = max(mine, key=lambda r: r["id"])
            if run["status"] != "completed" or run["conclusion"] not in PASSED:
                problems.append(f"필수 CI {context}: {run['conclusion'] or run['status']}")
        if status not in (None, "success"):  # a check run and a status of one name: both must pass
            problems.append(f"필수 CI {context}: {status}")
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


def changes_requested(reviews):
    """People whose last review state is CHANGES_REQUESTED. Comments do not change a state; bots are left out."""
    last = {}
    for review in sorted(reviews, key=lambda r: r.get("submitted_at") or ""):
        user = review.get("user") or {}
        if user.get("type") != "Bot" and review.get("submitted_at") and review.get("state") != "COMMENTED":
            last[user.get("login") or "ghost"] = review["state"]
    return sorted(login for login, state in last.items() if state == "CHANGES_REQUESTED")


def external_reviews(repo, number, reported, reviews):
    """Reviews and comments written or edited after the review report: nobody judged them."""
    items = [(r.get("submitted_at"), r) for r in reviews]
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
    if grade == "쉬움" and fields["등급"] is None:
        problems.append("리뷰 보고에 「등급」이 없다")
    if grade == "쉬움" and fields["리뷰한 head"] != sha:
        problems.append(f"리뷰 보고의 「리뷰한 head」가 {sha}가 아니다")
    if (grade == "쉬움" or fields["남은 지적"] is not None) and fields["남은 지적"] != "없음":
        problems.append("리뷰 보고의 「남은 지적」이 「없음」 한 줄이 아니다")
    problems += ci_problems(repo, report["head"], required_checks(repo, report["base_branch"]))
    reviews = pages(f"repos/{repo}/pulls/{number}/reviews")
    blocked = changes_requested(reviews)
    if blocked:
        problems.append("변경 요청: " + ", ".join(blocked))
    if grade == "쉬움":  # docs PRs have no reviewer to judge bot comments: CI only (POLICY §3)
        # The report's time is the last body edit by a person: bots (CodeRabbit) also rewrite the body.
        edits = [e["editedAt"] for e in pr["userContentEdits"]["nodes"]
                 if (e.get("editor") or {}).get("__typename") == "User"]
        late = external_reviews(repo, number, max(edits, default=pr["createdAt"]), reviews)
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


def blob_sha(data):
    """The git blob id, so files can be compared with a REST tree without downloading them."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tag_version(name):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", name or "")
    return tuple(map(int, match.groups())) if match else None


def lock_problems(lock):
    if not isinstance(lock, dict) or not isinstance(lock.get("sources"), dict) or not isinstance(lock.get("skills"), dict):
        return ["skills.lock.json에 sources·skills 객체가 없다"]
    problems = []
    for name, src in lock["sources"].items():
        if not (isinstance(src, dict) and re.fullmatch(r"[\w.-]+/[\w.-]+", str(src.get("repo")))
                and src.get("update") in ("tag", "commit") and isinstance(src.get("days"), int) and src["days"] >= 7
                and all(isinstance(src.get(k), str) for k in ("license", "plugin"))
                and (src["update"] == "tag" or isinstance(src.get("branch"), str))):
            problems.append(f"출처 {name}: repo, update(tag·commit), days(7 이상), license, plugin"
                            "(commit이면 branch)가 있어야 한다")
    for name, skill in lock["skills"].items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or not isinstance(skill, dict) \
                or skill.get("source") not in lock["sources"] or not isinstance(skill.get("path"), str) \
                or ".." in skill["path"].split("/") or not isinstance(skill.get("requires"), list):
            problems.append(f"{name}: 이름(소문자·숫자·-), source, path, requires가 맞지 않다")
            continue
        for need in skill["requires"]:  # one source moves as one pin, so its skills change together
            if (lock["skills"].get(need) or {}).get("source") != skill["source"]:
                problems.append(f"{name}: 의존 스킬 {need}가 lock에 없거나 출처가 다르다")
    return problems


def newest_pin(src, cutoff):
    """(tag or None, commit) of the newest version older than the cutoff that is newer than the pin, or None."""
    repo = src["repo"]

    def ahead(sha):  # never back, never sideways: a new tag can name an old commit
        return not src.get("commit") or gh_api(f"repos/{repo}/compare/{src['commit']}...{sha}")["status"] == "ahead"
    if src["update"] == "commit":
        found = gh_api(f"repos/{repo}/commits?sha={quote(src['branch'], safe='')}"
                       f"&until={cutoff:%Y-%m-%dT%H:%M:%SZ}&per_page=1")
        if not found:
            return None
        return (None, found[0]["sha"]) if ahead(found[0]["sha"]) else None
    current = tag_version(src.get("tag"))
    for tag in sorted({t["name"] for t in pages(f"repos/{repo}/tags") if tag_version(t["name"])},
                      key=tag_version, reverse=True):
        if current and tag_version(tag) <= current:
            return None
        target = gh_api(f"repos/{repo}/git/ref/tags/{quote(tag, safe='')}")["object"]
        date = None
        if target["type"] == "tag":  # the tag's own date: an old commit can get a new tag
            annotated = gh_api(f"repos/{repo}/git/tags/{target['sha']}")
            date, target = annotated["tagger"]["date"], annotated["object"]
        if target["type"] != "commit":
            raise ValueError(f"{repo} {tag}: 커밋을 가리키지 않는다")
        date = date or gh_api(f"repos/{repo}/commits/{target['sha']}")["commit"]["committer"]["date"]
        if datetime.fromisoformat(date.replace("Z", "+00:00")) <= cutoff:
            return (tag, target["sha"]) if ahead(target["sha"]) else None
    return None


def snapshot(src, names, skills, commit):
    """{"<skill>/<rel>": (path in the source, tree entry)} at the commit, with the source LICENSE in each skill."""
    repo = src["repo"]
    tree = gh_api(f"repos/{repo}/git/trees/{commit}?recursive=1")
    if tree.get("truncated"):
        raise OSError(f"{repo}@{commit[:7]}: 트리가 커서 REST가 다 보여 주지 않는다")
    entries = {e["path"]: e for e in tree["tree"]}
    out = {}
    for name in names:
        prefix = skills[name]["path"].rstrip("/") + "/"
        found = {p[len(prefix):]: p for p, e in entries.items() if p.startswith(prefix) and e.get("type") != "tree"}
        if "SKILL.md" not in found or "LICENSE" in found:
            raise OSError(f"{repo}@{commit[:7]} {prefix}: SKILL.md가 없거나 LICENSE가 이미 있다")
        found["LICENSE"] = src["license"]
        for rel, path in found.items():
            entry = entries.get(path) or {}
            if (not rel.isprintable() or "\\" in rel or any(part in ("", ".", "..") or part.lower().startswith(".git") for part in rel.split("/"))
                    or entry.get("type") != "blob" or entry.get("mode") not in ("100644", "100755")
                    or not isinstance(entry.get("size"), int) or entry["size"] > MAX_READ):
                raise OSError(f"{repo}@{commit[:7]} {json.dumps(path)}: 없거나 일반 파일이 아니다(symlink·submodule, "
                              f"{MAX_READ}바이트 넘음, 쓸 수 없는 이름)")
            out[f"{name}/{rel}"] = (path, entry)
    return out


def local_shas(root, names):
    found = {}
    for name in names:
        for path in sorted((root / "skills" / name).rglob("*")):
            if path.is_file():
                found[path.relative_to(root / "skills").as_posix()] = blob_sha(path.read_bytes())
    return found


def write_managed(path, managed):
    """Replace the MANAGED literal of a baseline.py, one entry per line."""
    text = path.read_bytes().decode("utf-8")
    node = next(n for n in ast.parse(text).body
                if isinstance(n, ast.Assign) and [getattr(t, "id", None) for t in n.targets] == ["MANAGED"])
    lines = text.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = ["MANAGED = {\n"] + [
        f"    {json.dumps(rel)}: {{{json.dumps(kind)}: {json.dumps(want)}}},\n"
        for rel, spec in managed.items() for kind, want in spec.items()] + ["}\n"]
    path.write_bytes("".join(lines).encode("utf-8"))


def skills_bump(root, check, now):
    """Move each skill source of skills/skills.lock.json to its newest version older than `days`."""
    try:
        lock = json.loads(read_file(root, "skills/skills.lock.json"))
        problems = lock_problems(lock)
        if problems:
            raise ValueError("; ".join(problems))
        updates = []
        for name, src in lock["sources"].items():
            pin = newest_pin(src, now - timedelta(days=src["days"]))
            names = sorted(n for n, s in lock["skills"].items() if s["source"] == name)
            files = snapshot(src, names, lock["skills"], pin[1]) if pin else None
            if files and {rel: e["sha"] for rel, (_, e) in files.items()} != local_shas(root, names):
                updates.append((name, src, pin, names, files))
        if not updates:
            print("skills-bump: 새 판이 없다")
            return 0
        for name, src, (tag, commit), names, _ in updates:
            print(f"skills-bump: {name}: {src.get('tag') or (src.get('commit') or '없음')[:7]} → {tag or commit[:7]} "
                  f"({src['repo']}, 스킬: {', '.join(names)})")
        if check:
            return 1
        writes = {}  # download and verify everything before the first write
        for name, src, (tag, commit), names, files in updates:
            for rel, (path, entry) in files.items():
                data = contents(src["repo"], path, commit)
                if data is None or blob_sha(data) != entry["sha"]:
                    raise OSError(f"{src['repo']}@{commit[:7]} {path}: 받은 바이트가 트리와 다르다")
                writes[rel] = data
            version = json.loads(contents(src["repo"], src["plugin"], commit) or b"null")
            version = version.get("version") if isinstance(version, dict) else None
            if not isinstance(version, str):
                raise ValueError(f"{src['repo']}@{commit[:7]} {src['plugin']}: version이 없다")
            src.update({"commit": commit, "version": version}, **({"tag": tag} if tag else {}))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration) as error:
        print(f"skills-bump: 실행 실패: {error}", file=sys.stderr)
        return 2
    changed = [n for update in updates for n in update[3]]
    for base in ("skills", SKILLS):
        for name in changed:
            shutil.rmtree(root / base / name, ignore_errors=True)
        for rel, data in writes.items():
            (root / base / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / base / rel).write_bytes(data)
    (root / "skills/skills.lock.json").write_bytes(dump_json(lock))
    managed = {rel: spec for rel, spec in embedded_managed((root / "baseline.py").read_bytes()).items()
               if not rel.startswith(SKILLS)}
    for name in sorted(lock["skills"]):
        for path in sorted((root / "skills" / name).rglob("*")):
            if path.is_file():
                managed[SKILLS + path.relative_to(root / "skills").as_posix()] = {"sha256": sha256(path.read_bytes())}
    before = sha256((root / "baseline.py").read_bytes())
    write_managed(root / "baseline.py", managed)
    after = sha256((root / "baseline.py").read_bytes())
    for rel in ("core/.claude/settings.json", ".claude/settings.json"):  # the enqueue hook pins baseline.py
        if (root / rel).is_file():
            (root / rel).write_bytes((root / rel).read_bytes().replace(before.encode(), after.encode()))
    shutil.copyfile(root / "baseline.py", root / ".baseline/baseline.py")
    recorded = json.loads((root / ".baseline/baseline.json").read_bytes())
    (root / ".baseline/baseline.json").write_bytes(dump_json(dict(recorded, managed=managed)))
    print("skills-bump: skills/, .claude/skills/, skills.lock.json, baseline.py의 MANAGED, .baseline/을 바꿨다. "
          "PR을 연다(소유자가 diff를 읽고 병합한다)")
    return 0


def cmd_skills_bump(args):
    root = Path(__file__).resolve().parent
    if not (root / "skills/skills.lock.json").is_file():
        sys.exit("skills-bump: skills/skills.lock.json이 없다. repo-baseline 클론의 baseline.py로 돌린다")
    return skills_bump(root, args.check, datetime.now(timezone.utc))


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
    bump_parser = sub.add_parser("skills-bump", help="스킬 출처마다 7일 지난 새 판으로 사본을 바꾼다(repo-baseline 전용)")
    bump_parser.add_argument("--check", action="store_true", help="바꾸지 않고 새 판이 있는지만 본다(있으면 1)")
    args = parser.parse_args(argv)
    return {"init": cmd_init, "check": cmd_check, "run": cmd_run, "budget": cmd_budget,
            "review-preflight": cmd_review_preflight, "enqueue": cmd_enqueue,
            "skills-bump": cmd_skills_bump}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
