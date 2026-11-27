"""Layout checks for the redesigned baseline (redesign plan §7: https://github.com/minjunkim-labs/repo-baseline/blob/c3f6d569871f51b83c1405dee34db6850a0b30e3/docs/archive/redesign-2026-11.md)."""
from pathlib import Path
import json
import re
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def docs():
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", "graft/", "skills/", ".claude/skills/")):  # skill copies keep the source bytes
            continue
        yield path


FRAGMENT_MAX_BYTES = 8192


def fragment_problem(path):
    """Why a changelog.d/ file is not one short entry, or None. Checks the name first and never follows symlinks."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md", path.name):
        return "name is not YYYY-MM-DD-<slug>.md"
    if not stat.S_ISREG(path.lstat().st_mode):
        return "not a regular file (symlink or directory)"
    with open(path, "rb") as f:
        data = f.read(FRAGMENT_MAX_BYTES + 1)
    if len(data) > FRAGMENT_MAX_BYTES:
        return f"size is over {FRAGMENT_MAX_BYTES} bytes"
    lines = [l for l in data.decode("utf-8").splitlines() if l.strip()]
    if not 1 <= len(lines) <= 3 or not lines[0].startswith("- ") or any(l.startswith("- ") for l in lines[1:]):
        return "not one entry of 1-3 lines starting with '- '"
    return None


class DistributionTests(unittest.TestCase):
    def test_core_agents_file_stays_small(self):
        self.assertLessEqual(len((ROOT / "core/AGENTS.md").read_text(encoding="utf-8").splitlines()), 60)

    def test_own_v2_copies_are_one_released_install(self):
        # The root is a consumer: it moves with `upgrade <tag>`, not with each change to baseline.py or core/.
        import hashlib, re, subprocess
        copy = (ROOT / ".baseline/baseline.py").read_bytes()
        version = re.search(rb'^VERSION = "([^"]+)"', copy, re.M).group(1).decode()
        self.assertEqual(json.loads((ROOT / ".baseline/baseline.json").read_text(encoding="utf-8"))["version"], version)
        settings = (ROOT / ".claude/settings.json").read_bytes()
        pin = re.compile(rb'("--sha256",\s*")([0-9a-f]{64})"')
        self.assertEqual(pin.search(settings).group(2).decode(), hashlib.sha256(copy).hexdigest())  # else the hook allows nothing
        tag = f"v{version}"

        def at_tag(rel):
            r = subprocess.run(["git", "show", f"refs/tags/{tag}:{rel}"], cwd=ROOT, capture_output=True)
            return r.stdout if r.returncode == 0 else None

        released = at_tag("baseline.py")
        if released is None:
            # shortcut: an untagged VERSION or a clone without tags skips silently; once the root is upgraded to a tag, CI compares.
            self.skipTest(f"태그 {tag}가 없어 사본을 그 판과 비교하지 못한다(태그를 내지 않은 판이거나 태그를 받지 않은 클론)")
        self.assertEqual(copy, released, ".baseline/baseline.py")
        self.assertEqual(settings, pin.sub(b"\\g<1>" + hashlib.sha256(copy).hexdigest().encode() + b'"',
                                           at_tag("core/.claude/settings.json")), ".claude/settings.json")
        for rel in (".github/pull_request_template.md", ".claude/hooks/allow_enqueue.py"):
            self.assertEqual((ROOT / rel).read_bytes(), at_tag("core/" + rel), rel)

    def test_own_coderabbit_config_is_the_template(self):
        template = (ROOT / "github/.coderabbit.yaml").read_text(encoding="utf-8")
        self.assertEqual((ROOT / ".coderabbit.yaml").read_text(encoding="utf-8"), template)
        self.assertIn('\nlanguage: "ko-KR"\n', template)
        self.assertIn("\ninheritance: true\n", template)

    def test_changelog_fragments_are_one_short_entry(self):
        folder = ROOT / "changelog.d"  # empty right after a tag gathers it into docs/releases/, so git drops it
        problems = [f"{path.name}: {fragment_problem(path)}"
                    for path in sorted(folder.iterdir() if folder.is_dir() else []) if fragment_problem(path)]
        self.assertEqual(problems, [])

    def test_fragment_check_rejects_bad_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            good = d / "2026-11-17-ok.md"
            good.write_text("- one entry\n  continued\n", encoding="utf-8")
            cases = {"2026-11-17-ok.md": None, "Bad.md": "name", "2026-11-17-two.md": "one entry",
                     "2026-11-17-big.md": "size", "2026-11-17-link.md": "regular file",
                     "2026-11-17-dir.md": "regular file"}
            (d / "Bad.md").write_text("- x\n", encoding="utf-8")
            (d / "2026-11-17-two.md").write_text("- a\n- b\n", encoding="utf-8")
            (d / "2026-11-17-big.md").write_text("- " + "x" * FRAGMENT_MAX_BYTES, encoding="utf-8")
            (d / "2026-11-17-link.md").symlink_to(good)
            (d / "2026-11-17-dir.md").mkdir()
            for name, expected in cases.items():
                problem = fragment_problem(d / name)
                if expected is None:
                    self.assertIsNone(problem, name)
                else:
                    self.assertIn(expected, problem or "", name)

    def test_policy_stays_one_page(self):
        self.assertLessEqual(len((ROOT / "POLICY.md").read_text(encoding="utf-8")), 10000)

    def test_policy_has_no_pipeline_standing_path(self):
        text = (ROOT / "POLICY.md").read_text(encoding="utf-8")
        for word in ("repo-office", "파이프라인", "stages.json", "sync_consumers"):
            self.assertNotIn(word, text)

    def test_relative_links_resolve(self):
        missing = []
        for path in docs():
            for target in LINK.findall(path.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+:", target):
                    continue
                if not (path.parent / target).exists():
                    missing.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [])

    def test_no_model_names_in_core_or_policy(self):
        for rel in ["POLICY.md", "core/AGENTS.md", "core/REVIEW.md"]:
            text = (ROOT / rel).read_text(encoding="utf-8").lower()
            for word in ("opus", "sonnet", "composer", "grok"):
                self.assertNotIn(word, text, rel)

    def test_default_settings_do_not_require_the_gate(self):
        self.assertNotIn('"review/gate"', (ROOT / ".github/repository-settings.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
