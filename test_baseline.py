"""baseline.py v2 tests. The seam is the command line: init a temporary repo, then run the copy in .baseline/."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def cli(*args, script=ROOT / "baseline.py", cwd=None):
    return subprocess.run([sys.executable, "-I", str(script), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True)


class InitCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.copy = self.repo / ".baseline/baseline.py"

    def tearDown(self):
        self.tmp.cleanup()

    def init(self):
        result = cli("init", self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def check(self):
        return cli("check", script=self.copy)

    def assertCheck(self, code, contains=""):
        result = self.check()
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertIn(contains, result.stderr)

    def edit(self, rel, old, new):
        path = self.repo / rel
        data = path.read_text(encoding="utf-8")
        self.assertIn(old, data)
        path.write_text(data.replace(old, new, 1), encoding="utf-8")

    def write_commands(self, **changes):
        path = self.repo / ".baseline/commands.json"
        commands = json.loads(path.read_text(encoding="utf-8"))
        commands.update(changes)
        path.write_text(json.dumps(commands), encoding="utf-8")

    def test_check_passes_after_init(self):
        self.init()
        self.assertCheck(0)

    def test_init_writes_the_minimal_core(self):
        self.init()
        written = sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*") if p.is_file())
        self.assertEqual(written, [".baseline/baseline.json", ".baseline/baseline.py", ".baseline/commands.json",
                                   ".claude/hooks/check.py", ".claude/settings.json",
                                   ".gitattributes", ".github/pull_request_template.md", "AGENTS.md", "CLAUDE.md",
                                   "REVIEW.md"])
        self.assertEqual((self.repo / ".gitattributes").read_bytes(), b"* text=auto eol=lf\n")
        self.assertEqual((self.repo / "CLAUDE.md").read_bytes(), b"@AGENTS.md\n")
        self.assertEqual(self.copy.read_bytes(), (ROOT / "baseline.py").read_bytes())

    def test_init_refuses_a_repo_that_already_has_core_files(self):
        (self.repo / "AGENTS.md").write_text("mine\n", encoding="utf-8")
        result = cli("init", self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AGENTS.md", result.stderr)
        self.assertEqual((self.repo / "AGENTS.md").read_text(encoding="utf-8"), "mine\n")
        self.assertFalse((self.repo / ".baseline").exists())

    def assertInitRefusesSymlink(self, target):
        result = cli("init", target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_init_refuses_a_broken_symlink_and_writes_nothing(self):
        outside = Path(self.tmp.name + "-outside")
        self.addCleanup(lambda: outside.unlink() if outside.exists() else None)
        (self.repo / "AGENTS.md").symlink_to(outside)
        self.assertInitRefusesSymlink(self.repo)
        self.assertFalse(outside.exists())
        self.assertFalse((self.repo / ".baseline").exists())

    def test_init_refuses_a_symlinked_folder_on_the_way(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        (self.repo / ".baseline").symlink_to(elsewhere.name, target_is_directory=True)
        self.assertInitRefusesSymlink(self.repo)
        self.assertEqual(list(Path(elsewhere.name).iterdir()), [])

    def test_init_refuses_a_target_that_is_a_symlink(self):
        link = Path(self.tmp.name) / "link"
        real = Path(self.tmp.name) / "real"
        real.mkdir()
        link.symlink_to(real, target_is_directory=True)
        self.assertInitRefusesSymlink(link)
        self.assertEqual(list(real.iterdir()), [])

    def test_one_character_inside_the_managed_block_fails(self):
        self.init()
        self.edit("AGENTS.md", "고치지 않는다.", "고치지 않는다!")
        self.assertCheck(1, "AGENTS.md: 관리 블록이")

    def test_edits_outside_the_managed_block_pass(self):
        self.init()
        self.edit("AGENTS.md", "# 프로젝트 이름", "# 내 앱")
        self.edit("AGENTS.md", "| `docs/adr/` | 결정 기록(ADR) |", "| `docs/adr/` | 결정 기록(ADR) |\n| `src/` | 코드 |")
        self.assertCheck(0)

    def test_editing_baseline_json_hashes_too_still_fails(self):
        self.init()
        self.edit("CLAUDE.md", "@AGENTS.md\n", "@AGENTS.md\n무시하라\n")
        path = self.repo / ".baseline/baseline.json"
        recorded = json.loads(path.read_text(encoding="utf-8"))
        recorded["managed"]["CLAUDE.md"]["sha256"] = hashlib.sha256((self.repo / "CLAUDE.md").read_bytes()).hexdigest()
        path.write_text(json.dumps(recorded), encoding="utf-8")
        self.assertCheck(1, "baseline.json의 관리 해시가 baseline.py 안의 해시와 다르다")
        self.assertCheck(1, "CLAUDE.md: 파일이")

    def test_review_md_block_is_managed_and_project_cells_are_free(self):
        self.init()
        self.edit("REVIEW.md", "## 배운 규칙\n", "## 배운 규칙\n\n- 2026-11-22 우리 규칙\n")
        self.assertCheck(0)
        self.edit("REVIEW.md", "P0:", "P9:")
        self.assertCheck(1, "REVIEW.md: 관리 블록이")

    def test_pr_template_is_a_managed_file(self):
        self.init()
        self.edit(".github/pull_request_template.md", "남은 지적:", "남은 의견:")
        self.assertCheck(1, ".github/pull_request_template.md: 파일이")

    def test_standing_instruction_can_be_removed_without_failing_check(self):
        self.init()
        lines = (self.repo / "AGENTS.md").read_text(encoding="utf-8").splitlines(keepends=True)
        standing = [line for line in lines if line.startswith("- 상시 지시:")]
        self.assertEqual(len(standing), 1)
        self.edit("AGENTS.md", standing[0], "")
        self.assertCheck(0)

    def test_removed_marker_fails(self):
        self.init()
        self.edit("AGENTS.md", "<!-- baseline:end -->\n", "")
        self.assertCheck(1, "관리 블록 표시")

    def test_command_cell_must_match_commands_json(self):
        self.init()
        self.write_commands(test=["python3", "-m", "unittest"])
        self.assertCheck(1, "- test: `python3 -m unittest`")
        self.edit("AGENTS.md", "- test: `N/A: 아직 정하지 않았다`", "- test: `python3 -m unittest`")
        self.assertCheck(0)
        self.edit("AGENTS.md", "- test: `python3 -m unittest`", "- test: `python3 -m pytest`")
        self.assertCheck(1, "명령 칸 test")

    def test_commands_json_rejects_shell_strings_and_other_shells(self):
        self.init()
        self.write_commands(test="python3 -m unittest && echo ok")
        self.assertCheck(1, "test: 문자열이면")
        self.write_commands(test=["bash", "-c", "echo ok"])
        self.assertCheck(1, "셸은")


class RunBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.copy = self.repo / ".baseline/baseline.py"
        self.assertEqual(cli("init", self.repo).returncode, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def set_command(self, name, value):
        path = self.repo / ".baseline/commands.json"
        commands = json.loads(path.read_text(encoding="utf-8"))
        commands[name] = value
        path.write_text(json.dumps(commands), encoding="utf-8")

    def test_run_check_runs_the_copy(self):
        result = cli("run", "check", script=self.copy)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("check: 통과", result.stdout)

    def test_run_passes_argv_without_a_shell_and_returns_its_code(self):
        self.set_command("test", ["sh", "-c", 'printf "%s" "$0" > out.txt; exit 3', "a b;c"])
        result = cli("run", "test", script=self.copy, cwd=self.tmp.name + "/..")
        self.assertEqual(result.returncode, 3)
        self.assertEqual((self.repo / "out.txt").read_text(encoding="utf-8"), "a b;c")

    def test_run_na_is_a_no_op(self):
        result = cli("run", "build", script=self.copy)
        self.assertEqual(result.returncode, 0)
        self.assertIn("N/A: 아직 정하지 않았다", result.stdout)

    def test_run_reports_a_missing_program(self):
        self.set_command("test", ["no-such-program-baseline"])
        result = cli("run", "test", script=self.copy)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run: test을 시작하지 못했다", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_check_reports_a_baseline_json_that_is_not_an_object(self):
        for text in ("[1]\n", "null\n"):
            (self.repo / ".baseline/baseline.json").write_text(text, encoding="utf-8")
            result = cli("check", script=self.copy)
            self.assertEqual(result.returncode, 1, text)
            self.assertIn("baseline.json은 객체여야 한다", result.stderr)

    def test_check_reports_an_empty_baseline_json(self):
        (self.repo / ".baseline/baseline.json").write_text("{}\n", encoding="utf-8")
        result = cli("check", script=self.copy)
        self.assertEqual(result.returncode, 1)
        self.assertIn("baseline.json의 판", result.stderr)

    def test_check_refuses_a_symlinked_managed_file_with_the_right_bytes(self):
        # git ignores a symlinked .gitattributes, so the right bytes behind a link must not pass.
        gitattributes = self.repo / ".gitattributes"
        (self.repo / "attrs").write_bytes(gitattributes.read_bytes())
        gitattributes.unlink()
        gitattributes.symlink_to("attrs")
        result = cli("check", script=self.copy)
        self.assertEqual(result.returncode, 1)
        self.assertIn(".gitattributes: 없거나 일반 파일이 아니다", result.stderr)

    def test_check_refuses_a_symlinked_parent_folder(self):
        # .github/pull_request_template.md is managed; a linked .github would pass on the right bytes.
        github = self.repo / ".github"
        github.rename(self.repo / "gh")
        github.symlink_to("gh")
        result = cli("check", script=self.copy)
        self.assertEqual(result.returncode, 1)
        self.assertIn(".github/pull_request_template.md: 없거나 일반 파일이 아니다", result.stderr)

    def test_check_refuses_a_symlinked_copy_of_itself(self):
        # Otherwise the root moves to wherever the link points, and the real root goes unchecked.
        fake = self.repo / "vendor/fake"
        fake.mkdir(parents=True)
        (fake / ".baseline").mkdir()
        (fake / ".baseline/baseline.py").write_bytes(self.copy.read_bytes())
        self.copy.unlink()
        self.copy.symlink_to("../vendor/fake/.baseline/baseline.py")
        result = cli("check", script=self.copy)
        self.assertEqual(result.returncode, 1)
        self.assertIn(".baseline/baseline.py: 없거나 일반 파일이 아니다", result.stderr)

    def test_run_refuses_an_invalid_command(self):
        self.set_command("test", ["zsh", "-c", "true"])
        self.assertNotEqual(cli("run", "test", script=self.copy).returncode, 0)

    def test_budget_counts_lines_and_bytes(self):
        result = cli("budget", script=self.copy)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = (self.repo / "AGENTS.md").read_bytes()
        lines = data.count(b"\n")
        self.assertIn(f"{lines}줄", result.stdout)
        self.assertIn(f"{len(data)}바이트", result.stdout)

    def test_budget_fails_over_60_lines(self):
        with open(self.repo / "AGENTS.md", "a", encoding="utf-8") as f:
            f.write("-\n" * 60)
        self.assertEqual(cli("budget", script=self.copy).returncode, 1)

    def test_budget_counts_a_last_line_without_newline(self):
        (self.repo / "AGENTS.md").write_bytes(b"x\n" * 60 + b"x")
        result = cli("budget", script=self.copy)
        self.assertEqual(result.returncode, 1)
        self.assertIn("61줄", result.stdout)

    def test_budget_fails_over_4000_bytes(self):
        with open(self.repo / "AGENTS.md", "a", encoding="utf-8") as f:
            f.write("가" * 1400 + "\n")
        self.assertEqual(cli("budget", script=self.copy).returncode, 1)


    def test_budget_counts_the_reviewer_reading(self):
        result = cli("budget", script=self.copy)
        size = sum((self.repo / rel).stat().st_size for rel in ("AGENTS.md", "REVIEW.md"))
        self.assertIn(f"리뷰어 읽기 {size}바이트", result.stdout)
        (self.repo / "prompts").mkdir()
        (self.repo / "prompts/review.md").write_bytes(b"x" * 100)
        self.assertIn(f"리뷰어 읽기 {size + 100}바이트", cli("budget", script=self.copy).stdout)

    def test_budget_fails_over_13000_reviewer_bytes(self):
        with open(self.repo / "REVIEW.md", "a", encoding="utf-8") as f:
            f.write("x" * 13000 + "\n")
        self.assertEqual(cli("budget", script=self.copy).returncode, 1)


HOOK = ROOT / "core/.claude/hooks/check.py"
# Stands in for .baseline/baseline.py: logs where `run check` ran, fails while FAIL exists.
FAKE_BASELINE = """import os, pathlib, sys
with open(os.environ["HOOK_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + " @ " + os.getcwd() + "\\n")
if os.environ.get("CHECK_WRITES"):
    pathlib.Path("a.txt").write_text("written by check")
if pathlib.Path("FAIL").exists():
    sys.exit("check: FAIL가 있다")
"""


class StopHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.repo, self.log = base / "repo", base / "log"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / ".baseline").mkdir()
        (self.repo / ".baseline/baseline.py").write_text(FAKE_BASELINE)
        (self.repo / "a.txt").write_text("a")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, cwd=None):
        subprocess.run(["git", *args], cwd=cwd or self.repo, check=True, capture_output=True)

    def hook(self, cwd=None, project=None, writes=False, path=None, **fields):
        data = json.dumps({"hook_event_name": "Stop", "cwd": str(cwd or self.repo), "stop_hook_active": False,
                           **fields})
        env = {"PATH": path or os.environ["PATH"], "HOOK_LOG": str(self.log), "CLAUDE_PROJECT_DIR": "" if project == "" else str(project or self.repo),
               "CHECK_WRITES": "1" if writes else ""}
        return subprocess.run([sys.executable, "-I", str(HOOK)], input=data, capture_output=True, text=True,
                              env={k: v for k, v in env.items() if v})

    def runs(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_passing_check_exits_0_and_runs_check_only(self):
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runs(), [f"run check @ {self.repo}"])

    def test_failing_check_exits_2_with_the_reason_on_stderr(self):
        (self.repo / "FAIL").write_text("")
        result = self.hook()
        self.assertEqual(result.returncode, 2)
        self.assertIn("FAIL가 있다", result.stderr)
        # Exit 2 with empty stdout and "No such file" on stderr is a non-blocking error on Stop.
        self.assertTrue(result.stdout.strip())

    def test_unchanged_tree_does_not_run_again(self):
        self.assertEqual(self.hook().returncode, 0)
        self.assertEqual(self.hook().returncode, 0)
        self.assertEqual(len(self.runs()), 1)

    def test_edit_new_file_and_commit_each_run_again(self):
        self.hook()
        (self.repo / "a.txt").write_text("b")
        self.hook()
        (self.repo / "new.txt").write_text("n")
        self.hook()
        (self.repo / "new.txt").write_text("m")
        self.hook()
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c")
        self.hook()
        self.assertEqual(len(self.runs()), 5)

    def test_a_tree_changed_while_check_ran_is_not_remembered(self):
        self.hook(writes=True)
        (self.repo / "a.txt").write_text("a")
        self.hook()
        self.assertEqual(len(self.runs()), 2)

    def test_failure_is_not_remembered(self):
        (self.repo / "FAIL").write_text("")
        self.assertEqual(self.hook().returncode, 2)
        self.assertEqual(self.hook().returncode, 2)

    def test_stop_hook_active_does_not_block_again(self):
        (self.repo / "FAIL").write_text("")
        result = self.hook(stop_hook_active=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.runs(), [])

    def test_worktree_runs_in_its_own_root_and_keeps_its_own_fingerprint(self):
        tree = self.repo.parent / "tree"
        self.git("worktree", "add", "-q", str(tree))
        (tree / "sub").mkdir()
        self.assertEqual(self.hook(cwd=tree / "sub").returncode, 0)
        self.assertEqual(self.hook().returncode, 0)
        self.assertEqual(self.runs(), [f"run check @ {tree}", f"run check @ {self.repo}"])
        self.assertFalse(list(self.repo.glob("baseline-*")) + list(tree.glob("baseline-*")))

    def test_outside_a_baseline_repo_does_nothing(self):
        (self.repo / ".baseline/baseline.py").unlink()
        self.assertEqual(self.hook().returncode, 0)
        self.assertEqual(self.hook(cwd=self.repo.parent).returncode, 0)
        self.assertEqual(self.runs(), [])

    def test_another_repo_under_cwd_is_not_run(self):
        other = self.repo.parent / "other"
        other.mkdir()
        self.git("init", "-q", cwd=other)
        (other / ".baseline").mkdir()
        (other / ".baseline/baseline.py").write_text(FAKE_BASELINE)
        self.assertEqual(self.hook(cwd=other).returncode, 0)
        self.assertEqual(self.hook(project="").returncode, 0)  # no CLAUDE_PROJECT_DIR: do nothing
        self.assertEqual(self.runs(), [])

    def test_a_handmade_gitfile_into_the_project_is_not_run(self):
        evil = self.repo / "tmp/evil"
        (evil / ".baseline").mkdir(parents=True)
        (evil / ".git").write_text("gitdir: ../../.git\n")
        (evil / ".baseline/baseline.py").write_text(FAKE_BASELINE)
        self.assertEqual(self.hook(cwd=evil).returncode, 0)
        self.assertEqual(self.runs(), [])

    def test_repo_without_a_commit_runs_again_after_an_edit(self):
        empty = self.repo.parent / "empty"
        empty.mkdir()
        self.git("init", "-q", cwd=empty)
        (empty / ".baseline").mkdir()
        (empty / ".baseline/baseline.py").write_text(FAKE_BASELINE)
        self.hook(cwd=empty, project=empty)
        self.hook(cwd=empty, project=empty)
        (empty / "x").write_text("x")
        self.hook(cwd=empty, project=empty)
        self.assertEqual(len(self.runs()), 2)

    def test_fingerprint_does_not_follow_links_out_of_the_repo_or_through_the_stamp(self):
        outside = self.repo.parent / "outside"
        outside.mkdir()
        (outside / "a.txt").write_text("secret")
        self.git("rm", "-q", "a.txt")
        (self.repo / "dir").mkdir()
        (self.repo / "dir/a.txt").write_text("a")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "dir")
        (self.repo / "dir/a.txt").unlink()
        (self.repo / "dir").rmdir()
        (self.repo / "dir").symlink_to(outside)
        target = self.repo.parent / "target"
        target.write_text("keep")
        (self.repo / ".git/baseline-check").symlink_to(target)
        self.hook()
        (outside / "a.txt").write_text("changed")
        self.hook()
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(target.read_text(), "keep")

    def test_git_before_2_36_still_blocks(self):
        # `git worktree list -z` needs git 2.36; this stand-in refuses it like an older git.
        bin_ = self.repo.parent / "bin"
        bin_.mkdir()
        real = subprocess.run(["git", "--exec-path"], capture_output=True, text=True).stdout.strip() + "/git"
        (bin_ / "git").write_text(f'#!/bin/sh\ncase " $* " in *" worktree "*" -z "*) exit 129;; esac\nexec "{real}" "$@"\n')
        (bin_ / "git").chmod(0o755)
        (self.repo / "FAIL").write_text("")
        self.assertEqual(self.hook(path=f"{bin_}:{os.environ['PATH']}").returncode, 2)

    def test_a_project_without_git_is_a_non_blocking_error(self):
        self.assertEqual(self.hook(project=self.repo.parent).returncode, 1)
        self.assertEqual(self.runs(), [])

    def test_bad_input_is_a_non_blocking_error(self):
        result = subprocess.run([sys.executable, "-I", str(HOOK)], input="{", capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)


class SourceTests(unittest.TestCase):
    def test_embedded_hashes_match_core(self):
        import baseline as b
        core = ROOT / "core"
        actual = {rel: {kind: b.digest((core / rel).read_bytes(), kind)} for rel, spec in b.MANAGED.items()
                  for kind in spec}
        self.assertEqual(b.MANAGED, actual, "core/를 고쳤으면 baseline.py의 MANAGED를 이 값으로 바꾼다")

    def test_core_agents_md_shows_the_default_commands(self):
        import baseline as b
        text = (ROOT / "core/AGENTS.md").read_text(encoding="utf-8")
        for name, value in b.DEFAULT_COMMANDS.items():
            self.assertIn(b.command_line(name, value) + "\n", text)

    def test_core_instructions_use_no_emphasis_words(self):
        import baseline as b
        for rel in ("AGENTS.md", "REVIEW.md"):
            text = (ROOT / "core" / rel).read_bytes().replace(b.START, b"").replace(b.END, b"").decode("utf-8")
            for word in ("MUST", "NEVER", "!"):
                self.assertNotIn(word, text, rel)

    def test_pr_template_has_the_review_fields_enqueue_reads(self):
        text = (ROOT / "core/.github/pull_request_template.md").read_text(encoding="utf-8")
        review = text.split("## Review\n", 1)[1].splitlines()
        for field in ("리뷰한 head:", "등급:", "남은 지적:"):
            self.assertEqual([line for line in review if line.startswith(field)], [field], field)


    def test_core_reviewer_reading_fits_the_budget(self):
        import baseline as b
        size = sum(len((ROOT / rel).read_bytes()) for rel in ("core/AGENTS.md", "core/REVIEW.md", "prompts/review.md"))
        self.assertLessEqual(size, b.REVIEW_BYTES)


BOT = "dependabot[bot]"
BASE, HEAD = "b" * 40, "c" * 40
PR_URL = "https://github.com/o/r/pull/7"


class FakeGitHub:
    """Answers `gh api` like GitHub REST. Every other program call fails, and every call is kept."""

    def __init__(self, base, head, author="owner", fork=False):
        import baseline as b
        self.b = b
        self.calls, self.raw, self.moved = [], {}, False
        self.author, self.fork, self.commits = author, fork, {HEAD: sorted(set(base) ^ set(head) | {
            p for p in set(base) & set(head) if base[p] != head[p]})}
        self.pushes = [{"actor": {"login": author}, "after": HEAD}]
        self.patches, self.modes, self.base_modes, self.extra = {}, {}, {}, {}
        for ref, files in ((BASE, base), (HEAD, head)):
            for path, data in files.items():
                self.raw[("o/r", path, ref)] = data
        self.base, self.head = base, head

    def files(self):
        out = []
        for path in sorted(set(self.base) | set(self.head)):
            old, new = self.base.get(path), self.head.get(path)
            if old == new:
                continue
            status = "added" if old is None else "removed" if new is None else "modified"
            patch = self.patches.get(path)
            if patch is None and old is not None and new is not None:
                import difflib
                patch = "".join(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True), n=1))
                patch = patch.split("\n", 2)[2] if patch else ""
            out.append({"filename": path, "status": status, "patch": patch})
        return out

    def answer(self, path):
        from urllib.parse import unquote, urlsplit
        url = urlsplit(path)
        query = dict(part.split("=", 1) for part in url.query.split("&") if part)
        route = url.path
        if route in self.extra:
            return self.extra[route]
        if route == f"repos/o/r/git/trees/{HEAD}":
            return {"truncated": False, "tree": [{"path": p, "mode": self.modes.get(p, "100644")} for p in self.head]
                    + [{"path": p, "mode": m} for p, m in self.modes.items() if p not in self.head]}
        if route == f"repos/o/r/git/trees/{BASE}":
            return {"truncated": False, "tree": [{"path": p, "mode": self.base_modes.get(p, "100644")}
                                                 for p in self.base]}
        if route == "repos/o/r/activity":  # cursor-paged: the real endpoint ignores `page`
            return self.pushes if query.get("ref") == "topic" else []
        if query.get("page", "1") != "1":
            return {"files": []} if route.startswith("repos/o/r/commits/") else []
        if route == "repos/o/r/pulls/7":
            later = self.calls_to(route) > 1
            head = "d" * 40 if self.moved == "head" and later else HEAD
            base = "a" * 40 if self.moved == "base" and later else BASE
            return {"number": 7, "user": {"login": self.author},
                    "head": {"sha": head, "ref": "topic", "repo": {"full_name": "x/r" if self.fork else "o/r"}},
                    "base": {"sha": base, "ref": "main", "repo": {"full_name": "o/r"}}}
        if route == "repos/o/r/pulls/7/files":
            return self.files()
        if route == "repos/o/r/pulls/7/commits":
            return [{"sha": sha} for sha in self.commits]
        if route.startswith("repos/o/r/commits/"):
            return {"files": [{"filename": p} for p in self.commits[route.rsplit("/", 1)[1]]]}
        raise KeyError(route)

    def calls_to(self, route):
        return sum(1 for argv in self.calls if argv[-1].split("?")[0] == route)

    def run(self, argv, **kwargs):
        from urllib.parse import unquote, urlsplit
        self.calls.append(list(argv))
        if argv[:2] != ["gh", "api"]:
            return subprocess.CompletedProcess(argv, 1, b"", b"not gh api")
        path = argv[-1]
        if "/contents/" in path:
            url = urlsplit(path)
            repo, rel = url.path.split("/contents/", 1)
            data = self.raw.get((repo.removeprefix("repos/"), unquote(rel), unquote(url.query.split("ref=", 1)[1])))
            if data is None:
                return subprocess.CompletedProcess(argv, 1, b"", b"gh: Not Found (HTTP 404)\n")
            return subprocess.CompletedProcess(argv, 0, data, b"")
        try:
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.answer(path)).encode(), b"")
        except KeyError:
            return subprocess.CompletedProcess(argv, 1, b"", b"gh: Not Found (HTTP 404)\n")


def core_tree():
    import baseline as b
    tree = {rel: (ROOT / "core" / rel).read_bytes() for rel in b.MANAGED}
    tree[".baseline/baseline.py"] = (ROOT / "baseline.py").read_bytes()
    tree[".baseline/baseline.json"] = b.dump_json({"version": b.VERSION, "profiles": [], "managed": b.MANAGED})
    tree["README.md"] = b"# r\n"
    return tree


class PreflightTests(unittest.TestCase):
    def preflight(self, gh, *extra):
        import baseline as b
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from unittest import mock
        out, err = StringIO(), StringIO()
        with mock.patch.object(b.subprocess, "run", gh.run), redirect_stdout(out), redirect_stderr(err):
            code = b.main(["review-preflight", PR_URL, "--json", *extra])
        report = json.loads(out.getvalue()) if out.getvalue() else None
        return code, report, err.getvalue()

    def grade(self, head_changes, base=None, **kwargs):
        base = base or core_tree()
        head = dict(base, **head_changes)
        for path in [p for p, v in head.items() if v is None]:
            del head[path]
        code, report, err = self.preflight(FakeGitHub(base, head, **kwargs))
        self.assertEqual(code, 0, err)
        return report["grade"], report["reasons"]

    def test_docs_only_is_docs(self):
        self.assertEqual(self.grade({"README.md": b"# r2\n", "docs/a.md": b"a\n"})[0], "문서")

    def test_instructions_prompts_and_skills_are_not_docs(self):
        tree = core_tree()
        cases = {
            "AGENTS.md": tree["AGENTS.md"] + b"\nmore\n",
            "sub/CLAUDE.md": b"x\n",
            "prompts/review.md": b"x\n",
            "skills/tdd/SKILL.md": b"x\n",
            "notes/SKILL.md": b"x\n",
        }
        for path, data in cases.items():
            self.assertEqual(self.grade({path: data})[0], "쉬움", path)

    def test_managed_files_and_sensitive_paths_are_hard(self):
        tree = core_tree()
        cases = {
            ".github/pull_request_template.md": tree[".github/pull_request_template.md"] + b"x\n",
            "REVIEW.md": tree["REVIEW.md"].replace(b"## \xec\x9e\x85\xeb\xa0\xa5", b"## x"),
            ".github/workflows/ci.yml": b"x\n",
            ".claude/skills/tdd/SKILL.md": b"x\n",
            ".baseline/commands.json": b"{}\n",
            "app/package.json": b"{}\n",
            ".mcp.json": b"{}\n",
            ".mise.toml": b"x\n",
        }
        for path, data in cases.items():
            grade, reasons = self.grade({path: data})
            self.assertEqual(grade, "어려움", path)
            self.assertTrue(any(path in reason for reason in reasons), (path, reasons))

    def test_a_managed_block_counts_and_the_project_cells_do_not(self):
        tree = core_tree()
        agents = tree["AGENTS.md"]
        self.assertEqual(self.grade({"AGENTS.md": agents.replace("한 줄로".encode(), b"x")})[0], "쉬움")
        self.assertEqual(self.grade({"AGENTS.md": agents.replace("고치지 않는다".encode(), b"x")})[0], "어려움")
        self.assertEqual(self.grade({"AGENTS.md": agents.replace(b"<!-- baseline:end -->\n", b"")})[0], "어려움")

    def test_grade_inputs_come_from_base(self):
        tree = core_tree()
        listed = tree["REVIEW.md"].replace("- 아직 없음.\n\n## 코딩".encode(), "- `src/auth/**` 인증\n\n## 코딩".encode())
        base = dict(tree, **{"REVIEW.md": listed})
        self.assertEqual(self.grade({"src/auth/a.py": b"x\n"}, base=base)[0], "어려움")
        # Removing the line in the same PR does not lower the grade, and the removal itself is hard.
        self.assertEqual(self.grade({"REVIEW.md": tree["REVIEW.md"], "src/auth/a.py": b"x\n"}, base=base)[0],
                         "어려움")
        self.assertEqual(self.grade({"REVIEW.md": tree["REVIEW.md"]}, base=base)[0], "어려움")
        # A sensitive path the PR itself lists counts only from the next PR on.
        self.assertEqual(self.grade({"REVIEW.md": listed})[0], "쉬움")
        folder = tree["REVIEW.md"].replace("- 아직 없음.\n\n## 코딩".encode(), "- `src/auth` 인증\n\n## 코딩".encode())
        self.assertEqual(self.grade({"src/auth/a.py": b"x\n"}, base=dict(tree, **{"REVIEW.md": folder}))[0], "어려움")

    def test_sensitive_paths_written_as_prose_count(self):
        tree = core_tree()
        prose = tree["REVIEW.md"].replace("- 아직 없음.\n".encode(), "이 경로를 건드리면 어려움: `src/auth/**`, `pay.py`.\n".encode())
        base = dict(tree, **{"REVIEW.md": prose})
        self.assertEqual(self.grade({"src/auth/a.py": b"x\n"}, base=base)[0], "어려움")
        self.assertEqual(self.grade({"pay.py": b"x\n"}, base=base)[0], "어려움")

    def test_widening_the_standing_instruction_is_hard(self):
        agents = core_tree()["AGENTS.md"]
        line = "- 상시 지시: 문서·쉬움 PR은".encode()
        self.assertEqual(self.grade({"AGENTS.md": agents.replace(line, "- 상시 지시: 모든 PR은".encode())})[0],
                         "어려움")
        removed = b"".join(l for l in agents.splitlines(True) if not l.startswith(line))
        self.assertEqual(self.grade({"AGENTS.md": removed})[0], "쉬움")

    def test_uses_rest_only(self):
        tree = core_tree()
        gh = FakeGitHub(tree, dict(tree, **{"docs/a.md": b"a\n"}))
        self.assertEqual(self.preflight(gh)[0], 0)
        self.assertTrue(gh.calls)
        for argv in gh.calls:
            self.assertEqual(argv[:2], ["gh", "api"], argv)
            self.assertFalse(any("graphql" in arg.lower() for arg in argv), argv)

    def test_env_names_in_any_commit_stop_the_review(self):
        tree = core_tree()
        gh = FakeGitHub(tree, dict(tree, **{"docs/a.md": b"a\n"}))
        gh.commits["e" * 40] = ["app/.env"]
        code, report, _ = self.preflight(gh)
        self.assertEqual(code, 1)
        self.assertEqual(report["secret_hits"], ["app/.env"])
        self.assertIsNone(report["diff_argv"])

    def test_a_commit_at_the_rest_file_limit_fails(self):
        tree = core_tree()
        gh = FakeGitHub(tree, dict(tree, **{"docs/a.md": b"a\n"}))
        gh.commits["e" * 40] = [f"f{i}" for i in range(3000)]
        code, report, err = self.preflight(gh)
        self.assertEqual((code, report), (2, None))
        self.assertIn("3000", err)

    def test_head_moving_during_the_run_fails(self):
        tree = core_tree()
        gh = FakeGitHub(tree, dict(tree, **{"docs/a.md": b"a\n"}))
        for moved in ("head", "base"):
            gh.calls.clear()
            gh.moved = moved
            code, report, err = self.preflight(gh)
            self.assertEqual(code, 2, moved)
            self.assertIsNone(report)
            self.assertIn("바뀌었다", err)

    def test_fork_and_diff_command(self):
        tree = core_tree()
        code, report, _ = self.preflight(FakeGitHub(tree, dict(tree, **{"docs/a.md": b"a\n"}), fork=True))
        self.assertEqual(code, 0)
        self.assertTrue(report["fork"])
        self.assertEqual(report["diff_argv"], ["git", "diff", f"{BASE}...{HEAD}", "--", ".", ":!.env*", ":!**/.env*"])

    # upgrade exception

    def upgrade(self, version="2.0.1", tag_core=None, extra=None, tag_version=None, status="ahead", modes=None):
        """Base is this core; head is the core of a tag whose AGENTS.md block says `tag_core`."""
        import baseline as b
        base = core_tree()
        agents = base["AGENTS.md"].replace("고치지 않는다".encode(), (tag_core or "고치지 않는다2").encode())
        managed = dict(b.MANAGED, **{"AGENTS.md": {"block_sha256": b.digest(agents, "block_sha256")}})
        source = base[".baseline/baseline.py"].decode()
        source = source.replace(f'VERSION = "{b.VERSION}"', f'VERSION = "{tag_version or version}"')
        source = source.replace(b.MANAGED["AGENTS.md"]["block_sha256"], managed["AGENTS.md"]["block_sha256"])
        head = dict(base, **{"AGENTS.md": agents, ".baseline/baseline.py": source.encode(),
                             ".baseline/baseline.json": b.dump_json({"version": version, "profiles": [],
                                                                     "managed": managed})})
        gh = FakeGitHub(base, dict(head, **(extra or {})))
        tag = "t" * 40
        gh.raw[(b.BASELINE_REPO, "baseline.py", tag)] = source.encode()
        gh.extra[f"repos/{b.BASELINE_REPO}/git/ref/tags/v{version}"] = {"object": {"type": "commit", "sha": tag}}
        gh.extra[f"repos/{b.BASELINE_REPO}/compare/{tag}...main"] = {"status": status}
        gh.modes.update(modes or {})
        code, report, err = self.preflight(gh)
        self.assertEqual(code, 0, err)
        return report["grade"], report["reasons"]

    def test_upgrade_with_the_tag_bytes_is_easy(self):
        self.assertEqual(self.upgrade()[0], "쉬움")

    def test_upgrade_with_a_different_byte_is_hard(self):
        base = core_tree()
        changed = base["AGENTS.md"].replace("고치지 않는다".encode(), "고치지 않는다3".encode())
        self.assertEqual(self.upgrade(extra={"AGENTS.md": changed})[0], "어려움")
        self.assertEqual(self.upgrade(extra={".baseline/baseline.py": b"x\n"})[0], "어려움")

    def test_upgrade_with_project_cells_or_other_files_is_hard(self):
        tree = core_tree()
        agents = tree["AGENTS.md"].replace("고치지 않는다".encode(), "고치지 않는다2".encode())
        self.assertEqual(self.upgrade(extra={"AGENTS.md": agents.replace("한 줄로".encode(), b"x")})[0], "어려움")
        self.assertEqual(self.upgrade(extra={"src/app.py": b"x\n"})[0], "어려움")
        self.assertEqual(self.upgrade(extra={".baseline/commands.json": b"{}\n"})[0], "어려움")

    def test_upgrade_needs_a_newer_tag_that_main_holds(self):
        self.assertEqual(self.upgrade(status="diverged")[0], "어려움")
        self.assertEqual(self.upgrade(version="2-x")[0], "어려움")
        self.assertEqual(self.upgrade(version="1.9.0")[0], "어려움")  # downgrade from 2.0.0-dev

    def test_upgrade_through_a_symlink_is_hard(self):
        grade, reasons = self.upgrade(modes={".baseline/baseline.py": "120000"})
        self.assertEqual(grade, "어려움")
        self.assertIn("symlink·submodule: .baseline/baseline.py", reasons)

    def test_symlinks_submodules_and_unprintable_names_are_hard(self):
        tree = core_tree()
        gh = FakeGitHub(tree, dict(tree, **{"docs/a.md": b"a\n"}))
        gh.modes["docs"] = "120000"
        code, report, _ = self.preflight(gh)
        self.assertEqual((code, report["grade"]), (0, "어려움"))
        self.assertEqual(self.grade({"docs/a\nb.md": b"a\n"})[0], "어려움")
        base = dict(tree, **{"docs/link.md": b"../.claude/settings.json"})
        gh = FakeGitHub(base, dict(base, **{"docs/link.md": b"now a file\n"}))
        gh.base_modes["docs/link.md"] = "120000"
        self.assertEqual(self.preflight(gh)[1]["grade"], "어려움")

    def test_nested_baseline_and_github_folders_are_sensitive(self):
        for path in ("vendor/x/.baseline/commands.json", "vendor/x/.github/workflows/ci.yml"):
            self.assertEqual(self.grade({path: b"x\n"})[0], "어려움", path)

    def test_upgrade_without_the_tag_is_hard(self):
        import baseline as b
        tree = core_tree()
        head = dict(tree, **{".baseline/baseline.json": b.dump_json({"version": "9.9.9", "profiles": [],
                                                                     "managed": b.MANAGED})})
        code, report, _ = self.preflight(FakeGitHub(tree, head))
        self.assertEqual((code, report["grade"]), (0, "어려움"))

    # Dependabot exception

    def bump(self, old, new, author=BOT, pushers=(BOT,), path="package-lock.json"):
        base = dict(core_tree(), **{path: old.encode()})
        gh = FakeGitHub(base, dict(base, **{path: new.encode()}), author=author)
        gh.pushes = [{"actor": {"login": login}, "after": HEAD if i == 0 else "f" * 40}
                     for i, login in enumerate(pushers)]
        code, report, err = self.preflight(gh)
        self.assertEqual(code, 0, err)
        return report["grade"], report["reasons"]

    LOCK = ('{\n  "packages": {\n    "node_modules/a": {\n      "version": "1.2.3",\n'
            '      "integrity": "sha512-AAAA=="\n    }\n  }\n}\n')

    def test_dependabot_minor_and_patch_is_easy(self):
        new = self.LOCK.replace("1.2.3", "1.3.0").replace("sha512-AAAA==", "sha512-BBBB==")
        self.assertEqual(self.bump(self.LOCK, new)[0], "쉬움")

    def test_dependabot_major_is_hard(self):
        self.assertEqual(self.bump(self.LOCK, self.LOCK.replace("1.2.3", "2.0.0"))[0], "어려움")

    def test_dependabot_new_dependency_is_hard(self):
        new = self.LOCK.replace('    "node_modules/a"', '    "node_modules/b": {\n      "version": "1.0.0"\n    },\n'
                                '    "node_modules/a"')
        self.assertEqual(self.bump(self.LOCK, new)[0], "어려움")

    def test_dependabot_change_outside_versions_is_hard(self):
        new = self.LOCK.replace("1.2.3", "1.2.4").replace('"version"', '"resolved": "https://x", "version"')
        self.assertEqual(self.bump(self.LOCK, new)[0], "어려움")
        self.assertEqual(self.bump("a\n", "b\n", path="src/app.py")[0], "쉬움")  # not the exception: general rules

    def test_dependabot_pushed_by_someone_else_is_hard(self):
        new = self.LOCK.replace("1.2.3", "1.2.4")
        self.assertEqual(self.bump(self.LOCK, new, pushers=(BOT, "owner"))[0], "어려움")
        self.assertEqual(self.bump(self.LOCK, new, pushers=())[0], "어려움")
        # The activity endpoint ignores `page`; a full page cannot be read to the end.
        self.assertEqual(self.bump(self.LOCK, new, pushers=(BOT,) * 100)[0], "어려움")

    def test_dependabot_is_the_pr_author_login_not_a_git_name(self):
        new = self.LOCK.replace("1.2.3", "1.2.4")
        self.assertEqual(self.bump(self.LOCK, new, author="owner")[0], "어려움")


if __name__ == "__main__":
    unittest.main()
