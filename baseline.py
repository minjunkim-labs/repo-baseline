"""repo-baseline v2: copy the core into a repo and check that it still matches.

Python 3.9+ standard library only. Run with `python3 -I`. In a consumer repo every command
runs from the pinned copy `.baseline/baseline.py`.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

VERSION = "2.0.0-dev"
START, END = b"<!-- baseline:start -->\n", b"<!-- baseline:end -->\n"
# The hashes of this version. check trusts these, not only baseline.json, so editing a managed
# file together with baseline.json still fails. test_baseline.py keeps them equal to core/.
MANAGED = {
    ".gitattributes": {"sha256": "d60f352d0db1404c70afb4bb8b2ca3fd1c610572aa40720e8a0b7baa7885418c"},
    "AGENTS.md": {"block_sha256": "9bfb5a756aa596b09a6741c38e0da0114be63e59ad15bea20fb3f91137435559"},
    "CLAUDE.md": {"sha256": "336cc4fbf19beaada7ccf9986414fa91851a8d7a07dfb3ccbe800a69eed0ab49"},
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
MAX_READ = 1 << 20


def read_file(path):
    """check and budget read a PR tree in CI: regular files only, at most MAX_READ bytes.
    git ignores a symlinked .gitattributes, and a link to /dev/zero never ends."""
    if path.is_symlink() or not path.is_file():
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
    here = Path(__file__).resolve().parent
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
        commands = json.loads(read_file(root / ".baseline/commands.json"))
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
    try:
        recorded = json.loads(read_file(root / ".baseline/baseline.json"))
    except (OSError, ValueError) as error:
        recorded = None
        problems.append(f"baseline.json을 읽지 못했다: {error}")
    if recorded is not None and not isinstance(recorded, dict):
        recorded = None
        problems.append("baseline.json은 객체여야 한다")
    if recorded is not None and recorded.get("version") != VERSION:
        problems.append(f"baseline.json의 판 {recorded.get('version')!r}이 baseline.py의 판 {VERSION!r}과 다르다")
    if recorded is not None and recorded.get("managed") != MANAGED:
        problems.append("baseline.json의 관리 해시가 baseline.py 안의 해시와 다르다")
    for rel, expected in MANAGED.items():
        (kind, want), = expected.items()
        try:
            got = digest(read_file(root / rel), kind)
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
            lines = read_file(root / "AGENTS.md").decode("utf-8").splitlines()
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
    try:
        data = read_file(repo_root() / "AGENTS.md")
    except OSError as error:
        sys.exit(f"budget: AGENTS.md: {error}")
    lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    print(f"budget: AGENTS.md {lines}줄(상한 {BUDGET_LINES}), {len(data)}바이트(상한 {BUDGET_BYTES})")
    if lines > BUDGET_LINES or len(data) > BUDGET_BYTES:
        print("budget: 상한을 넘었다", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="baseline.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="빈 저장소에 코어를 복사한다").add_argument("path")
    sub.add_parser("check", help="관리 파일·블록과 명령 칸이 이 판과 같은지 본다")
    sub.add_parser("run", help="commands.json의 명령을 돌린다").add_argument("name", choices=COMMANDS)
    sub.add_parser("budget", help="AGENTS.md의 줄 수와 바이트를 잰다")
    args = parser.parse_args(argv)
    return {"init": cmd_init, "check": cmd_check, "run": cmd_run, "budget": cmd_budget}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
