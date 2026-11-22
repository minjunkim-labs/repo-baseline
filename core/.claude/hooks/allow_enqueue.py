"""PreToolUse hook: allow `python3 -I .baseline/baseline.py enqueue <PR number> <40-hex SHA>` and nothing else.

Auto mode drops the matching allow rule (an interpreter with a flag), so this hook answers "allow" instead.
It answers only when the copy it would run has the bytes of origin/main, which a person merged.
Otherwise it prints nothing and the call goes through the normal permission flow. Deny rules still win.
"""
import json
import os
import re
import subprocess
import sys

COMMAND = re.compile(r"python3 -I \.baseline/baseline\.py enqueue [1-9][0-9]{0,9} [0-9a-f]{40}")


def git(cwd, *args):
    # No fsmonitor: a repo's own config must not run a program here.
    return subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", cwd, *args],
                          capture_output=True, check=True, timeout=10).stdout


def allowed(event):
    if event.get("tool_name") != "Bash" or not COMMAND.fullmatch(event["tool_input"]["command"]):
        return False
    cwd = event["cwd"]
    top = git(cwd, "rev-parse", "--show-toplevel").decode().strip()
    folder = os.path.join(cwd, ".baseline")
    copy = os.path.join(folder, "baseline.py")
    if os.path.realpath(top) != os.path.realpath(cwd) or os.path.islink(folder) or os.path.islink(copy):
        return False
    with open(copy, "rb") as f:
        return f.read() == git(cwd, "cat-file", "blob", "origin/main:.baseline/baseline.py")


def main():
    try:
        ok = allowed(json.load(sys.stdin))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        ok = False
    if ok:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                 "permissionDecisionReason": "baseline enqueue (origin/main copy)"}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
