"""baseline.py v2 tests. The seam is the command line: init a temporary repo, then run the copy in .baseline/."""
import hashlib
import json
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

    def test_check_refuses_a_symlinked_folder_on_the_way(self):
        # A linked folder above a managed file must fail even when the bytes behind it are right.
        github = self.repo / ".github"
        github.rename(self.repo / "real-github")
        github.symlink_to("real-github", target_is_directory=True)
        result = cli("check", script=self.copy)
        self.assertEqual(result.returncode, 1)
        self.assertIn("없거나 일반 파일이 아니다", result.stderr)

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


if __name__ == "__main__":
    unittest.main()
