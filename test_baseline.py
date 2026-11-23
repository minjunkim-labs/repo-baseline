"""baseline.py v2 tests. The seam is the command line: init a temporary repo, then run the copy in .baseline/."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REAL_RUN = subprocess.run  # tests patch subprocess.run; git still runs for real
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
        import baseline as b
        written = sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*") if p.is_file())
        skills = sorted(rel for rel in b.MANAGED if rel.startswith(".claude/skills/"))
        self.assertIn(".claude/skills/tdd/SKILL.md", skills)
        self.assertEqual([rel for rel in written if rel not in skills], [
            ".baseline/baseline.json", ".baseline/baseline.py", ".baseline/commands.json",
            ".claude/hooks/allow_enqueue.py", ".claude/hooks/check.py", ".claude/settings.json",
            ".gitattributes", ".github/pull_request_template.md", "AGENTS.md", "CLAUDE.md", "REVIEW.md",
            "docs/agents/LICENSE", "docs/agents/domain.md", "docs/agents/issue-tracker.md",
            "docs/agents/triage-labels.md"])
        self.assertEqual(sorted(set(written) & set(skills)), skills)
        self.assertEqual((self.repo / ".claude/skills/tdd/SKILL.md").read_bytes(),
                         (ROOT / "skills/tdd/SKILL.md").read_bytes())
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

    def test_editing_a_skill_copy_fails(self):
        self.init()
        with (self.repo / ".claude/skills/tdd/SKILL.md").open("a", encoding="utf-8") as f:
            f.write("x\n")
        self.assertCheck(1, ".claude/skills/tdd/SKILL.md: 파일이 이 판과 다르다")

    def test_an_extra_file_in_a_skill_copy_fails_and_a_project_skill_passes(self):
        self.init()
        (self.repo / ".claude/skills/mine").mkdir()
        (self.repo / ".claude/skills/mine/SKILL.md").write_text("mine\n", encoding="utf-8")
        self.assertCheck(0)
        (self.repo / ".claude/skills/tdd/extra.md").write_text("x\n", encoding="utf-8")
        self.assertCheck(1, ".claude/skills/tdd/extra.md: 이 판의 스킬 사본에 없는 파일이다")

    def test_a_linked_skill_copy_fails_without_walking_the_link(self):
        self.init()
        outside = Path(self.tmp.name + "-outside")
        self.addCleanup(shutil.rmtree, outside, True)
        shutil.copytree(self.repo / ".claude/skills/tdd", outside)
        (outside / "far.md").write_text("x\n", encoding="utf-8")
        shutil.rmtree(self.repo / ".claude/skills/tdd")
        (self.repo / ".claude/skills/tdd").symlink_to(outside)
        self.assertCheck(1, ".claude/skills/tdd/SKILL.md: 없거나 일반 파일이 아니다")
        self.assertNotIn("far.md", self.check().stderr)

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

    def test_a_newline_in_a_worktree_path_does_not_forge_an_entry(self):
        evil = self.repo.parent / "evil"
        self.git("worktree", "add", "-q", "-b", "nl", f"{self.repo.parent}/a\nworktree {evil}")
        (evil / ".baseline").mkdir(parents=True)
        (evil / ".git").write_text(f"gitdir: {self.repo}/.git\n")
        (evil / ".baseline/baseline.py").write_text(FAKE_BASELINE)
        self.assertEqual(self.hook(cwd=evil).returncode, 0)
        self.assertEqual(self.runs(), [])

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
        actual = {rel: {kind: b.digest(b.source(rel).read_bytes(), kind)} for rel, spec in b.MANAGED.items()
                  for kind in spec}
        self.assertEqual(b.MANAGED, actual, "core/·skills/를 고쳤으면 baseline.py의 MANAGED를 이 값으로 바꾼다")

    def test_skill_copies_match_the_lock(self):
        import baseline as b
        lock = json.loads((ROOT / "skills/skills.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(b.lock_problems(lock), [])
        on_disk = sorted(p.relative_to(ROOT / "skills").as_posix() for p in (ROOT / "skills").rglob("*")
                         if p.is_file() and p.name != "skills.lock.json")
        managed = sorted(rel[len(b.SKILLS):] for rel in b.MANAGED if rel.startswith(b.SKILLS))
        self.assertEqual(on_disk, managed)
        for name in lock["skills"]:
            self.assertIn(f"{name}/SKILL.md", managed)
            self.assertIn(f"{name}/LICENSE", managed)

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

    def graphql(self, argv):
        return subprocess.CompletedProcess(argv, 1, b"", b"no graphql here")

    def calls_to(self, route):
        return sum(1 for argv in self.calls if argv[-1].split("?")[0] == route)

    def run(self, argv, **kwargs):
        from urllib.parse import unquote, urlsplit
        self.calls.append(list(argv))
        if argv[:2] != ["gh", "api"]:
            return subprocess.CompletedProcess(argv, 1, b"", b"not gh api")
        if argv[2] == "graphql":
            return self.graphql(argv)
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
    tree = {rel: b.source(rel).read_bytes() for rel in b.MANAGED}
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


def tagged_core(version, agents=None, profiles=None):
    """A repo-baseline tag tree: contents paths + consumer paths with MANAGED hashes for `version`."""
    import baseline as b
    base = core_tree()
    agents = agents if agents is not None else base["AGENTS.md"]
    managed = dict(b.MANAGED, **{"AGENTS.md": {"block_sha256": b.digest(agents, "block_sha256")}})
    source = base[".baseline/baseline.py"].decode()
    source = source.replace(f'VERSION = "{b.VERSION}"', f'VERSION = "{version}"')
    source = source.replace(b.MANAGED["AGENTS.md"]["block_sha256"], managed["AGENTS.md"]["block_sha256"])
    source = source.encode()
    remote = {b.repo_rel(rel): (agents if rel == "AGENTS.md" else base[rel]) for rel in managed}
    remote["baseline.py"] = source
    consumer = {rel: (agents if rel == "AGENTS.md" else base[rel]) for rel in managed}
    consumer[".baseline/baseline.py"] = source
    consumer[".baseline/baseline.json"] = b.dump_json({"version": version, "profiles": profiles or [], "managed": managed})
    return remote, consumer, managed, source


class UpgradeTests(unittest.TestCase):
    """upgrade <tag> in a temporary consumer; GitHub REST is faked."""

    def setUp(self):
        import baseline as b
        self.b = b
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.before_remote, self.before, _, _ = tagged_core("2.0.0", profiles=["keep"])
        agents = core_tree()["AGENTS.md"].replace("고치지 않는다".encode(), "고치지 않는다2".encode())
        self.after_remote, _, self.after_managed, self.after_source = tagged_core("2.0.1", agents, profiles=["keep"])
        self.base = dict(self.before)
        self.base["AGENTS.md"] = self.before["AGENTS.md"].replace("# 프로젝트 이름".encode(), "# 내 앱".encode(), 1)
        for rel, data in self.base.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.sha, self.old = "t" * 40, "s" * 40
        self.gh = FakeGitHub(self.base, self.base)
        self.gh.raw.clear()
        for rel, data in self.before_remote.items():
            self.gh.raw[(b.BASELINE_REPO, rel, self.old)] = data
        for rel, data in self.after_remote.items():
            self.gh.raw[(b.BASELINE_REPO, rel, self.sha)] = data
        self.gh.extra.update({
            f"repos/{b.BASELINE_REPO}/git/ref/tags/v2.0.0": {"object": {"type": "commit", "sha": self.old}},
            f"repos/{b.BASELINE_REPO}/git/ref/tags/v2.0.1": {"object": {"type": "commit", "sha": self.sha}},
            f"repos/{b.BASELINE_REPO}/compare/{self.old}...main": {"status": "ahead"},
            f"repos/{b.BASELINE_REPO}/compare/{self.sha}...main": {"status": "ahead"},
        })

    def tearDown(self):
        self.tmp.cleanup()

    def run_upgrade(self, tag="v2.0.1"):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from unittest import mock
        out, err = StringIO(), StringIO()
        with mock.patch.object(self.b.subprocess, "run", self.gh.run), \
                mock.patch.object(self.b, "repo_root", lambda: self.repo), \
                redirect_stdout(out), redirect_stderr(err):
            code = self.b.main(["upgrade", tag])
        return code, out.getvalue() + err.getvalue()

    def test_stops_when_a_managed_block_was_edited(self):
        path = self.repo / "AGENTS.md"
        edited = path.read_bytes().replace("고치지 않는다".encode(), "고치지 않는다!".encode())
        path.write_bytes(edited)
        code, out = self.run_upgrade()
        self.assertEqual(code, 1, out)
        self.assertIn("관리 블록이 고쳐져 있다", out)
        self.assertIn("--- a/AGENTS.md", out)
        self.assertEqual(path.read_bytes(), edited)
        self.assertEqual(json.loads((self.repo / ".baseline/baseline.json").read_bytes())["version"], "2.0.0")

    def test_read_failure_on_existing_block_file_does_not_replace_it(self):
        path = self.repo / "REVIEW.md"
        before = path.read_bytes()
        from unittest import mock
        real = self.b.read_file
        seen = {"n": 0}

        def boom(root, rel):
            if rel == "REVIEW.md":
                seen["n"] += 1
                if seen["n"] > 1:  # stop-check already read once; fail on the write pass
                    raise OSError(f"{self.b.MAX_READ}바이트를 넘는다")
            return real(root, rel)

        with mock.patch.object(self.b, "read_file", boom):
            code, out = self.run_upgrade()
        self.assertEqual(code, 2, out)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads((self.repo / ".baseline/baseline.json").read_bytes())["version"], "2.0.0")

    def test_upgrade_result_is_easy_for_review_preflight(self):
        extra = self.repo / ".claude/skills/code-review/local.md"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b"local\n")
        settings = b'{"args": ["--sha256", "' + (b"0" * 64) + b'"]}\n'
        (self.repo / ".claude/settings.json").write_bytes(settings)
        code, out = self.run_upgrade()
        self.assertEqual(code, 0, out)
        agents = (self.repo / "AGENTS.md").read_bytes()
        self.assertIn("# 내 앱".encode(), agents)
        self.assertEqual(self.b.digest(agents, "block_sha256"), self.after_managed["AGENTS.md"]["block_sha256"])
        self.assertEqual((self.repo / ".baseline/baseline.py").read_bytes(), self.after_source)
        self.assertFalse(extra.exists())
        pin = self.b.sha256(self.after_source).encode()
        self.assertIn(pin, (self.repo / ".claude/settings.json").read_bytes())
        recorded = json.loads((self.repo / ".baseline/baseline.json").read_bytes())
        self.assertEqual((recorded["version"], recorded["profiles"], recorded["managed"]),
                         ("2.0.1", ["keep"], self.after_managed))
        base = dict(self.base)
        base[".claude/skills/code-review/local.md"] = b"local\n"
        base[".claude/settings.json"] = settings
        head = dict(base)
        for rel in list(self.after_managed) + [".baseline/baseline.py", ".baseline/baseline.json",
                                               ".claude/settings.json"]:
            head[rel] = (self.repo / rel).read_bytes()
        del head[".claude/skills/code-review/local.md"]
        gh = FakeGitHub(base, head)
        gh.raw[(self.b.BASELINE_REPO, "baseline.py", self.sha)] = self.after_source
        gh.extra[f"repos/{self.b.BASELINE_REPO}/git/ref/tags/v2.0.1"] = {
            "object": {"type": "commit", "sha": self.sha}}
        gh.extra[f"repos/{self.b.BASELINE_REPO}/compare/{self.sha}...main"] = {"status": "ahead"}
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from unittest import mock
        stdout, stderr = StringIO(), StringIO()
        with mock.patch.object(self.b.subprocess, "run", gh.run), redirect_stdout(stdout), redirect_stderr(stderr):
            preflight = self.b.main(["review-preflight", PR_URL, "--json"])
        self.assertEqual(preflight, 0, stderr.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["grade"], "쉬움")

    def test_a_new_block_file_matches_the_tag_and_other_bytes_stay_hard(self):
        notes = "제목\n<!-- baseline:start -->\n본문\n<!-- baseline:end -->\n꼬리\n".encode()
        digest = self.b.digest(notes, "block_sha256")
        source = self.after_source.replace(
            b"MANAGED = {\n",
            b'MANAGED = {\n    "NOTES.md": {"block_sha256": "%s"},\n' % digest.encode(),
            1)
        self.gh.raw[(self.b.BASELINE_REPO, "baseline.py", self.sha)] = source
        self.gh.raw[(self.b.BASELINE_REPO, "core/NOTES.md", self.sha)] = notes
        code, out = self.run_upgrade()
        self.assertEqual(code, 0, out)
        self.assertEqual((self.repo / "NOTES.md").read_bytes(), notes)
        base = dict(self.base)
        head = dict(base)
        for rel in list(self.b.embedded_managed(source)) + [".baseline/baseline.py", ".baseline/baseline.json"]:
            head[rel] = (self.repo / rel).read_bytes()

        def grade(tree):
            gh = FakeGitHub(base, tree)
            gh.raw[(self.b.BASELINE_REPO, "baseline.py", self.sha)] = source
            gh.raw[(self.b.BASELINE_REPO, "core/NOTES.md", self.sha)] = notes
            gh.extra[f"repos/{self.b.BASELINE_REPO}/git/ref/tags/v2.0.1"] = {
                "object": {"type": "commit", "sha": self.sha}}
            gh.extra[f"repos/{self.b.BASELINE_REPO}/compare/{self.sha}...main"] = {"status": "ahead"}
            from contextlib import redirect_stderr, redirect_stdout
            from io import StringIO
            from unittest import mock
            stdout, stderr = StringIO(), StringIO()
            with mock.patch.object(self.b.subprocess, "run", gh.run), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                preflight = self.b.main(["review-preflight", PR_URL, "--json"])
            self.assertEqual(preflight, 0, stderr.getvalue())
            return json.loads(stdout.getvalue())["grade"]

        self.assertEqual(grade(head), "쉬움")
        changed = dict(head)
        changed["NOTES.md"] = "다른 바깥\n<!-- baseline:start -->\n본문\n<!-- baseline:end -->\n꼬리\n".encode()
        self.assertEqual(self.b.digest(changed["NOTES.md"], "block_sha256"), digest)
        self.assertEqual(grade(changed), "어려움")

    def test_an_edited_block_on_a_dev_version_stops_without_a_tree(self):
        recorded = json.loads((self.repo / ".baseline/baseline.json").read_bytes())
        recorded["version"] = "2.0.0-dev"
        (self.repo / ".baseline/baseline.json").write_bytes(self.b.dump_json(recorded))
        path = self.repo / "AGENTS.md"
        edited = path.read_bytes().replace("고치지 않는다".encode(), "고치지 않는다!".encode())
        path.write_bytes(edited)
        from unittest import mock
        with mock.patch.object(self.b, "source_root", lambda: None):
            code, out = self.run_upgrade()
        self.assertEqual(code, 1, out)
        self.assertIn("관리 블록이 고쳐져 있다", out)
        self.assertEqual(path.read_bytes(), edited)
        self.assertEqual(json.loads((self.repo / ".baseline/baseline.json").read_bytes())["version"], "2.0.0-dev")

    def test_missing_markers_do_not_skip_edit_check_when_tag_switches_to_sha256(self):
        """None == None must not skip the stop; a finished sha256 write may resume."""
        path = self.repo / "AGENTS.md"
        stripped = b"project only, no managed markers\n"
        path.write_bytes(stripped)
        whole = b"tag whole file\n"
        after_managed = {rel: ( {"sha256": self.b.sha256(whole)} if rel == "AGENTS.md" else spec)
                         for rel, spec in self.after_managed.items()}
        source = self.after_source.decode()
        # Replace MANAGED via the live module helper used by skills-bump-style rewrites is heavy;
        # build a tiny baseline.py the way other upgrade tests embed MANAGED.
        source = (f'VERSION = "2.0.1"\nMANAGED = {after_managed!r}\n').encode()
        self.gh.raw[(self.b.BASELINE_REPO, "baseline.py", self.sha)] = source
        self.gh.raw[(self.b.BASELINE_REPO, "core/AGENTS.md", self.sha)] = whole
        for rel, data in self.after_remote.items():
            if rel not in ("baseline.py", "core/AGENTS.md"):
                self.gh.raw[(self.b.BASELINE_REPO, rel, self.sha)] = data
        code, out = self.run_upgrade()
        self.assertEqual(code, 1, out)
        self.assertIn("관리 블록이 고쳐져 있다", out)
        self.assertEqual(path.read_bytes(), stripped)
        path.write_bytes(whole)
        code, out = self.run_upgrade()
        self.assertEqual(code, 0, out)
        self.assertEqual(path.read_bytes(), whole)
        self.assertEqual(json.loads((self.repo / ".baseline/baseline.json").read_bytes())["version"], "2.0.1")

    def test_a_cleanup_failure_does_not_record_the_version_and_retry_finishes(self):
        extra = self.repo / ".claude/skills/code-review/local.md"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b"local\n")
        real = Path.unlink

        def boom(self, *args, **kwargs):
            if self.name == "local.md":
                raise OSError("cleanup")
            return real(self, *args, **kwargs)

        from unittest import mock
        with mock.patch.object(Path, "unlink", boom):
            code, out = self.run_upgrade()
        self.assertEqual(code, 2, out)
        self.assertTrue(extra.exists())
        self.assertEqual(json.loads((self.repo / ".baseline/baseline.json").read_bytes())["version"], "2.0.0")
        code, out = self.run_upgrade()
        self.assertEqual(code, 0, out)
        self.assertFalse(extra.exists())
        self.assertEqual(json.loads((self.repo / ".baseline/baseline.json").read_bytes())["version"], "2.0.1")


REPORT = ("## Summary\n완료 기준: x\n\n## Review\n리뷰어(구현과 다른 컨텍스트): 하위 에이전트\n리뷰한 head: {head}\n"
          "등급: {grade}\n고친 것: 없음\n남은 지적: {left}\n외부 리뷰 판정: 없음\n\n## Summary by CodeRabbit\n등급: 문서\n")
REPORTED = "2026-01-01T00:10:00Z"


class EnqueueGitHub(FakeGitHub):
    """FakeGitHub plus what enqueue reads: required CI, permissions, review activity and the GraphQL PR."""

    def __init__(self, base, head, body="", **kwargs):
        super().__init__(base, head, **kwargs)
        self.body, self.mutations, self.commit_author = body, [], {"login": self.author}
        self.edits = [(REPORTED, "User", "owner")]
        self.checks = [{"id": 1, "name": "ci", "status": "completed", "conclusion": "success", "app": {"id": 15368}}]
        self.permission = {"owner": "admin", "helper": "write", "reader": "read"}
        self.extra.update({
            "repos/o/r/branches/main": {"protection": {"required_status_checks": {
                "checks": [{"context": "ci", "app_id": 15368}], "contexts": ["ci"]}}},
            "repos/o/r/rules/branches/main": [],
            f"repos/o/r/commits/{HEAD}/status": {"statuses": []},
            "repos/o/r/pulls/7/reviews": [], "repos/o/r/pulls/7/comments": [], "repos/o/r/issues/7/comments": []})

    def answer(self, path):
        route = path.split("?")[0]
        if route == f"repos/o/r/commits/{HEAD}/check-runs":
            return {"check_runs": self.checks}
        if route == "repos/o/r/pulls/7/commits" and "page=1" in path:
            return [{"sha": sha, "author": self.commit_author} for sha in self.commits]
        if route.startswith("repos/o/r/collaborators/"):
            return {"permission": self.permission.get(route.split("/")[4], "none")}
        return super().answer(path)

    def graphql(self, argv):
        fields = dict(argv[i + 1].split("=", 1) for i, a in enumerate(argv) if a in ("-f", "-F"))
        if "enqueuePullRequest" in fields["query"]:
            self.mutations.append(fields)
            data = {"enqueuePullRequest": {"mergeQueueEntry": {"position": 1}}}
        else:
            edits = [{"editedAt": t, "editor": {"__typename": kind, "login": login}} for t, kind, login in self.edits]
            data = {"repository": {"pullRequest": {"id": "PR_7", "body": self.body, "createdAt": "2026-01-01T00:00:00Z",
                                                   "userContentEdits": {"totalCount": len(edits), "nodes": edits}}}}
        return subprocess.CompletedProcess(argv, 0, json.dumps({"data": data}).encode(), b"")


class EnqueueTests(unittest.TestCase):
    def gh(self, changes=None, grade="쉬움", left="없음", reviewed=HEAD, **kwargs):
        tree = core_tree()
        head = dict(tree, **(changes or {"src/app.py": b"x\n"}))
        body = REPORT.format(head=reviewed, grade=grade, left=left) if grade else ""
        return EnqueueGitHub(tree, head, body=body, **kwargs)

    def enqueue(self, gh, sha=HEAD, remote="false"):
        import baseline as b
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from unittest import mock
        out = StringIO()
        with mock.patch.object(b.subprocess, "run", gh.run), mock.patch.dict(b.os.environ, {"CLAUDE_CODE_REMOTE": remote}), \
                redirect_stdout(out), redirect_stderr(out):
            code = b.main(["enqueue", PR_URL, sha])
        return code, out.getvalue()

    def assertQueued(self, gh):
        code, out = self.enqueue(gh)
        self.assertEqual(code, 0, out)
        self.assertEqual(gh.mutations, [{"query": gh.mutations[0]["query"], "id": "PR_7", "sha": HEAD}])
        self.assertIn("expectedHeadOid", gh.mutations[0]["query"])

    def assertRefused(self, gh, reason, sha=HEAD):
        code, out = self.enqueue(gh, sha)
        self.assertEqual(code, 1, out)
        self.assertIn(reason, out)
        self.assertEqual(gh.mutations, [])

    def test_easy_pr_with_a_clean_report_is_queued_at_that_head(self):
        self.assertQueued(self.gh())

    def test_docs_pr_needs_ci_and_no_report(self):
        self.assertQueued(self.gh({"docs/a.md": b"a\n"}, grade=None))
        gh = self.gh({"docs/a.md": b"a\n"}, grade=None)
        gh.checks[0]["conclusion"] = "failure"
        self.assertRefused(gh, "ci")

    def test_docs_pr_ignores_bot_comments_nobody_judges(self):
        gh = self.gh({"docs/a.md": b"a\n"}, grade=None)
        gh.edits = []
        gh.extra["repos/o/r/issues/7/comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                                    "created_at": "2026-01-01T00:20:00Z"}]
        self.assertQueued(gh)

    def test_easy_pr_needs_the_report(self):
        self.assertRefused(self.gh(grade=None), "리뷰한 head")
        gh = self.gh()
        gh.body = gh.body.replace("등급: 쉬움\n", "")
        self.assertRefused(gh, "「등급」이 없다")

    def test_hard_grade_is_always_refused(self):
        self.assertRefused(self.gh({".github/workflows/x.yml": b"on: push\n"}), "어려움")
        self.assertRefused(self.gh({"AGENTS.md": core_tree()["AGENTS.md"].replace(b"POLICY.md]", b"POLICY.mdx]")}), "어려움")

    def test_report_grade_above_the_path_grade_wins(self):
        self.assertRefused(self.gh(grade="어려움"), "어려움")
        docs = {"docs/a.md": b"a\n"}
        self.assertQueued(self.gh(docs, grade="쉬움"))  # raised to easy: the easy report is complete
        self.assertRefused(self.gh(docs, grade="쉬움", reviewed="d" * 40), "리뷰한 head")
        self.assertRefused(self.gh(docs, grade="모름"), "등급")

    def test_head_mismatch_is_refused(self):
        self.assertRefused(self.gh(), "head", sha="d" * 40)
        self.assertRefused(self.gh(reviewed="d" * 40), "리뷰한 head")
        self.assertRefused(self.gh(reviewed="`" + HEAD + "`" + "x"), "리뷰한 head")

    def test_ci_not_passed_is_refused(self):
        for run in ({"status": "in_progress", "conclusion": None}, {"conclusion": "failure"},
                    {"app": {"id": 1}}, {"name": "other"}):
            gh = self.gh()
            gh.checks[0].update(run)
            self.assertRefused(gh, "ci")
        gh = self.gh()
        gh.checks.append(dict(gh.checks[0], id=2, conclusion="failure"))  # the latest run counts
        self.assertRefused(gh, "ci")
        gh = self.gh()
        gh.extra["repos/o/r/branches/main"] = {"protection": {"enabled": False}}
        self.assertRefused(gh, "필수 CI")

    def test_required_checks_from_rulesets_and_statuses_count(self):
        gh = self.gh()
        gh.extra["repos/o/r/rules/branches/main"] = [{"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": "lint"}]}}]
        self.assertRefused(gh, "lint")
        gh.extra[f"repos/o/r/commits/{HEAD}/status"] = {"statuses": [{"context": "lint", "state": "success"}]}
        self.assertQueued(gh)

    def test_a_failing_status_with_the_check_name_counts(self):
        gh = self.gh()
        gh.extra["repos/o/r/branches/main"] = {"protection": {"required_status_checks": {"contexts": ["ci"]}}}
        gh.extra[f"repos/o/r/commits/{HEAD}/status"] = {"statuses": [{"context": "ci", "state": "failure"}]}
        self.assertRefused(gh, "ci")

    def test_changes_requested_blocks_even_a_docs_pr(self):
        gh = self.gh({"docs/a.md": b"a\n"}, grade=None)
        gh.extra["repos/o/r/pulls/7/reviews"] = [
            {"user": {"login": "helper", "type": "User"}, "state": "CHANGES_REQUESTED", "submitted_at": "2026-01-01T00:01:00Z"},
            {"user": {"login": "coderabbitai[bot]", "type": "Bot"}, "state": "CHANGES_REQUESTED",
             "submitted_at": "2026-01-01T00:02:00Z"}]
        self.assertRefused(gh, "변경 요청: helper")
        gh = self.gh({"docs/a.md": b"a\n"}, grade=None)
        gh.extra["repos/o/r/pulls/7/reviews"] = [
            {"user": {"login": "helper", "type": "User"}, "state": "CHANGES_REQUESTED", "submitted_at": "2026-01-01T00:01:00Z"},
            {"user": {"login": "helper", "type": "User"}, "state": "APPROVED", "submitted_at": "2026-01-01T00:02:00Z"},
            {"user": {"login": "helper", "type": "User"}, "state": "COMMENTED", "submitted_at": "2026-01-01T00:03:00Z"}]
        self.assertQueued(gh)

    def test_remaining_findings_are_refused(self):
        self.assertRefused(self.gh(left="[Spec] P1 src/app.py:1 틀렸다"), "남은 지적")
        self.assertRefused(self.gh(left="없음\n- [Spec] P1 src/app.py:1 틀렸다"), "남은 지적")
        gh = self.gh()
        gh.body = gh.body.replace("남은 지적: 없음\n", "")
        self.assertRefused(gh, "남은 지적")
        gh = self.gh()
        gh.body += "\n## Review\n남은 지적: 없음\n"
        self.assertRefused(gh, "남은 지적")

    def test_unjudged_external_reviews_are_refused(self):
        late = "2026-01-01T00:20:00Z"
        for route, item in (("pulls/7/reviews", {"user": {"login": "coderabbitai[bot]"}, "state": "COMMENTED", "submitted_at": late}),
                            ("pulls/7/comments", {"user": {"login": "helper"}, "created_at": REPORTED,
                                                  "updated_at": late}),
                            ("issues/7/comments", {"user": {"login": "owner"}, "created_at": late})):
            gh = self.gh()
            gh.extra[f"repos/o/r/{route}"] = [item]
            self.assertRefused(gh, "판정하지 않은 외부 리뷰")
        gh = self.gh()
        gh.extra["repos/o/r/issues/7/comments"] = [{"user": {"login": "x[bot]"}, "created_at": "2026-01-01T00:05:00Z"}]
        gh.extra["repos/o/r/pulls/7/reviews"] = [{"user": {"login": "owner"}, "state": "PENDING", "submitted_at": None}]  # pending
        self.assertQueued(gh)

    def test_a_bot_editing_the_body_does_not_move_the_report_time(self):
        gh = self.gh()
        gh.edits.append(("2026-01-01T00:30:00Z", "Bot", "coderabbitai"))
        gh.extra["repos/o/r/issues/7/comments"] = [{"user": {"login": "coderabbitai[bot]"},
                                                    "created_at": "2026-01-01T00:20:00Z"}]
        self.assertRefused(gh, "판정하지 않은 외부 리뷰")

    def test_base_must_hold_the_standing_instruction(self):
        tree = core_tree()
        tree["AGENTS.md"] = b"".join(l for l in tree["AGENTS.md"].splitlines(True) if "상시 지시" not in l.decode())
        gh = EnqueueGitHub(tree, dict(tree, **{"src/app.py": b"x\n"}), body=REPORT.format(head=HEAD, grade="쉬움",
                                                                                          left="없음"))
        self.assertRefused(gh, "상시 지시")

    def test_fork_and_accounts_without_write_are_refused(self):
        self.assertRefused(self.gh(fork=True), "fork")
        self.assertRefused(self.gh(author="reader"), "reader")
        gh = self.gh()
        gh.commit_author = None
        self.assertRefused(gh, "커밋")
        gh = self.gh()
        gh.commit_author = {"login": "stranger"}
        self.assertRefused(gh, "stranger")

    def test_secret_names_stop_it(self):
        gh = self.gh()
        gh.commits["e" * 40] = ["app/.env"]
        self.assertRefused(gh, ".env")

    def test_cloud_and_a_bad_sha_stop_before_any_call(self):
        gh = self.gh()
        code, out = self.enqueue(gh, remote="true")
        self.assertEqual(code, 2)
        self.assertIn("클라우드", out)
        code, out = self.enqueue(gh, sha="c" * 39)
        self.assertEqual(code, 2)
        self.assertEqual(gh.calls, [])


class AllowEnqueueHookTests(unittest.TestCase):
    """The PreToolUse hook gets the event JSON on stdin and the pinned sha256 in argv, as settings.json gives it."""
    COMMAND = "python3 -I .baseline/baseline.py enqueue 7 " + HEAD
    HOOK = ROOT / "core/.claude/hooks/allow_enqueue.py"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "r"
        (self.repo / ".baseline").mkdir(parents=True)
        (self.repo / ".baseline/baseline.py").write_bytes((ROOT / "baseline.py").read_bytes())
        self.pinned = hashlib.sha256((ROOT / "baseline.py").read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, command=COMMAND, cwd=None, tool="Bash", argv=None):
        event = {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd or self.repo),
                 "permission_mode": "default", "hook_event_name": "PreToolUse"}
        result = subprocess.run([sys.executable, "-I", str(self.HOOK), *(argv or ["--sha256", self.pinned])],
                                input=json.dumps(event), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] if result.stdout else None

    def test_allows_the_exact_command_when_the_copy_has_the_pinned_hash(self):
        self.assertEqual(self.hook(), "allow")

    def test_settings_pin_this_baseline_py_and_allow_no_rule(self):
        settings = json.loads((ROOT / "core/.claude/settings.json").read_text(encoding="utf-8"))
        hook, = settings["hooks"]["PreToolUse"][0]["hooks"]
        self.assertEqual(hook["args"], ["-I", "${CLAUDE_PROJECT_DIR}/.claude/hooks/allow_enqueue.py",
                                        "--sha256", self.pinned])
        self.assertEqual((settings["permissions"]["allow"], settings["permissions"]["ask"]), ([], []))
        self.assertLessEqual({"Read(**/.env*)", "Read(**/.env*/**)"}, set(settings["permissions"]["deny"]))  # .envrc too

    def test_says_nothing_for_any_other_command(self):
        for command in (self.COMMAND + "; rm -rf ~", self.COMMAND + "\nrm x", "python3 .baseline/baseline.py enqueue 7 "
                        + HEAD, f"python3 -I .baseline/baseline.py enqueue {PR_URL} {HEAD}",
                        "python3 -I .baseline/baseline.py enqueue 7 " + HEAD[:39], "python3 -I .baseline/baseline.py check",
                        " " + self.COMMAND, "python3 -I .baseline/baseline.py enqueue 07 " + HEAD):
            self.assertIsNone(self.hook(command), command)
        self.assertIsNone(self.hook(tool="Monitor"))

    def test_says_nothing_when_the_copy_is_not_the_pinned_bytes(self):
        (self.repo / ".baseline/baseline.py").write_bytes(b"print('x')\n")
        self.assertIsNone(self.hook())
        self.assertIsNone(self.hook(cwd=self.tmp.name))  # no copy there
        for argv in ([], ["--sha256"], ["--sha256", "x" * 64], ["--sha", self.pinned]):
            self.assertIsNone(self.hook(argv=argv or ["--x"]), argv)

    def test_says_nothing_for_a_symlinked_copy(self):
        real = self.repo / "real.py"
        (self.repo / ".baseline/baseline.py").rename(real)
        (self.repo / ".baseline/baseline.py").symlink_to(real)
        self.assertIsNone(self.hook())

    def test_bad_input_says_nothing(self):
        result = subprocess.run([sys.executable, "-I", str(self.HOOK), "--sha256", self.pinned],
                                input="not json", capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

NOW = "2026-11-23T00:00:00+00:00"


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def days_ago(n):
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(NOW) - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeSources:
    """Answers `gh api` for skill sources: tags, commits by date, trees and file bytes per commit."""

    def __init__(self):
        self.tags, self.commits, self.trees, self.modes, self.calls = {}, {}, {}, {}, []
        self.corrupt, self.light = set(), set()

    def commit(self, repo, sha, age, files, tag=None, tag_age=None):
        self.commits.setdefault(repo, []).append((sha, days_ago(age)))
        self.trees[repo, sha] = files
        if tag:
            self.tags.setdefault(repo, []).append((tag, sha, days_ago(age if tag_age is None else tag_age)))

    def answer(self, route, query):
        repo = "/".join(route.split("/")[1:3])
        rest = route.split("/", 3)[3]
        if rest == "tags":
            return [] if query.get("page", "1") != "1" else [
                {"name": t, "commit": {"sha": c}} for t, c, _ in self.tags.get(repo, [])]
        if rest.startswith("git/ref/tags/"):
            t, c, _ = next(x for x in self.tags[repo] if x[0] == rest.rsplit("/", 1)[1])
            return {"object": {"type": "commit", "sha": c} if t in self.light else {"type": "tag", "sha": "t" + c[1:]}}
        if rest.startswith("git/tags/"):
            t, c, date = next(x for x in self.tags[repo] if "t" + x[1][1:] == rest.rsplit("/", 1)[1])
            return {"tagger": {"date": date}, "object": {"type": "commit", "sha": c}}
        if rest == "commits":
            ok = [(c, d) for c, d in self.commits[repo] if d <= query["until"]]
            return [{"sha": c, "commit": {"committer": {"date": d}}} for c, d in ok[-1:]]
        if rest.startswith("compare/"):
            a, b_ = rest.split("/", 1)[1].split("...")
            order = [c for c, _ in self.commits[repo]]
            return {"status": "identical" if a == b_ else "ahead" if order.index(a) < order.index(b_) else "behind"}
        if rest.startswith("git/trees/"):
            files = self.trees[repo, rest.rsplit("/", 1)[1]]
            return {"truncated": False, "tree": [
                {"path": p, "type": "blob", "mode": self.modes.get(p, "100644"), "sha": blob_sha(d), "size": len(d)}
                for p, d in files.items()]}
        raise KeyError(route)

    def run(self, argv, **kwargs):
        from urllib.parse import unquote, urlsplit
        self.calls.append(list(argv))
        if argv[:1] == ["git"]:
            return REAL_RUN(argv, **kwargs)
        if argv[:2] != ["gh", "api"]:
            return subprocess.CompletedProcess(argv, 1, b"", b"not gh api")
        url = urlsplit(argv[-1])
        query = dict(part.split("=", 1) for part in url.query.split("&") if part)
        if "/contents/" in url.path:
            repo, rel = url.path.split("/contents/", 1)
            files = self.trees.get((repo.split("/", 1)[1], unquote(query["ref"])), {})
            data = files.get(unquote(rel))
            if data is None:
                return subprocess.CompletedProcess(argv, 1, b"", b"gh: Not Found (HTTP 404)\n")
            return subprocess.CompletedProcess(argv, 0, data + (b"!" if unquote(rel) in self.corrupt else b""), b"")
        try:
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.answer(url.path, query)).encode(), b"")
        except (KeyError, StopIteration):
            return subprocess.CompletedProcess(argv, 1, b"", b"gh: Not Found (HTTP 404)\n")


def plugin(version):
    return json.dumps({"version": version}).encode()


class SkillsBumpTests(unittest.TestCase):
    """skills-bump in a temporary repo-baseline: skills/, its lock, baseline.py and .baseline/."""

    def setUp(self):
        import baseline as b
        self.b = b
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".baseline").mkdir()
        (self.root / "baseline.py").write_bytes((ROOT / "baseline.py").read_bytes())
        (self.root / ".baseline/baseline.json").write_bytes(b.dump_json({"version": "x", "managed": {}}))
        self.pin = '{"args": ["--sha256", "%s"]}\n'
        (self.root / ".claude").mkdir()
        (self.root / ".claude/settings.json").write_text(self.pin % ("0" * 64))  # any earlier hash is replaced
        self.gh = FakeSources()
        m = {"LICENSE": b"MIT m\n", "p.json": plugin("1.0.0"),
             "s/grill/SKILL.md": b"grill 1\n", "s/grilling/SKILL.md": b"grilling 1\n",
             "s/grilling/old.md": b"old\n", "s/other/SKILL.md": b"other\n"}
        self.gh.commit("m/s", "1" * 40, 60, m, tag="v1.0.0")
        p = {"pstack/LICENSE": b"MIT p\n", "pstack/plugin.json": plugin("0.1.0"), "pstack/skills/blast/SKILL.md": b"b1\n"}
        self.gh.commit("c/p", "a" * 40, 60, p)
        self.lock = {
            "sources": {
                "m": {"repo": "m/s", "update": "tag", "days": 7, "license": "LICENSE", "plugin": "p.json",
                      "tag": "v1.0.0", "commit": "1" * 40, "version": "1.0.0"},
                "p": {"repo": "c/p", "update": "commit", "branch": "main", "days": 7, "license": "pstack/LICENSE",
                      "plugin": "pstack/plugin.json", "commit": "a" * 40, "version": "0.1.0"}},
            "skills": {
                "grill": {"source": "m", "path": "s/grill", "requires": ["grilling"]},
                "grilling": {"source": "m", "path": "s/grilling", "requires": []},
                "blast": {"source": "p", "path": "pstack/skills/blast", "requires": []}}}
        self.write_lock()
        self.git("init", "-q")
        code, out = self.bump()  # the copies of the pins
        self.assertEqual(code, 0, out)
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "pins")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_lock(self):
        (self.root / "skills").mkdir(exist_ok=True)
        (self.root / "skills/skills.lock.json").write_bytes(self.b.dump_json(self.lock))

    def bump(self, *flags):
        from contextlib import redirect_stdout, redirect_stderr
        from datetime import datetime
        from io import StringIO
        from unittest import mock
        out, err = StringIO(), StringIO()
        with mock.patch.object(self.b.subprocess, "run", self.gh.run), redirect_stdout(out), redirect_stderr(err):
            code = self.b.skills_bump(self.root, "--check" in flags, datetime.fromisoformat(NOW))
        return code, out.getvalue() + err.getvalue()

    def read(self, rel):
        path = self.root / rel
        return path.read_bytes() if path.exists() else None

    def m_release(self, sha, age, version, grilling=b"grilling 2\n", tag_age=None):
        files = {"LICENSE": b"MIT m\n", "p.json": plugin(version), "s/grill/SKILL.md": b"grill " + version.encode() + b"\n",
                 "s/grilling/SKILL.md": grilling, "s/other/SKILL.md": b"other 2\n"}
        self.gh.commit("m/s", sha, age, files, tag="v" + version, tag_age=tag_age)

    def test_tag_source_takes_the_newest_tag_older_than_7_days(self):
        self.m_release("2" * 40, 10, "1.1.0")
        self.m_release("3" * 40, 3, "1.2.0")
        code, out = self.bump()
        self.assertEqual(code, 0, out)
        lock = json.loads(self.read("skills/skills.lock.json"))
        self.assertEqual({k: lock["sources"]["m"][k] for k in ("tag", "commit", "version")},
                         {"tag": "v1.1.0", "commit": "2" * 40, "version": "1.1.0"})
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1.1.0\n")
        self.assertEqual(self.read("skills/grill/LICENSE"), b"MIT m\n")
        self.assertIsNone(self.read("skills/other/SKILL.md"))  # not in the lock

    def test_a_tag_newer_than_7_days_is_not_taken_even_on_an_old_commit(self):
        self.m_release("2" * 40, 30, "1.1.0", tag_age=2)
        code, out = self.bump("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("새 판이 없다", out)

    def test_commit_source_takes_the_last_commit_older_than_7_days(self):
        files = dict(self.gh.trees["c/p", "a" * 40])
        self.gh.commit("c/p", "b" * 40, 10, dict(files, **{"pstack/skills/blast/SKILL.md": b"b2\n",
                                                           "pstack/plugin.json": plugin("0.2.0")}))
        self.gh.commit("c/p", "c" * 40, 2, dict(files, **{"pstack/skills/blast/SKILL.md": b"b3\n"}))
        code, out = self.bump()
        self.assertEqual(code, 0, out)
        lock = json.loads(self.read("skills/skills.lock.json"))["sources"]["p"]
        self.assertEqual((lock["commit"], lock["version"]), ("b" * 40, "0.2.0"))
        self.assertEqual(self.read("skills/blast/SKILL.md"), b"b2\n")
        self.assertEqual(self.read(".claude/skills/blast/LICENSE"), b"MIT p\n")

    def test_a_commit_source_never_goes_back(self):
        self.lock["sources"]["p"]["commit"] = "b" * 40
        self.write_lock()
        self.gh.commit("c/p", "b" * 40, 3, dict(self.gh.trees["c/p", "a" * 40]))
        code, out = self.bump("--check")
        self.assertEqual(code, 0, out)

    def test_a_new_tag_on_an_older_commit_is_not_taken(self):
        self.m_release("0" * 40, 90, "1.1.0", tag_age=10)
        commits = self.gh.commits["m/s"]
        commits.insert(0, commits.pop())  # 0... comes before the pinned 1...
        code, out = self.bump("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("새 판이 없다", out)

    def test_a_tag_behind_the_pin_is_skipped_for_an_older_tag_ahead_of_it(self):
        self.m_release("2" * 40, 10, "1.1.0")
        self.m_release("0" * 40, 90, "1.2.0", tag_age=8)
        commits = self.gh.commits["m/s"]
        commits.insert(0, commits.pop())  # 0... comes before the pinned 1...
        code, out = self.bump("--check")
        self.assertEqual(code, 1, out)
        self.assertIn("m: v1.0.0 → v1.1.0", out)

    def test_a_lightweight_tag_is_not_taken(self):
        self.m_release("2" * 40, 30, "1.1.0", tag_age=1)
        self.gh.light.add("v1.1.0")  # no tag date: the 30-day-old commit date says nothing about the tag
        code, out = self.bump("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("새 판이 없다", out)

    def test_a_skill_folder_with_uncommitted_changes_is_not_written(self):
        self.m_release("2" * 40, 10, "1.1.0")
        (self.root / "skills/grill/SKILL.md").write_bytes(b"local edit\n")
        (self.root / ".claude/skills/grilling/notes.md").write_bytes(b"untracked\n")
        lock = self.read("skills/skills.lock.json")
        code, out = self.bump()
        self.assertEqual(code, 2, out)
        self.assertIn("skills/grill/SKILL.md", out)
        self.assertIn(".claude/skills/grilling/notes.md", out)
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"local edit\n")
        self.assertEqual(self.read(".claude/skills/grilling/notes.md"), b"untracked\n")
        self.assertEqual(self.read("skills/skills.lock.json"), lock)

    def test_an_edit_git_status_hides_is_not_written_over(self):
        self.m_release("2" * 40, 10, "1.1.0")
        for flag, rel in (("--assume-unchanged", "skills/grill/SKILL.md"), ("--skip-worktree", ".claude/skills/grilling/SKILL.md")):
            self.git("update-index", flag, rel)
            (self.root / rel).write_bytes(b"hidden edit\n")
        code, out = self.bump()
        self.assertEqual(code, 2, out)
        self.assertIn("skills/grill/SKILL.md", out)
        self.assertIn(".claude/skills/grilling/SKILL.md", out)
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"hidden edit\n")
        self.assertEqual(self.read(".claude/skills/grilling/SKILL.md"), b"hidden edit\n")

    def test_a_linked_write_target_outside_the_skill_folders_stops_every_write(self):
        self.m_release("2" * 40, 10, "1.1.0")
        outside = Path(self.tmp.name + "-outside.json")
        outside.write_bytes(b"{}\n")
        self.addCleanup(outside.unlink)
        (self.root / ".baseline/baseline.json").unlink()
        (self.root / ".baseline/baseline.json").symlink_to(outside)
        code, out = self.bump()
        self.assertEqual(code, 2, out)
        self.assertIn(".baseline/baseline.json", out)
        self.assertEqual(outside.read_bytes(), b"{}\n")
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1\n")  # nothing written

    def test_a_linked_skill_folder_is_not_written_through(self):
        self.m_release("2" * 40, 10, "1.1.0")
        outside = Path(self.tmp.name + "-outside")
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside)
        shutil.rmtree(self.root / ".claude/skills/grill")
        (self.root / ".claude/skills/grill").symlink_to(outside)
        code, out = self.bump()
        self.assertEqual(code, 2, out)
        self.assertIn(".claude/skills/grill", out)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1\n")  # unchanged

    def test_git_files_in_a_skill_folder_are_refused(self):
        self.m_release("2" * 40, 10, "1.1.0")
        self.gh.trees["m/s", "2" * 40]["s/grill/.gitattributes"] = b"* -diff\n"
        code, out = self.bump()
        self.assertEqual(code, 2, out)
        self.assertIn(".gitattributes", out)
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1\n")  # unchanged

    def test_changing_a_skill_moves_its_required_skills_and_drops_removed_files(self):
        self.m_release("2" * 40, 10, "1.1.0")
        for root in ("skills", ".claude/skills"):
            self.assertEqual(self.read(f"{root}/grilling/old.md"), b"old\n")
        code, out = self.bump()
        self.assertEqual(code, 0, out)
        for root in ("skills", ".claude/skills"):
            self.assertEqual(self.read(f"{root}/grilling/SKILL.md"), b"grilling 2\n")
            self.assertIsNone(self.read(f"{root}/grilling/old.md"))
        managed = self.b.embedded_managed(self.read("baseline.py"))
        self.assertEqual(managed[".claude/skills/grilling/SKILL.md"], {"sha256": self.b.sha256(b"grilling 2\n")})
        self.assertNotIn(".claude/skills/grilling/old.md", managed)
        self.assertEqual(self.read(".baseline/baseline.py"), self.read("baseline.py"))
        self.assertEqual(json.loads(self.read(".baseline/baseline.json"))["managed"], managed)
        self.assertEqual(self.read(".claude/settings.json").decode(), self.pin % self.b.sha256(self.read("baseline.py")))

    def test_a_skill_added_to_the_lock_comes_from_the_pinned_version(self):
        code, out = self.bump()  # copies of the pins; no newer version exists
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1\n")
        self.lock = json.loads(self.read("skills/skills.lock.json"))
        self.lock["skills"]["other"] = {"source": "m", "path": "s/other", "requires": []}
        self.write_lock()
        code, out = self.bump()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read(".claude/skills/other/SKILL.md"), b"other\n")
        self.assertEqual(json.loads(self.read("skills/skills.lock.json"))["sources"]["m"]["tag"], "v1.0.0")
        self.assertEqual(self.bump("--check")[0], 0)

    def test_check_reports_without_writing(self):
        self.m_release("2" * 40, 10, "1.1.0")
        before = self.read("skills/skills.lock.json")
        code, out = self.bump("--check")
        self.assertEqual(code, 1, out)
        self.assertIn("m: v1.0.0 → v1.1.0", out)
        self.assertEqual(self.read("skills/skills.lock.json"), before)
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1\n")  # unchanged

    def test_a_new_version_without_changes_to_our_skills_is_no_update(self):
        files = dict(self.gh.trees["m/s", "1" * 40], **{"p.json": plugin("1.0.1")})
        self.gh.commit("m/s", "2" * 40, 10, files, tag="v1.0.1")
        for rel, data in {"grill/SKILL.md": b"grill 1\n", "grilling/SKILL.md": b"grilling 1\n",
                          "grilling/old.md": b"old\n"}.items():
            (self.root / "skills" / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / "skills" / rel).write_bytes(data)
            (self.root / "skills" / rel).with_name("LICENSE").write_bytes(b"MIT m\n")
        before = self.read("skills/skills.lock.json")
        code, out = self.bump("--check")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("skills/skills.lock.json"), before)

    def test_a_requirement_outside_the_lock_or_source_is_refused(self):
        self.lock["skills"]["grill"]["requires"] = ["blast"]
        self.write_lock()
        code, out = self.bump("--check")
        self.assertEqual(code, 2, out)
        self.assertIn("grill: 의존 스킬 blast", out)

    def test_a_symlink_in_a_skill_folder_is_refused_and_nothing_is_written(self):
        self.m_release("2" * 40, 10, "1.1.0")
        self.gh.modes["s/grilling/SKILL.md"] = "120000"
        code, out = self.bump()
        self.assertEqual(code, 2, out)
        self.assertIn("s/grilling/SKILL.md", out)
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1\n")  # unchanged

    def test_bytes_that_do_not_match_the_tree_are_refused(self):
        self.m_release("2" * 40, 10, "1.1.0")
        self.gh.corrupt.add("s/grill/SKILL.md")
        code, out = self.bump()
        self.assertEqual(code, 2, out)
        self.assertEqual(self.read("skills/grill/SKILL.md"), b"grill 1\n")  # unchanged


class DoctorTests(unittest.TestCase):
    def problems(self, **facts):
        import baseline as b
        base = {"versions": {name: "1.0.0" for name in b.DOCTOR_TOOLS}, "want": {}, "os": "linux",
                "wsl": False, "wsl_version": None, "repo": "/home/u/repo", "git_path": "/usr/bin/git",
                "skills_repo": [], "skills_user": [], "org": "acme",
                "environment": ["github.com/acme"], "mise_toml": None, "mise_trusted": True,
                "sandbox": False, "have_bubblewrap": True, "have_socat": True}
        base.update(facts)
        return "\n".join(b.doctor_problems(base))

    def test_a_different_version_prints_the_install_command(self):
        text = self.problems(versions={"python": "3.9.6", "git": "2.39.0", "gh": "2.40.0", "claude": "1.0.0", "mise": "2026.1.0"},
                             want={"python": "3.12"})
        self.assertIn("python 판이 다르다. 지금 3.9.6, 기준 3.12", text)
        self.assertIn("고치는 명령: mise install python@3.12", text)

    def test_a_missing_tool_prints_the_install_command(self):
        versions = {"python": "3.12.0", "git": None, "gh": "2.40.0", "claude": "1.0.0", "mise": "2026.1.0"}
        self.assertIn("고치는 명령: sudo apt install git", self.problems(versions=versions))
        self.assertIn("고치는 명령: brew install git", self.problems(versions=versions, os="darwin"))

    def test_wsl1_mnt_and_windows_git_print_fix_commands(self):
        text = self.problems(wsl=True, wsl_version=1, repo="/mnt/c/src/repo", git_path="/mnt/c/Program Files/Git/cmd/git.exe")
        self.assertIn("고치는 명령: wsl.exe --set-version <배포판> 2", text)
        self.assertNotIn("set-default-version", text)
        self.assertIn("고치는 명령: 저장소를 ~ 아래에 클론한다", text)
        self.assertIn("고치는 명령: sudo apt install git", text)

    def test_wsl_checks_stay_quiet_off_wsl(self):
        text = self.problems(wsl=False, repo="/mnt/c/src/repo", git_path="/mnt/c/Program Files/Git/cmd/git.exe")
        self.assertNotIn("WSL1", text)
        self.assertNotIn("/mnt/", text)
        self.assertNotIn("Windows git", text)

    def test_the_same_personal_skill_name_prints_rm_and_plugin_guidance(self):
        text = self.problems(skills_repo=["tdd"], skills_user=[{"entry": "my-tdd", "names": ["my-tdd", "tdd"]}])
        self.assertIn("개인 스킬 tdd이 저장소 사본과 같은 이름이다", text)
        self.assertIn("고치는 명령: rm -rf ~/.claude/skills/my-tdd", text)
        self.assertIn("플러그인:스킬", text)

    def test_a_prose_environment_entry_names_the_org(self):
        quiet = self.problems(org="acme", environment=["Source control: github.com/acme and all repos under it"])
        self.assertNotIn("autoMode", quiet)
        self.assertNotIn("autoMode", self.problems(org="acme", environment=["https://github.com/acme/repo"]))
        for item in ("Source control: github.com/acme-other", "Source control: notgithub.com/acme", "gitlab.com/acme"):
            text = self.problems(org="acme", environment=[item])
            self.assertIn("조직 acme이 없다", text, item)

    def test_a_symlink_loop_in_skills_does_not_crash(self):
        import baseline as b
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "skills"
            folder.mkdir()
            link = folder / "loop"
            link.symlink_to(link)
            self.assertEqual([item["entry"] for item in b.skill_entries(folder)], ["loop"])

    def test_a_missing_org_prints_json_and_does_not_write(self):
        text = self.problems(org="acme", environment=["github.com/other"])
        self.assertIn("자동으로 쓰지 않는다", text)
        self.assertIn('고치는 명령: {"autoMode": {"environment": ["github.com/acme"]}}', text)

    def test_a_missing_claude_or_mise_does_not_require_itself(self):
        missing = {"python": "3.12.0", "git": "2.39.0", "gh": "2.40.0", "claude": None, "mise": "2026.1.0"}
        text = self.problems(versions=missing, want={"claude": "2.1.0"})
        self.assertIn("고치는 명령: claude를 설치한다", text)
        self.assertNotIn("claude update", text)
        mismatch = self.problems(want={"claude": "2.1.0"})
        self.assertIn("고치는 명령: claude update", mismatch)
        no_mise = {"python": "3.12.0", "git": "2.39.0", "gh": "2.40.0", "claude": "1.0.0", "mise": None}
        mac = self.problems(versions=no_mise, os="darwin", want={"mise": "2026.11.0"})
        self.assertIn("고치는 명령: brew install mise", mac)
        self.assertNotIn("mise install mise", mac)
        linux = self.problems(versions=no_mise, os="linux")
        self.assertIn("고치는 명령: curl -fsSL https://mise.run | sh", linux)
        self.assertNotIn("mise install mise", linux)

    def test_an_untrusted_mise_toml_prints_mise_trust(self):
        text = self.problems(mise_toml="/home/u/repo/.mise.toml", mise_trusted=False)
        self.assertIn("고치는 명령: mise trust /home/u/repo/.mise.toml", text)

    def test_sandbox_on_linux_or_wsl2_requires_bubblewrap_and_socat(self):
        text = self.problems(sandbox=True, os="linux", have_bubblewrap=False, have_socat=False)
        self.assertIn("고치는 명령: sudo apt install bubblewrap", text)
        self.assertIn("고치는 명령: sudo apt install socat", text)
        quiet = self.problems(sandbox=True, os="darwin", have_bubblewrap=False, have_socat=False)
        self.assertNotIn("bubblewrap", quiet)
        wsl = self.problems(sandbox=True, os="linux", wsl=True, wsl_version=2, have_bubblewrap=True, have_socat=False)
        self.assertIn("socat", wsl)
        self.assertNotIn("bubblewrap", wsl)

    def test_a_matching_machine_passes(self):
        self.assertEqual(self.problems(), "")

    def test_an_unreadable_version_is_not_copied_into_the_command(self):
        text = self.problems(want={"python": "3.12; echo x"})
        self.assertIn("python 기준 판을 읽을 수 없다", text)
        self.assertNotIn("echo x", text)
        self.assertNotIn("mise install python@", text)

    def test_an_unsafe_skill_entry_is_not_removed(self):
        text = self.problems(skills_repo=["tdd"], skills_user=[{"entry": "../../.ssh", "names": ["tdd"]}])
        self.assertIn("고치는 명령을 만들지 못했다", text)
        self.assertNotIn("rm -rf", text)
        self.assertNotIn(".ssh", text)

    def test_a_longer_installed_version_matches_the_pin(self):
        versions = {"python": "3.12.16", "git": "2.45.1", "gh": "2.60.0", "claude": "2.1.330", "mise": "2026.11.9"}
        self.assertEqual(self.problems(versions=versions, want={"python": "3.12"}), "")

    def test_a_pinned_git_and_another_tool_print_their_own_commands(self):
        text = self.problems(want={"git": "2.45", "godot": "4.3"},
                             versions={"python": "3.12.0", "git": "2.39.0", "gh": "2.40.0", "claude": "1.0.0",
                                       "mise": "2026.1.0", "godot": "4.2.0"})
        self.assertIn("고치는 명령: mise install git@2.45", text)
        self.assertIn("고치는 명령: AGENTS.md 길잡이의 설치법으로 godot 4.3을 설치한다", text)

    def test_windows_git_version_string_on_wsl(self):
        text = self.problems(wsl=True, wsl_version=2, git_version="git version 2.40.0.windows.1")
        self.assertIn("고치는 명령: sudo apt install git", text)
        quiet = self.problems(wsl=False, git_version="git version 2.40.0.windows.1")
        self.assertNotIn("Windows git", quiet)

    def test_mise_pins_and_trust_show(self):
        import baseline as b
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        self.assertFalse(b.mise_config_trusted(f"{folder}: untrusted\n", folder))
        self.assertTrue(b.mise_config_trusted(f"{folder}: trusted\n", folder))
        self.assertFalse(b.mise_config_trusted(f"{folder}/.mise.toml: untrusted\n", folder))
        self.assertFalse(b.show_is_trusted(1, f"{folder}: trusted\n", folder))
        self.assertTrue(b.show_is_trusted(0, f"{folder}: trusted\n", folder))
        text = 'min_version = "2026.11.0"\n\n[tools]\npython = "3.12"\n'
        self.assertEqual(b.pins_from({}, text, "2026.11.9"), {"python": "3.12"})
        self.assertEqual(b.pins_from({}, text, "2026.10.0")["mise"], "2026.11.0")
        self.assertEqual(b.pins_from({"claude": "2.1.283"}, "", "2026.11.9"), {"claude": "2.1.283"})
        self.assertEqual(b.pins_from({"mise": "2026.1.0"}, text, "2026.11.9")["mise"], "2026.11.0")
        self.assertEqual(b.pins_from({"mise": "2026.12.0"}, 'min_version = "2026.11.0"\n', "2026.12.1")["mise"], "2026.12.0")
        self.assertNotIn("./probe", b.pins_from({"./probe": "1.0.0", "godot": "4.3"}, "", None))
        self.assertEqual(b.version_binary("godot"), "godot")
        self.assertEqual(b.version_binary("python"), "python3")
        self.assertIsNone(b.version_binary("./probe"))
        self.assertIsNone(b.version_binary("a/b"))
        (folder / ".claude/skills/tdd").mkdir(parents=True)
        (folder / ".claude/skills/mine").mkdir()
        self.assertEqual(b.repo_skill_names(folder), ["tdd"])

    def test_stdin_facts_print_the_fix_command(self):
        import json
        facts = {"versions": {"python": "3.9.6", "git": "2.39.0", "gh": "2.40.0", "claude": "1.0.0", "mise": "2026.1.0"},
                 "want": {"mise": "2026.11.0"}, "os": "linux", "wsl": False, "repo": "/home/u/repo",
                 "git_path": "/usr/bin/git", "skills_repo": [], "skills_user": [], "org": "acme",
                 "environment": ["github.com/acme"], "mise_toml": None, "mise_trusted": True,
                 "sandbox": False, "have_bubblewrap": True, "have_socat": True}
        result = subprocess.run([sys.executable, "-I", str(ROOT / "baseline.py"), "doctor"],
                                input=json.dumps(facts), capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("고치는 명령: mise install mise@2026.11.0", result.stderr)

    def test_a_linked_or_unreadable_mise_file_is_not_parsed(self):
        import baseline as b
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        secret = folder / "secret.toml"
        secret.write_text('min_version = "9.9.9"\n[tools]\npython = "9.8.7"\n', encoding="utf-8")
        (folder / ".mise.toml").symlink_to(secret)
        (folder / ".claude").mkdir()
        target = folder / "other.json"
        target.write_text('{"sandbox": {"enabled": true}}\n', encoding="utf-8")
        (folder / ".claude/settings.json").symlink_to(target)
        self.assertEqual(b.repo_bytes(folder, ".mise.toml"), (None, True))
        self.assertEqual(b.repo_bytes(folder, ".claude/settings.json"), (None, True))
        facts = b.gather_doctor(folder)
        self.assertTrue(facts["mise_unreadable"])
        self.assertNotIn("9.9.9", facts["want"].get("mise", ""))
        self.assertNotEqual(facts["want"].get("python"), "9.8.7")
        text = "\n".join(b.doctor_problems(facts))
        self.assertIn(".mise.toml을 읽지 못했다", text)
        self.assertNotIn("9.8.7", text)
        (folder / ".mise.toml").unlink()
        (folder / ".mise.toml").write_bytes(b"\xff")
        self.assertTrue(b.gather_doctor(folder)["mise_unreadable"])
        (folder / ".mise.toml").write_bytes(b"x" * (b.MAX_READ + 1))
        self.assertTrue(b.gather_doctor(folder)["mise_unreadable"])

    def test_oversized_stdin_is_refused(self):
        import baseline as b
        result = subprocess.run([sys.executable, "-I", str(ROOT / "baseline.py"), "doctor"],
                                input="x" * (b.MAX_READ + 1), capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("너무 크다", result.stderr)


if __name__ == "__main__":
    unittest.main()
