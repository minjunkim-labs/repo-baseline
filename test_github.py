"""baseline.py github plan|apply against a fake GitHub, and the ops check.

Ported from tools/test_github_settings.py, tools/test_apply_github_settings.py and tools/test_check_ops.py
(v1); each v1 case keeps its name here.
"""
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import baseline as b

ROOT = Path(__file__).resolve().parent
# Synthetic default-setup profile: unit tests must not depend on a consumer checkout.
BASELINE = {
    "schema_version": 1, "repository": "owner/repo", "repository_id": 12, "default_branch": "main",
    "expected": {
        "repository": {
            "default_branch": "main", "visibility": "private", "allow_merge_commit": False,
            "allow_rebase_merge": False, "allow_squash_merge": True, "allow_auto_merge": False,
            "delete_branch_on_merge": True, "allow_update_branch": True,
            "squash_merge_commit_title": "PR_TITLE", "squash_merge_commit_message": "PR_BODY",
            "security_and_analysis": {
                name: {"status": "enabled"} for name in
                ("dependabot_security_updates", "secret_scanning", "secret_scanning_push_protection")
            },
        },
        "protection": {
            "required_status_checks": {"strict": True, "checks": [{"context": "CI", "app_id": 15368}]},
            "required_pull_request_reviews": {
                "required_approving_review_count": 0, "dismiss_stale_reviews": True,
                "require_code_owner_reviews": False, "require_last_push_approval": False,
            },
            **{name: {"enabled": enabled} for name, enabled in {
                "enforce_admins": True, "required_linear_history": True,
                "required_conversation_resolution": True, "allow_force_pushes": False,
                "allow_deletions": False, "lock_branch": False,
            }.items()},
        },
        "rulesets": [], "actions": {"enabled": True, "allowed_actions": "selected", "sha_pinning_required": True},
        "allowed_actions": {"github_owned_allowed": True, "verified_allowed": False, "patterns_allowed": []},
        "workflow_token": {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
        "fork_policy": {"approval_policy": "all_external_contributors"},
        "immutable_releases": {"enabled": True}, "private_vulnerability_reporting": {"enabled": True},
        "dependabot_alerts": {"enabled": True},
        "codeql": {"state": "configured"},
    },
}
PREFIX = f"repos/{BASELINE['repository']}"
PROTECTION = "branches/main/protection"
QUEUE = {
    "name": "merge-queue", "target": "branch", "enforcement": "active", "bypass_actors": [],
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [{"type": "merge_queue", "parameters": {"merge_method": "SQUASH"}}],
}


def labels():
    """Status labels as GitHub lists them."""
    return [{"id": i, "url": "x", "default": False, **label} for i, label in enumerate(copy.deepcopy(b.LABELS))]


def label_page(rel, items):
    page = int(rel.split("&page=")[1])
    return copy.deepcopy(items[(page - 1) * 100:page * 100])


def advanced(profile):
    """The project's profile as an advanced CodeQL setup, whatever setup the project uses."""
    profile = copy.deepcopy(profile)
    profile["expected"]["codeql"] = {"state": "not-configured"}
    profile["expected"].setdefault("codeql_workflow", {"path": ".github/workflows/codeql.yml", "state": "active"})
    return profile


def http_error(path, status):
    return subprocess.CalledProcessError(1, ["gh", "api", path], stderr=f"gh: error (HTTP {status})")


def project(test, profile):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    root = Path(folder.name)
    (root / ".github").mkdir()
    (root / b.GITHUB_PROFILE).write_text(json.dumps(profile))
    return root


def run(test, profile, read, write=None, apply=False, template=None):
    """github plan or apply on a checkout holding profile; template=None uses the real common values."""
    stdout, stderr = io.StringIO(), io.StringIO()
    common = b.GITHUB_SETTINGS if template is None else template
    def no_write(method, path, body):
        test.fail(f"plan wrote {method} {path}")
    with patch.object(b, "GITHUB_SETTINGS", common), redirect_stdout(stdout), redirect_stderr(stderr):
        code = b.github(project(test, profile), apply, read=read, write=write or no_write, sleep=lambda seconds: None)
    return code, stdout.getvalue(), stderr.getvalue()


class FakeGitHub:
    """Stores settings in GET shape and applies writes the way GitHub reports them back."""

    def __init__(self, profile=BASELINE, fresh=False):
        expected = copy.deepcopy(profile["expected"])
        self.metadata = {"id": profile["repository_id"], "full_name": profile["repository"], **expected["repository"]}
        self.state = {b.endpoint(name, profile["default_branch"]): value
                      for name, value in expected.items() if name not in ("repository", "dependabot_alerts")}
        self.state[PROTECTION] = self.protection_view(self.state[PROTECTION])
        self.rulesets = dict(enumerate(self.state.pop("rulesets"), start=1))
        self.alerts = expected["dependabot_alerts"]["enabled"]
        self.labels = labels()
        self.codeql_pending = 0  # reads that still report the old state after a PATCH
        self.codeql_missing = 0  # reads after writes that answer 404
        self.writes, self.fail_on = [], None
        if fresh:  # what a new repository answers before any setup
            self.metadata.update(allow_merge_commit=True, allow_rebase_merge=True, allow_auto_merge=False,
                                 delete_branch_on_merge=False, allow_update_branch=False,
                                 squash_merge_commit_title="COMMIT_OR_PR_TITLE",
                                 squash_merge_commit_message="COMMIT_MESSAGES")
            self.metadata["security_and_analysis"] = {
                key: {"status": "disabled"} for key in self.metadata["security_and_analysis"]}
            self.alerts = False
            # GitHub's default labels, wontfix among them with its own colour and text
            self.labels = [{"name": "bug", "color": "d73a4a", "description": "Something isn't working"},
                           {"name": "wontfix", "color": "FFFFFF", "description": "This will not be worked on"}]
            self.state.update({
                PROTECTION: None,
                "actions/permissions": {"enabled": True, "allowed_actions": "all", "sha_pinning_required": False},
                "actions/permissions/workflow": {"default_workflow_permissions": "write",
                                                 "can_approve_pull_request_reviews": True},
                "actions/permissions/fork-pr-contributor-approval": {"approval_policy": "first_time_contributors"},
                "immutable-releases": {"enabled": False, "enforced_by_owner": False},
                "private-vulnerability-reporting": {"enabled": False},
                "code-scanning/default-setup": {"state": "not-configured"},
            })

    @staticmethod
    def protection_view(expected):
        view = copy.deepcopy(expected)
        view.update({key: {"enabled": False} for key in b.UNMANAGED_PROTECTION})
        view["restrictions"] = None
        return view

    def read(self, path):
        rel = path[len(PREFIX):].lstrip("/") if path.startswith(PREFIX) else path
        if rel == "":
            return copy.deepcopy(self.metadata)
        if rel.startswith("labels?"):
            return label_page(rel, self.labels)
        if rel == "vulnerability-alerts":
            if self.alerts:
                return None
            raise http_error(path, 404)
        if rel == "actions/permissions/selected-actions" and self.state["actions/permissions"]["allowed_actions"] != "selected":
            raise http_error(path, 409)
        if rel == "code-scanning/default-setup" and self.codeql_missing and self.writes:
            self.codeql_missing -= 1
            raise http_error(path, 404)
        if rel == "code-scanning/default-setup" and self.codeql_pending:
            self.codeql_pending -= 1
            return {"state": "not-configured"}
        if rel == "rulesets?includes_parents=false":
            return [{"id": key, "name": value["name"], "source_type": "Repository"} for key, value in self.rulesets.items()]
        if rel.startswith("rulesets/"):
            ruleset = self.rulesets[int(rel.split("/")[1])]
            return {"id": int(rel.split("/")[1]), "node_id": "RRS_x", "source_type": "Repository",
                    "current_user_can_bypass": "never", **copy.deepcopy(ruleset)}
        if self.state.get(rel) is None:
            raise http_error(path, 404)
        return copy.deepcopy(self.state[rel])

    def write(self, method, path, body):
        rel = path[len(PREFIX):].lstrip("/")
        if rel == self.fail_on:
            raise http_error(path, 403)
        self.writes.append((method, rel))
        on = method == "PUT"
        if rel == "":
            body = copy.deepcopy(body)
            security = body.pop("security_and_analysis", {})
            self.metadata.update(body)
            self.metadata["security_and_analysis"].update(security)
        elif rel == "labels":
            self.labels.append(copy.deepcopy(body))
        elif rel.startswith("labels/"):
            label, = [label for label in self.labels if b.quote(label["name"], safe="") == rel.split("/", 1)[1]]
            label.update(name=body["new_name"], color=body["color"], description=body["description"])
        elif rel == "automated-security-fixes":
            self.metadata["security_and_analysis"]["dependabot_security_updates"] = {
                "status": "enabled" if on else "disabled"}
        elif rel == "vulnerability-alerts":
            self.alerts = on
        elif rel == "immutable-releases":
            self.state[rel] = {"enabled": on, "enforced_by_owner": False}
        elif rel == "private-vulnerability-reporting":
            self.state[rel] = {"enabled": on}
        elif rel == "code-scanning/default-setup":
            self.state[rel] = {"state": body["state"], "languages": ["python"]}
        elif rel == "rulesets":
            self.rulesets[max(self.rulesets, default=0) + 1] = copy.deepcopy(body)
        elif rel.startswith("rulesets/"):
            self.rulesets[int(rel.split("/")[1])] = copy.deepcopy(body)
        elif rel == PROTECTION:
            self.state[rel] = self.protection_view({
                "required_status_checks": dict(body["required_status_checks"]),
                "enforce_admins": {"enabled": body["enforce_admins"]},
                "required_pull_request_reviews": dict(body["required_pull_request_reviews"]),
                **{flag: {"enabled": body[flag]} for flag in b.PROTECTION_FLAGS},
            })
        else:
            self.state[rel] = copy.deepcopy(body)


class SettingsAuditTests(unittest.TestCase):
    """v1 tools/test_github_settings.py: the read-only comparison (now github plan and the audit after apply)."""

    def test_missing_security_field_is_drift(self):
        self.assertEqual(b.differences({"secret_scanning": {"status": "enabled"}}, {}), ["secret_scanning"])

    def test_checks_ignore_order_but_reject_extra_or_duplicate_entries(self):
        expected = [{"context": "CI", "app_id": 15368}, {"context": "policy", "app_id": 15368}]
        self.assertEqual(b.differences(expected, list(reversed(expected)), "checks"), [])
        self.assertEqual(b.differences(expected, expected + [expected[0]], "checks"), ["checks"])

    def test_wrong_check_app_and_boolean_types_are_not_accepted(self):
        self.assertEqual(b.differences([{"context": "CI", "app_id": 15368}],
                                       [{"context": "CI", "app_id": 1}], "checks"), ["checks"])
        self.assertEqual(b.differences(True, 1, "enabled"), ["enabled"])

    def test_default_setup_profile_has_no_workflow_controls(self):
        profile = advanced(BASELINE)
        profile["expected"]["codeql"] = {"state": "configured"}
        with self.assertRaisesRegex(ValueError, "필수 항목"):
            b.validate_profile(profile)
        for name in b.ADVANCED_CODEQL:
            del profile["expected"][name]
        b.validate_profile(profile)

    def test_retired_workflow_pin_is_refused_by_name(self):
        profile = advanced(BASELINE)
        profile["expected"]["codeql_main_source"] = {"path": ".github/workflows/codeql.yml", "type": "file", "sha": "0" * 40}
        with self.assertRaisesRegex(ValueError, "codeql_main_source"):
            b.validate_profile(profile)

    def profile(self):
        return copy.deepcopy(BASELINE)

    def reader(self, path):
        profile = self.profile()
        if path == "repos/owner/repo":
            return {"id": 12, "full_name": "owner/repo", **profile["expected"]["repository"]}
        if path.endswith("vulnerability-alerts"):
            return None
        if path.startswith("repos/owner/repo/labels?"):
            return label_page(path, labels())
        endpoints = {
            "branches/main/protection": "protection", "rulesets?includes_parents=false": "rulesets",
            "actions/permissions": "actions", "actions/permissions/selected-actions": "allowed_actions",
            "actions/permissions/workflow": "workflow_token",
            "actions/permissions/fork-pr-contributor-approval": "fork_policy",
            "immutable-releases": "immutable_releases", "code-scanning/default-setup": "codeql",
            "private-vulnerability-reporting": "private_vulnerability_reporting",
            "actions/workflows/codeql.yml": "codeql_workflow",
        }
        return copy.deepcopy(profile["expected"][endpoints[path[len("repos/owner/repo/"):]]])

    def test_live_reader_receives_only_get_paths_and_detects_drift(self):
        calls = []
        def read(path):
            calls.append(path)
            value = self.reader(path)
            if len(calls) == 1:
                value["allow_merge_commit"] = True
            return value
        self.assertEqual(b.audit(self.profile(), read), ["repository.allow_merge_commit"])
        self.assertEqual(len(calls), len(self.profile()["expected"]) + 1)  # metadata, each other control, labels
        self.assertTrue(all(path.startswith("repos/owner/repo") for path in calls))

    def test_rulesets_compare_the_rule_not_ids_or_timestamps(self):
        profile = self.profile()
        profile["expected"]["rulesets"] = [QUEUE]
        live = {"id": 7, "node_id": "RRS_x", "created_at": "2026-11-16T00:00:00Z", **copy.deepcopy(QUEUE)}
        def read(path):
            if path.endswith("/rulesets?includes_parents=false"):
                return [{"id": 7, "name": "merge-queue"}]
            if path.endswith("/rulesets/7"):
                return copy.deepcopy(live)
            return self.reader(path)
        self.assertEqual(b.audit(profile, read), [])
        live["rules"][0]["parameters"]["new_github_field"] = 3  # GitHub added a parameter: not drift
        self.assertEqual(b.audit(profile, read), [])
        live["rules"][0]["parameters"]["merge_method"] = "MERGE"
        self.assertEqual(b.audit(profile, read), ["rulesets"])
        del live["rules"][0]["parameters"]["merge_method"]  # a listed parameter that is gone is drift
        self.assertEqual(b.audit(profile, read), ["rulesets"])
        live["rules"][0]["parameters"]["merge_method"] = "SQUASH"
        live["rules"].append({"type": "deletion"})  # an extra rule is drift
        self.assertEqual(b.audit(profile, read), ["rulesets"])
        self.assertEqual(b.known_parameters([{"name": "q", "rules": []}], [{"name": "q", "rules": None}]),
                         [{"name": "q", "rules": None}])  # null rules are not read as an empty list

    def test_rulesets_need_every_field_and_unique_names(self):
        profile = self.profile()
        profile["expected"]["rulesets"] = [{"name": "merge-queue"}]
        with self.assertRaisesRegex(ValueError, "ruleset 목록"):
            b.validate_profile(profile)
        queue = dict({key: [] for key in b.RULESET_FIELDS}, name="q")
        profile["expected"]["rulesets"] = [queue, queue]
        with self.assertRaisesRegex(ValueError, "겹친다"):
            b.validate_profile(profile)

    def test_wrong_repository_and_request_paths_stop_before_extra_reads(self):
        for value in ["owner/repo?bad", "../repo", "https://github.com/owner/repo"]:
            profile = self.profile()
            profile["repository"] = value
            with self.assertRaises(ValueError):
                b.audit(profile, lambda _: self.fail("Invalid repository reached the API"))
        with self.assertRaises(ValueError):
            b.audit(self.profile(), lambda _: {"id": 13, "full_name": "owner/repo"})

    def test_permission_failure_is_unverified_not_disabled_or_pass(self):
        def read(path):
            if path.endswith("vulnerability-alerts"):
                raise PermissionError("no access")
            return self.reader(path)
        with self.assertRaises(PermissionError):
            b.audit(self.profile(), read)
        self.assertEqual(run(self, self.profile(), read)[0], 2)

    def test_unknown_endpoint_is_rejected(self):
        profile = self.profile()
        profile["expected"]["secrets"] = {}
        with self.assertRaises(ValueError):
            b.audit(profile, self.reader)

    def test_incomplete_baselines_are_unverified_before_network_access(self):
        for expected in [{}, [], None]:
            profile = self.profile()
            profile["expected"] = expected
            code, out, err = run(self, profile, lambda _: self.fail("Incomplete baseline reached network"))
            self.assertEqual((code, out), (2, ""))
            self.assertIn("실패", err)
        # The common values fill what a project file leaves out; a control missing from both stops the run.
        for control in self.profile()["expected"]:
            profile = self.profile()
            del profile["expected"][control]
            self.assertEqual(run(self, profile, lambda _: self.fail("Missing control reached network"), template={})[0], 2)
        profile = self.profile()
        del profile["expected"]["protection"]["enforce_admins"]["enabled"]
        self.assertEqual(run(self, profile, lambda _: self.fail("Missing protection reached network"), template={})[0], 2)

    def test_invalid_data_and_lookup_errors_are_unverified(self):
        profile = self.profile()
        profile["default_branch"] = None
        self.assertEqual(run(self, profile, self.reader)[0], 2)
        self.assertEqual(run(self, self.profile(), lambda _: None)[0], 2)
        def read(path):
            raise PermissionError("no access")
        code, out, err = run(self, self.profile(), read)
        self.assertEqual(code, 2)
        self.assertNotIn("차이", out)
        self.assertIn("실패", err)

    def test_extra_non_protection_field_reports_drift_without_schema_crash(self):
        profile = self.profile()
        profile["expected"]["repository"]["required_status_checks"] = False
        code, out, err = run(self, profile, self.reader)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("repository.required_status_checks", out)

    def exception(self, status="unsupported"):
        return {"status": status, "reason": "Private repository plan lacks this feature",
                "evidence": "GitHub documentation and repository setup review"}

    def test_declared_unsupported_control_is_limited_and_other_drift_still_fails(self):
        profile = self.profile()
        del profile["expected"]["protection"]
        profile["exceptions"] = {"protection": self.exception()}
        def read(path):
            self.assertFalse(path.endswith("/protection"), "Unavailable control must not be queried")
            return self.reader(path)
        code, out, err = run(self, profile, read)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("예외(unsupported): protection", out)
        self.assertIn("선언한 예외는 확인하지 않았다", out)
        profile["expected"]["actions"]["enabled"] = False
        self.assertEqual(run(self, profile, read)[0], 1)

    def test_nested_unavailable_fields_and_codeql_language_exception(self):
        profile = advanced(self.profile())
        for name in ("codeql", *b.ADVANCED_CODEQL):
            del profile["expected"][name]
        del profile["expected"]["repository"]["security_and_analysis"]["secret_scanning"]
        del profile["expected"]["actions"]["sha_pinning_required"]
        profile["exceptions"] = {
            "codeql": self.exception("not_applicable"),
            "repository.security_and_analysis.secret_scanning.status": self.exception(),
            "actions.sha_pinning_required": self.exception(),
        }
        def read(path):
            self.assertNotIn("code-scanning", path)
            self.assertNotIn("codeql.yml", path)
            result = self.reader(path)
            if path == "repos/owner/repo":
                del result["security_and_analysis"]["secret_scanning"]
            elif path.endswith("actions/permissions"):
                del result["sha_pinning_required"]
            return result
        code, out, err = run(self, profile, read)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("예외(not_applicable): codeql", out)

    def test_invalid_exceptions_cannot_erase_required_controls(self):
        cases = [None, {"protection": {}}, {"secrets": self.exception()},
                 {"repository.allow_squash_merge": self.exception()},
                 {"protection": self.exception("unverified")},
                 {"protection": dict(self.exception(), evidence=" ")},
                 {"protection": self.exception(), "actions": self.exception(),
                  "actions.sha_pinning_required": self.exception()}]
        for exceptions in cases:
            profile = self.profile()
            del profile["expected"]["protection"]
            profile["exceptions"] = exceptions
            with self.subTest(exceptions=exceptions):
                self.assertEqual(run(self, profile, lambda _: self.fail("Invalid exception reached API"))[0], 2)
        profile = self.profile()
        profile["exceptions"] = {"protection": self.exception()}
        self.assertEqual(run(self, profile, lambda _: self.fail("Conflicting expectation reached API"))[0], 2)

    def test_403_and_404_do_not_automatically_become_availability_exceptions(self):
        for code in (403, 404):
            def read(path):
                if path.endswith("/protection"):
                    raise http_error(path, code)
                return self.reader(path)
            status, out, err = run(self, self.profile(), read)
            if code == 403:
                self.assertEqual((status, out.count("차이")), (2, 0))
                self.assertIn("실패", err)
            else:  # 404 is an unprotected branch: every protection field differs, nothing passes
                self.assertEqual(status, 1)
                self.assertIn('차이: protection.enforce_admins.enabled: "<not set>" -> true', out)
            self.assertNotIn("차이 없음", out)

    def own_values(self):
        """A project file with only the values that differ per repository."""
        return {
            "repository": "owner/repo", "repository_id": 12,
            "expected": {
                "protection": {"required_status_checks": {"checks": [{"context": "ci", "app_id": 15368}]}},
                "allowed_actions": {"patterns_allowed": []},
            },
        }

    def test_project_file_with_own_values_takes_common_values_from_the_template(self):
        profile = b.merged(self.own_values())
        b.validate_profile(profile)
        b.validate_target(profile)
        self.assertIs(profile["expected"]["protection"]["required_status_checks"]["strict"], False)
        self.assertEqual(profile["expected"]["rulesets"], b.GITHUB_SETTINGS["expected"]["rulesets"])
        self.assertEqual(profile["expected"]["protection"]["required_status_checks"]["checks"],
                         [{"context": "ci", "app_id": 15368}])
        server = copy.deepcopy(profile["expected"])
        def read(path):
            rel = path[len("repos/owner/repo"):].lstrip("/")
            if rel.startswith("labels?"):
                return label_page(rel, labels())
            views = {"": {"id": 12, "full_name": "owner/repo", **server["repository"]},
                     "rulesets?includes_parents=false": [{"id": 1}], "rulesets/1": server["rulesets"][0],
                     "branches/main/protection": server["protection"], "actions/permissions": server["actions"],
                     "actions/permissions/selected-actions": server["allowed_actions"],
                     "actions/permissions/workflow": server["workflow_token"],
                     "actions/permissions/fork-pr-contributor-approval": server["fork_policy"],
                     "immutable-releases": server["immutable_releases"],
                     "private-vulnerability-reporting": server["private_vulnerability_reporting"],
                     "code-scanning/default-setup": server["codeql"], "vulnerability-alerts": None}
            return copy.deepcopy(views[rel])
        code, out, err = run(self, self.own_values(), read)
        self.assertEqual((code, err), (0, ""))
        self.assertIn(f"공통값은 baseline.py {b.VERSION}", out)
        server["protection"]["required_status_checks"]["strict"] = True
        code, out, _ = run(self, self.own_values(), read)
        self.assertEqual(code, 1)
        self.assertIn("protection.required_status_checks.strict", out)

    def test_project_values_win_and_full_copies_merge_to_themselves(self):
        self.assertEqual(b.merged(self.profile()), self.profile())
        values = self.own_values()
        values["expected"]["protection"]["required_status_checks"]["strict"] = True
        values["expected"]["rulesets"] = []
        profile = b.merged(values)
        self.assertIs(profile["expected"]["protection"]["required_status_checks"]["strict"], True)
        self.assertEqual(profile["expected"]["rulesets"], [])
        self.assertIs(profile["expected"]["protection"]["enforce_admins"]["enabled"], True)

    def test_exceptions_drop_template_values_and_unfilled_values_stop_before_reads(self):
        values = self.own_values()
        values["exceptions"] = {"codeql": self.exception("not_applicable"),
                                "repository.security_and_analysis.secret_scanning.status": self.exception()}
        profile = b.merged(values)
        b.validate_profile(profile)
        self.assertNotIn("codeql", profile["expected"])
        self.assertNotIn("secret_scanning", profile["expected"]["repository"]["security_and_analysis"])
        for key in ("repository", "expected"):
            values = self.own_values()
            if key == "repository":
                del values["repository"]
            else:
                del values["expected"]["allowed_actions"]
            with self.assertRaisesRegex(ValueError, "빈칸"):
                b.merged(values)
            code, out, err = run(self, values, lambda _: self.fail("Unfilled value reached network"))
            self.assertEqual((code, out), (2, ""))
            self.assertIn("실패", err)

    def test_main_pass_and_drift_have_distinct_exit_codes(self):
        code, out, err = run(self, self.profile(), self.reader)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("차이 없음: owner/repo", out)
        profile = self.profile()
        profile["expected"]["protection"]["enforce_admins"]["enabled"] = False
        code, out, err = run(self, profile, self.reader)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("protection.enforce_admins.enabled", out)


class ApplyTests(unittest.TestCase):
    """v1 tools/test_apply_github_settings.py, plus the status labels."""

    def run_tool(self, server, profile=BASELINE, apply=False):
        return run(self, profile, server.read, server.write, apply)

    def test_matching_settings_need_no_writes(self):
        server = FakeGitHub()
        code, out, _ = self.run_tool(server, apply=True)
        self.assertEqual((code, server.writes), (0, []))
        self.assertIn("통과:", out)

    def test_plan_shows_current_and_baseline_values_and_only_reads(self):
        server = FakeGitHub(fresh=True)
        commands = []
        def gh(command, **kwargs):
            commands.append(command)
            data = server.read(command[4])  # CalledProcessError, as check=True raises it
            return subprocess.CompletedProcess(command, 0, "" if data is None else json.dumps(data), "")
        stdout = io.StringIO()
        with patch.object(b.subprocess, "run", gh), redirect_stdout(stdout):
            code = b.github(project(self, BASELINE), False)
        out = stdout.getvalue()
        self.assertEqual(code, 1)
        self.assertEqual({command[3] for command in commands}, {"GET"})
        self.assertIn("차이: repository.allow_merge_commit: true -> false", out)
        self.assertIn('차이: protection.enforce_admins.enabled: "<not set>" -> true', out)
        self.assertIn("계획: PUT repos/owner/repo/branches/main/protection", out)
        self.assertIn("계획: POST repos/owner/repo/labels", out)
        self.assertIn("아무것도 쓰지 않았다", out)

    def test_protection_request_body(self):
        expected = copy.deepcopy(BASELINE["expected"]["protection"])
        expected["required_pull_request_reviews"]["dismissal_restrictions"] = {"users": [{"login": "lead"}]}
        [(method, path, body)] = b.writes_for("protection", expected, PREFIX, "main")
        self.assertEqual((method, path), ("PUT", f"{PREFIX}/{PROTECTION}"))
        self.assertEqual(body, {
            "required_status_checks": {"strict": True, "checks": [{"context": "CI", "app_id": 15368}]},
            "enforce_admins": True,
            "required_pull_request_reviews": {"required_approving_review_count": 0, "dismiss_stale_reviews": True,
                                              "require_code_owner_reviews": False, "require_last_push_approval": False},
            "restrictions": None, "required_linear_history": True, "allow_force_pushes": False,
            "allow_deletions": False, "required_conversation_resolution": True, "lock_branch": False,
        })

    def test_fresh_repository_reaches_baseline_and_audit_passes(self):
        # #183's done criterion: after apply on a new repository, plan shows no difference and the 5 labels exist.
        server = FakeGitHub(fresh=True)
        server.codeql_pending = 3  # default setup turns on in the background
        server.codeql_missing = 1  # and may briefly answer 404 first
        code, out, err = self.run_tool(server, apply=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("통과: owner/repo 설정과 라벨이 기준과 같다", out)
        self.assertEqual(b.audit(BASELINE, server.read), [])
        order = [rel for _, rel in server.writes]
        self.assertLess(order.index("vulnerability-alerts"), order.index("automated-security-fixes"))
        self.assertLess(order.index("actions/permissions"), order.index("actions/permissions/selected-actions"))
        self.assertEqual(b.settings_plan(BASELINE, server.read), ([], []))  # a second run changes nothing
        code, out, _ = self.run_tool(server)
        self.assertEqual(code, 0, out)
        self.assertIn("차이 없음: owner/repo", out)
        # Written out, not b.LABELS: a label dropped from the constant must fail here.
        self.assertEqual({label["name"] for label in server.labels} - {"bug"},
                         {"needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix"})
        self.assertIn({"name": "bug", "color": "d73a4a", "description": "Something isn't working"}, server.labels)

    def test_labels_are_created_or_fixed_and_never_deleted(self):
        server = FakeGitHub()
        server.labels = [dict(label) for label in labels() if label["name"] != "needs-info"]
        server.labels[0]["color"] = "000000"
        server.labels[1]["name"] = "NEEDS-TRIAGE" if server.labels[1]["name"] == "needs-triage" else server.labels[1]["name"]
        server.labels[-1]["name"] = "Wontfix"
        server.labels.append({"name": "project-own", "color": "123456", "description": None})
        code, out, err = self.run_tool(server, apply=True)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(server.writes), sorted([
            ("PATCH", "labels/needs-triage"), ("POST", "labels"), ("PATCH", "labels/Wontfix")]))
        self.assertEqual(sorted(label["name"] for label in server.labels),
                         sorted([label["name"] for label in b.LABELS] + ["project-own"]))
        # GitHub answers colours in either case; that alone is not a difference.
        server.labels[0]["color"] = server.labels[0]["color"].upper()
        self.assertEqual(b.label_changes(server.read, PREFIX), [])

    def test_labels_are_read_across_pages(self):
        server = FakeGitHub()
        server.labels = [{"name": f"label-{i}", "color": "000000", "description": ""} for i in range(150)] + labels()
        self.assertEqual(b.label_changes(server.read, PREFIX), [])

    def test_switching_features_off_uses_delete(self):
        profile = copy.deepcopy(BASELINE)
        profile["expected"]["immutable_releases"]["enabled"] = False
        profile["expected"]["private_vulnerability_reporting"]["enabled"] = False
        profile["expected"]["repository"]["security_and_analysis"]["dependabot_security_updates"]["status"] = "disabled"
        server = FakeGitHub()
        self.assertEqual(self.run_tool(server, profile, apply=True)[0], 0)
        self.assertEqual(sorted(server.writes), sorted([
            ("PATCH", ""), ("DELETE", "automated-security-fixes"),
            ("DELETE", "immutable-releases"), ("DELETE", "private-vulnerability-reporting")]))

    def test_visibility_and_extra_rulesets_are_left_to_a_person(self):
        server = FakeGitHub()
        server.metadata["visibility"] = "public"
        server.rulesets[1] = dict(copy.deepcopy(QUEUE), name="team rule")
        code, out, _ = self.run_tool(server, apply=True)
        self.assertEqual((code, server.writes), (1, []))
        self.assertIn("사람이 할 일: repository.visibility", out)
        self.assertIn("사람이 할 일: rulesets.team rule은 기준에 없다", out)

    def test_missing_ruleset_is_created_and_a_changed_one_replaced(self):
        profile = copy.deepcopy(BASELINE)
        profile["expected"]["rulesets"] = [QUEUE]
        server = FakeGitHub()
        code, out, _ = self.run_tool(server, profile, apply=True)
        self.assertEqual((code, server.writes), (0, [("POST", "rulesets")]))
        self.assertIn("통과", out)
        server.rulesets[1]["rules"][0]["parameters"]["new_github_field"] = 3  # GitHub added a parameter
        server.writes.clear()
        self.assertEqual(self.run_tool(server, profile, apply=True)[0], 0)
        self.assertEqual(server.writes, [])  # not drift, so nothing is rewritten
        server.rulesets[1]["rules"][0]["parameters"]["merge_method"] = "MERGE"
        code, out, _ = self.run_tool(server, profile, apply=True)
        self.assertEqual((code, server.writes), (0, [("PUT", "rulesets/1")]))

    def test_rulesets_sharing_a_name_are_left_to_a_person(self):
        profile = copy.deepcopy(BASELINE)
        profile["expected"]["rulesets"] = [QUEUE]
        server = FakeGitHub(profile)
        server.rulesets[2] = copy.deepcopy(QUEUE)
        server.rulesets[2]["enforcement"] = "disabled"
        code, out, _ = self.run_tool(server, profile, apply=True)
        self.assertEqual((code, server.writes), (1, []))
        self.assertIn("이 이름의 ruleset이 여럿이다", out)

    def test_protection_with_unmanaged_settings_is_left_to_a_person(self):
        server = FakeGitHub()
        server.state[PROTECTION]["required_signatures"] = {"enabled": True}
        server.state[PROTECTION]["required_status_checks"]["checks"] = [{"context": "old", "app_id": 15368}]
        code, out, _ = self.run_tool(server, apply=True)
        self.assertEqual(code, 1)
        self.assertNotIn(("PUT", PROTECTION), server.writes)
        self.assertIn("사람이 할 일: protection.required_signatures가 켜져 있다", out)

    def test_review_bypass_and_dismissal_lists_are_left_to_a_person(self):
        for key, value in (("bypass_pull_request_allowances", {"users": [{"login": "bot"}], "teams": [], "apps": []}),
                           ("dismissal_restrictions", {"users": [{"login": "lead"}], "teams": []})):
            with self.subTest(key):
                server = FakeGitHub()
                server.state[PROTECTION]["required_pull_request_reviews"][key] = value
                server.state[PROTECTION]["required_linear_history"] = {"enabled": False}
                code, out, _ = self.run_tool(server, apply=True)
                self.assertNotIn(("PUT", PROTECTION), server.writes)
                self.assertIn(f"사람이 할 일: protection.required_pull_request_reviews.{key}가 켜져 있다", out)

    def test_unaudited_fields_are_reported_when_the_control_is_not_set_yet(self):
        profile = copy.deepcopy(BASELINE)
        profile["expected"]["protection"]["required_pull_request_reviews"]["dismissal_restrictions"] = {"users": []}
        server = FakeGitHub(fresh=True)
        code, out, _ = self.run_tool(server, profile)
        self.assertIn("사람이 할 일: protection.required_pull_request_reviews.dismissal_restrictions", out)
        self.assertIn('차이: protection.required_linear_history.enabled: "<not set>" -> true', out)
        self.assertIn("계획: PUT repos/owner/repo/branches/main/protection", out)

    def test_advanced_codeql_keeps_default_setup_until_the_workflow_is_active(self):
        profile = advanced(BASELINE)
        server = FakeGitHub()
        server.state["code-scanning/default-setup"] = {"state": "configured"}
        code, out, _ = self.run_tool(server, profile, apply=True)
        self.assertNotEqual(code, 0)  # the audit cannot verify a workflow that does not exist yet
        self.assertNotIn(("PATCH", "code-scanning/default-setup"), server.writes)
        self.assertIn("사람이 할 일: codeql.state: 고급 설정 workflow가 돌 때까지", out)
        server.state["actions/workflows/codeql.yml"] = {"path": ".github/workflows/codeql.yml", "state": "active"}
        disabled = copy.deepcopy(profile)  # a baseline that records a disabled workflow must not turn scanning off
        disabled["expected"]["codeql_workflow"]["state"] = "disabled_manually"
        server.state["actions/workflows/codeql.yml"]["state"] = "disabled_manually"
        self.run_tool(server, disabled, apply=True)
        self.assertNotIn(("PATCH", "code-scanning/default-setup"), server.writes)
        server.state["actions/workflows/codeql.yml"]["state"] = "active"
        self.run_tool(server, profile, apply=True)
        self.assertIn(("PATCH", "code-scanning/default-setup"), server.writes)

    def test_retired_workflow_pin_stops_before_any_request(self):
        profile = advanced(BASELINE)
        profile["expected"]["codeql_main_source"] = {"path": ".github/workflows/codeql.yml", "type": "file", "sha": "0" * 40}
        server = FakeGitHub()
        reads = []
        server_read = server.read
        server.read = lambda path: reads.append(path) or server_read(path)
        code, _, err = self.run_tool(server, profile, apply=True)
        self.assertEqual((code, reads, server.writes), (2, [], []))
        self.assertIn("codeql_main_source", err)

    def test_fields_the_auditor_does_not_require_are_not_written(self):
        profile = copy.deepcopy(BASELINE)
        profile["expected"]["repository"]["has_wiki"] = False
        profile["expected"]["workflow_token"]["extra"] = True
        server = FakeGitHub()
        server.metadata["has_wiki"] = True
        server.state["actions/permissions/workflow"]["default_workflow_permissions"] = "write"
        code, out, _ = self.run_tool(server, profile, apply=True)
        self.assertIn("사람이 할 일: repository.has_wiki가 다르다", out)
        self.assertNotIn(("PATCH", ""), server.writes)
        self.assertEqual(server.state["actions/permissions/workflow"],
                         {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False})

    def test_a_write_with_unknown_outcome_is_reported(self):
        server = FakeGitHub(fresh=True)
        def timeout(method, path, body):
            raise subprocess.TimeoutExpired(["gh"], 60, stderr=b"timed out")
        server.write = timeout
        code, _, err = self.run_tool(server, apply=True)
        self.assertEqual(code, 2)
        self.assertIn("실패: timed out", err)
        self.assertIn("결과를 모른다: PUT repos/owner/repo/vulnerability-alerts", err)

    def test_unavailable_vulnerability_reporting_stops_before_any_write(self):
        server = FakeGitHub(fresh=True)
        server.state["private-vulnerability-reporting"] = None  # a private repository answers 404
        code, _, err = self.run_tool(server, apply=True)
        self.assertEqual((code, server.writes), (2, []), err)
        self.assertIn("private-vulnerability-reporting가 404다", err)

    def test_bad_profiles_and_read_errors_write_nothing(self):
        cases = {
            "identity": lambda p: p.update(repository_id=99),
            "schema": lambda p: p.update(schema_version=99),
            "branch path": lambda p: p.update(default_branch="x/../../other/repo/branches/main"),
            "branch pair": lambda p: p.update(default_branch="dev"),
            "placeholder": lambda p: p["expected"]["protection"]["required_status_checks"]["checks"][0].update(
                context="REPLACE: a required CI job name"),
        }
        for name, change in cases.items():
            with self.subTest(name):
                profile = copy.deepcopy(BASELINE)
                change(profile)
                server = FakeGitHub(fresh=True)
                code, _, err = self.run_tool(server, profile, apply=True)
                self.assertEqual((code, server.writes), (2, []), err)
        server = FakeGitHub(fresh=True)
        server.metadata["default_branch"] = "trunk"
        self.assertEqual(self.run_tool(server, apply=True)[0], 2)
        server = FakeGitHub(fresh=True)
        allowed = server.read
        def forbidden(path):
            if path.endswith("actions/permissions"):
                raise http_error(path, 403)
            return allowed(path)
        server.read = forbidden
        self.assertEqual(self.run_tool(server, apply=True)[0], 2)
        self.assertEqual(server.writes, [])

    def test_failed_write_stops_and_lists_what_was_written(self):
        server = FakeGitHub(fresh=True)
        server.fail_on = PROTECTION
        code, _, err = self.run_tool(server, apply=True)
        self.assertEqual(code, 2)
        self.assertIn("이미 썼다: PUT repos/owner/repo/vulnerability-alerts", err)
        self.assertNotIn("actions/permissions", [rel for _, rel in server.writes])

    def test_declared_exceptions_are_never_written(self):
        profile = copy.deepcopy(BASELINE)
        del profile["expected"]["immutable_releases"]
        del profile["expected"]["repository"]["security_and_analysis"]["secret_scanning"]["status"]
        del profile["expected"]["repository"]["security_and_analysis"]["dependabot_security_updates"]["status"]
        evidence = {"status": "unsupported", "reason": "test", "evidence": "test"}
        profile["exceptions"] = {path: evidence for path in (
            "immutable_releases", "repository.security_and_analysis.secret_scanning.status",
            "repository.security_and_analysis.dependabot_security_updates.status")}
        server = FakeGitHub(fresh=True)
        code, out, err = self.run_tool(server, profile, apply=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("선언한 예외는 확인하지 않았다", out)
        self.assertIn("예외(unsupported): immutable_releases", out)
        written = [rel for _, rel in server.writes]
        self.assertNotIn("immutable-releases", written)
        self.assertNotIn("automated-security-fixes", written)
        self.assertEqual(server.metadata["security_and_analysis"]["secret_scanning"], {"status": "disabled"})

    def test_reads_the_same_paths_as_the_checker(self):
        server, paths = FakeGitHub(), {"audit": set(), "plan": set()}
        def recorder(key):
            def read(path):
                paths[key].add(path)
                return server.read(path)
            return read
        b.audit(BASELINE, recorder("audit"))
        b.settings_plan(BASELINE, recorder("plan"))
        self.assertEqual(paths["plan"], paths["audit"])

    def test_profile_must_be_a_regular_file_in_the_project(self):
        root = project(self, BASELINE)
        outside = root.parent / f"{root.name}-outside.json"
        outside.write_text(json.dumps(BASELINE))
        self.addCleanup(outside.unlink)
        (root / b.GITHUB_PROFILE).unlink()
        (root / b.GITHUB_PROFILE).symlink_to(outside)
        with self.assertRaises(OSError):
            b.github_load(root)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(b.github(root, True, read=lambda _: self.fail("read"), write=None), 2)

    def test_template_and_own_profile_share_the_policy_values(self):
        # Until v1 is deleted, its template and the v2 common values are the same values.
        template = json.loads((ROOT / "templates/github/repository-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(b.GITHUB_SETTINGS, template)
        with self.assertRaisesRegex(ValueError, "빈칸"):
            b.github_load(project(self, template))
        placeholder = copy.deepcopy(BASELINE)
        placeholder["expected"]["protection"]["required_status_checks"]["checks"].append(
            {"context": "ci", "app_id": "REPLACE:<APP_ID>"})
        with self.assertRaisesRegex(ValueError, "빈칸"):
            b.github_load(project(self, placeholder))
        # This repository's own file keeps only per-project values; every policy value is common.
        own = json.loads((ROOT / b.GITHUB_PROFILE).read_text(encoding="utf-8"))
        self.assertEqual(sorted(own), ["expected", "repository", "repository_id"])
        self.assertEqual(own["expected"], {
            "protection": {"required_status_checks": {"checks": [{"context": "ci", "app_id": 15368}]}},
            "allowed_actions": {"patterns_allowed": []}})
        profile = b.github_load(ROOT)
        self.assertIs(profile["expected"]["protection"]["required_status_checks"]["strict"], False)
        for merged in (profile, template):  # identity, verified checks and third-party actions are per project
            del merged["expected"]["protection"]["required_status_checks"]["checks"]
            del merged["expected"]["allowed_actions"]["patterns_allowed"]
        self.assertEqual(profile["expected"], template["expected"])

    def test_project_file_with_own_values_only_is_planned_against_the_template(self):
        values = {"repository": BASELINE["repository"], "repository_id": BASELINE["repository_id"],
                  "expected": {"protection": {"required_status_checks": {"checks": [{"context": "ci", "app_id": 15368}]}},
                               "allowed_actions": {"patterns_allowed": []}}}
        profile = b.github_load(project(self, values))
        self.assertIs(profile["expected"]["protection"]["required_status_checks"]["strict"], False)
        server = FakeGitHub(profile)
        server.state[PROTECTION]["required_status_checks"]["strict"] = True
        code, out, _ = self.run_tool(server, values)
        self.assertEqual(code, 1)
        self.assertIn("차이: protection.required_status_checks.strict: true -> false", out)
        self.assertEqual(server.writes, [])
        code, out, _ = self.run_tool(server, values, apply=True)
        self.assertEqual(code, 0, out)
        self.assertIn("통과", out)
        self.assertEqual(server.writes, [("PUT", PROTECTION)])

    def test_server_ruleset_ids_and_text_cannot_steer_paths_or_the_terminal(self):
        server = FakeGitHub()
        server.rulesets["1/../../collaborators"] = dict(copy.deepcopy(QUEUE), name="x")
        code, _, err = self.run_tool(server, apply=True)
        self.assertEqual((code, server.writes), (2, []))
        self.assertIn("id가 정수인 목록이 아니다", err)
        server = FakeGitHub()
        server.rulesets[1] = dict(copy.deepcopy(QUEUE), name="team\x1b]0;x\x07")
        code, out, _ = self.run_tool(server)
        self.assertEqual(code, 1)
        self.assertNotIn("\x1b", out)
        self.assertIn("rulesets.team?]0;x?은 기준에 없다", out)

    def test_agents_cannot_run_apply(self):
        for rel in ("core/.claude/settings.json", ".claude/settings.json"):
            deny = json.loads((ROOT / rel).read_text(encoding="utf-8"))["permissions"]["deny"]
            self.assertIn("Bash(*baseline.py github apply*)", deny, rel)

    def test_cli_runs_plan_from_the_repo_root(self):
        server = FakeGitHub()
        root = project(self, BASELINE)
        with patch.object(b, "repo_root", lambda: root), patch.object(b, "github_read", server.read), \
                patch.object(b, "github_write", server.write), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(b.main(["github", "plan"]), 0)
        self.assertIn("차이 없음", out.getvalue())


ENV = "SENTRY_DSN=\nSENTRY_AUTH_TOKEN=\nPOSTHOG_KEY=\nPOSTHOG_HOST=\n"


class OpsTests(unittest.TestCase):
    """v1 tools/test_check_ops.py: docs/agents/ops.md when baseline.json lists ops."""

    def repo(self, ops=b.OPS_MD, env=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        if ops is not None:
            (root / "docs/agents").mkdir(parents=True)
            (root / b.OPS_PATH).write_text(ops, encoding="utf-8")
        if env is not None:
            (root / ".env.example").write_text(env, encoding="utf-8")
        return root

    def problems(self, **kwargs):
        return b.ops_problems(self.repo(**kwargs))

    def test_source_file_and_readme_table_match_baseline_py(self):
        self.assertEqual((ROOT / "ops/ops.md").read_text(encoding="utf-8"), b.OPS_MD)
        readme = (ROOT / "ops/README.md").read_text(encoding="utf-8")
        rows = [line for line in readme.split("## 도구", 1)[1].split("\n## ", 1)[0].splitlines() if line.startswith("|")]
        self.assertEqual(tuple(row.split("|")[2].strip() for row in rows[2:]), b.OPS_TOOLS)

    def test_every_rule_line_names_at_most_one_tool(self):
        # One tool per line is what makes an exclusion a plain line deletion.
        for line in b.OPS_MD.splitlines():
            self.assertLessEqual(len([tool for tool in b.OPS_TOOLS if b.ops_mentions(tool, line)]), 1, line)

    def test_block_as_copied_passes(self):
        self.assertEqual(self.problems(), [])

    def test_missing_file_fails(self):
        self.assertEqual(len(self.problems(ops=None)), 1)

    def test_any_edit_inside_the_block_fails(self):
        dropped = b.OPS_MD.replace("- 배포한 URL은 UptimeRobot에 소유자가 등록한다.\n", "")
        self.assertNotEqual(dropped, b.OPS_MD)
        self.assertEqual(self.problems(ops=dropped), [f"{b.OPS_PATH}에 없다: - 배포한 URL은 UptimeRobot에 소유자가 등록한다."])
        body = b.OPS_MD.splitlines()[2:]
        self.assertTrue(self.problems(ops="\n".join(b.OPS_MD.splitlines()[:2] + body[::-1]) + "\n"))

    def test_exclusion_drops_that_tools_lines_only(self):
        text = b.ops_text({"Cloudflare": "웹 도메인이 없는 데스크톱 게임"})
        self.assertNotIn("Cloudflare에", text)
        self.assertIn("UptimeRobot", text)
        self.assertTrue(text.endswith("- 뺀 도구: Cloudflare — 웹 도메인이 없는 데스크톱 게임\n"))
        self.assertEqual(self.problems(ops=text), [])
        # An exclusion line without deleting the tool's lines is not the generated file.
        kept = b.OPS_MD + "- 뺀 도구: Cloudflare — 이유\n"
        self.assertTrue(any("있으면 안 된다" in p for p in self.problems(ops=kept)))

    def test_secret_names_go_with_their_tool(self):
        text = b.ops_text({"Sentry": "서버가 없는 정적 페이지"})
        self.assertNotIn("SENTRY_", text)
        self.assertIn("POSTHOG_KEY", text)

    def test_exclusion_line_format_and_name(self):
        self.assertIn("표에 없는 도구", self.problems(ops=b.OPS_MD + "- 뺀 도구: Datadog — 비싸다\n")[0])
        self.assertIn("형식", self.problems(ops=b.OPS_MD + "- 뺀 도구: Cloudflare\n")[0])

    def test_sdk_stage_checks_env_example(self):
        # v1 checked these with --sdk; v2 starts once .env.example names any ops secret.
        self.assertEqual(self.problems(env="DATABASE_URL=\n"), [])
        self.assertEqual(self.problems(env="SENTRY_AUTH_TOKEN=\n")[0], ".env.example에 SENTRY_DSN 칸이 없다")
        self.assertEqual(self.problems(env=ENV), [])
        self.assertEqual(self.problems(env=ENV.replace("POSTHOG_KEY=", "NEXT_PUBLIC_POSTHOG_KEY=")), [])
        self.assertEqual(self.problems(env=ENV.replace("SENTRY_AUTH_TOKEN=", "SENTRY_AUTH_TOKEN=abc")),
                         [".env.example의 SENTRY_AUTH_TOKEN에 값이 있다. 빈 칸으로 둔다"])
        text = b.ops_text({"Sentry": "정적 페이지"})
        self.assertEqual(self.problems(ops=text, env="POSTHOG_KEY=\nPOSTHOG_HOST=\n"), [])

    def test_check_runs_ops_only_when_the_profile_is_on(self):
        root = self.repo(ops=None)
        (root / ".baseline").mkdir()
        recorded = {"version": b.VERSION, "profiles": [], "managed": b.MANAGED}
        def problems():
            (root / ".baseline/baseline.json").write_bytes(b.dump_json(recorded))
            with patch.object(b, "repo_root", lambda: root), redirect_stderr(io.StringIO()) as err:
                b.cmd_check(None)
            return err.getvalue()
        self.assertNotIn(b.OPS_PATH, problems())
        recorded["profiles"] = ["ops"]
        self.assertIn(b.OPS_PATH, problems())
        recorded["profiles"] = "ops"  # not a list: no crash, no ops check
        self.assertNotIn(b.OPS_PATH, problems())


class GithubReadTests(unittest.TestCase):
    def test_an_oversized_response_stops_the_run(self):
        huge = subprocess.CompletedProcess([], 0, stdout="[" + " " * (b.MAX_READ * 32) + "]", stderr="")
        with patch.object(b.subprocess, "run", return_value=huge):
            with self.assertRaisesRegex(OSError, "너무 크다"):
                b.github_read("repos/owner/repo/labels")

    def test_a_normal_response_is_parsed(self):
        small = subprocess.CompletedProcess([], 0, stdout='[{"name": "bug"}]', stderr="")
        with patch.object(b.subprocess, "run", return_value=small):
            self.assertEqual(b.github_read("repos/owner/repo/labels"), [{"name": "bug"}])


if __name__ == "__main__":
    unittest.main()
