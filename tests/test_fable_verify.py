from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "fable-verify"


class FableVerifyCliTest(unittest.TestCase):
    def run_cli(self, cwd: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(CLI), *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"command failed: {args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def write_acceptance(self, cwd: Path, criteria: list[dict[str, object]]) -> None:
        path = cwd / ".fable-verify" / "acceptance.json"
        path.write_text(json.dumps({"criteria": criteria}, indent=2) + "\n", encoding="utf-8")

    def read_json(self, path: Path) -> dict[str, object]:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_png(self, path: Path) -> None:
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
            b"\x90wS\xde"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    def state_snapshot(self, cwd: Path) -> dict[str, str]:
        paths = [
            cwd / ".fable-verify" / "goal.md",
            cwd / ".fable-verify" / "acceptance.json",
            cwd / ".fable-verify" / "ledger.json",
            cwd / ".fable-verify" / "evidence" / "index.json",
        ]
        return {path.name: path.read_text(encoding="utf-8") for path in paths}

    def single_criterion(self, evidence_required: list[str] | None = None) -> dict[str, object]:
        return {
            "id": "AC-001",
            "description": "A testable requirement.",
            "evidence_required": evidence_required or ["test"],
            "status": "pending",
            "evidence": [],
            "notes": "",
        }

    def add_generated_bug_evidence(self, cwd: Path) -> None:
        commands = [
            ("AC-001", "test", "print('reproduced redirect bug')"),
            ("AC-001", "log", "print('before: redirect loop observed')"),
            ("AC-002", "diff", "print('diff reviewed: login redirect fix')"),
            ("AC-003", "test", "print('redirect regression test passed')"),
            ("AC-004", "diff", "print('scoped diff reviewed')"),
        ]
        for criterion_id, evidence_type, script in commands:
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                criterion_id,
                "--type",
                evidence_type,
                "--command",
                f"{sys.executable} -c \"{script}\"",
                check=True,
            )

    def add_generated_generic_evidence(self, cwd: Path) -> None:
        commands = [
            ("AC-001", "file-read", "print('acceptance criteria reviewed')"),
            ("AC-002", "diff", "print('implementation diff reviewed')"),
            ("AC-003", "test", "print('verification passed')"),
        ]
        for criterion_id, evidence_type, script in commands:
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                criterion_id,
                "--type",
                evidence_type,
                "--command",
                f"{sys.executable} -c \"{script}\"",
                check=True,
            )

    def test_init_creates_expected_files_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            first = self.run_cli(cwd, "init", check=True)
            second = self.run_cli(cwd, "init", check=True)

            self.assertIn("Initialized Fable Verify", first.stdout)
            self.assertIn("already initialized", second.stdout)
            self.assertTrue((cwd / ".fable-verify" / "goal.md").exists())
            self.assertTrue((cwd / ".fable-verify" / "acceptance.json").exists())
            self.assertTrue((cwd / ".fable-verify" / "ledger.json").exists())
            self.assertTrue((cwd / ".fable-verify" / "evidence").is_dir())
            self.assertTrue((cwd / ".fable-verify" / "reports").is_dir())

    def test_plan_without_force_does_not_record_new_goal_over_existing_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            old_goal = "Fix: redirect loop"
            new_goal = "Ship unrelated billing dashboard"
            self.run_cli(cwd, "init", check=True)
            self.run_cli(cwd, "plan", old_goal, check=True)
            self.add_generated_bug_evidence(cwd)
            first_check = self.run_cli(cwd, "check")
            before = self.state_snapshot(cwd)

            replan = self.run_cli(cwd, "plan", new_goal)
            after = self.state_snapshot(cwd)
            second_check = self.run_cli(cwd, "check")
            status = self.run_cli(cwd, "status")

            self.assertEqual(first_check.returncode, 0)
            self.assertEqual(replan.returncode, 0)
            self.assertIn("plan unchanged", replan.stdout)
            self.assertIn("Use --force to regenerate criteria", replan.stdout)
            self.assertEqual(before, after)
            self.assertEqual(second_check.returncode, 0)
            self.assertIn(old_goal, status.stdout)
            self.assertNotIn(new_goal, status.stdout)
            self.assertNotIn(new_goal, (cwd / ".fable-verify" / "goal.md").read_text(encoding="utf-8"))
            ledger = self.read_json(cwd / ".fable-verify" / "ledger.json")
            self.assertEqual(old_goal, ledger["goal"])

    def test_plan_same_goal_with_existing_criteria_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            goal = "Fix: redirect loop"
            self.run_cli(cwd, "init", check=True)
            self.run_cli(cwd, "plan", goal, check=True)
            before = self.state_snapshot(cwd)

            second = self.run_cli(cwd, "plan", goal)

            self.assertEqual(second.returncode, 0)
            self.assertIn("plan unchanged", second.stdout)
            self.assertEqual(before, self.state_snapshot(cwd))

    def test_generated_criteria_do_not_require_report_evidence(self) -> None:
        cases = [
            ("Fix: redirect loop", 4, "Bug reproduction or characterization exists."),
            ("Add a tiny verification demo", 3, "The goal is captured as explicit, testable acceptance criteria."),
        ]
        for goal, expected_count, first_description in cases:
            with self.subTest(goal=goal):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)
                    self.run_cli(cwd, "plan", goal, check=True)
                    criteria = self.read_json(cwd / ".fable-verify" / "acceptance.json")["criteria"]
                    descriptions = [criterion["description"] for criterion in criteria]

                    self.assertEqual(expected_count, len(criteria))
                    self.assertEqual(first_description, descriptions[0])
                    self.assertNotIn("Final verification report is generated.", descriptions)
                    self.assertFalse(
                        any(criterion["evidence_required"] == ["file-read"] and "report" in criterion["description"].lower() for criterion in criteria)
                    )

    def test_bug_goal_detection_handles_punctuation_and_hyphens(self) -> None:
        goals = [
            "Bug: login redirect fails",
            "bug-fix login redirect",
            "fix: redirect loop",
            "regression-login",
        ]
        for goal in goals:
            with self.subTest(goal=goal):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)

                    self.run_cli(cwd, "plan", goal, check=True)
                    criteria = self.read_json(cwd / ".fable-verify" / "acceptance.json")["criteria"]

                    self.assertEqual("Bug reproduction or characterization exists.", criteria[0]["description"])
                    self.assertEqual(["test", "log"], criteria[0]["evidence_required"])
                    self.assertEqual(4, len(criteria))

    def test_generated_bug_criteria_can_pass_before_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.run_cli(cwd, "plan", "Bug: login redirect fails", check=True)
            self.add_generated_bug_evidence(cwd)

            check = self.run_cli(cwd, "check")
            reports_before = list((cwd / ".fable-verify" / "reports").glob("*.md"))
            report = self.run_cli(cwd, "report", check=True)

            self.assertEqual(check.returncode, 0)
            self.assertIn("PASS", check.stdout)
            self.assertEqual([], reports_before)
            self.assertTrue((cwd / report.stdout.splitlines()[0]).exists())

    def test_force_plan_clears_stale_verdict_and_requires_new_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.run_cli(cwd, "plan", "Bug: login redirect fails", check=True)
            self.add_generated_bug_evidence(cwd)
            first_check = self.run_cli(cwd, "check")
            old_index = self.read_json(cwd / ".fable-verify" / "evidence" / "index.json")

            forced = self.run_cli(cwd, "plan", "--force", "Add a tiny verification demo")
            ledger_after_force = self.read_json(cwd / ".fable-verify" / "ledger.json")
            acceptance_after_force = self.read_json(cwd / ".fable-verify" / "acceptance.json")
            index_after_force = self.read_json(cwd / ".fable-verify" / "evidence" / "index.json")
            second_check = self.run_cli(cwd, "check")

            self.assertEqual(first_check.returncode, 0)
            self.assertEqual(forced.returncode, 0)
            self.assertEqual("active", ledger_after_force["status"])
            self.assertIsNone(ledger_after_force["final_verdict"])
            self.assertEqual("Add a tiny verification demo", ledger_after_force["goal"])
            self.assertEqual(old_index, index_after_force)
            self.assertTrue(all(criterion["evidence"] == [] for criterion in acceptance_after_force["criteria"]))
            self.assertNotEqual(second_check.returncode, 0)
            self.assertIn("FAIL", second_check.stdout)
            self.assertIn("missing required evidence type", second_check.stdout)

    def test_repeated_reports_create_distinct_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )

            first = self.run_cli(cwd, "report", check=True).stdout.splitlines()[0]
            second = self.run_cli(cwd, "report", check=True).stdout.splitlines()[0]

            self.assertNotEqual(first, second)
            self.assertTrue((cwd / first).exists())
            self.assertTrue((cwd / second).exists())

    def test_lifecycle_transitions_keep_state_boundaries_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.assertEqual([], self.read_json(cwd / ".fable-verify" / "acceptance.json")["criteria"])

            self.run_cli(cwd, "plan", "Bug: login redirect fails", check=True)
            first_check = self.run_cli(cwd, "check")
            first_snapshot = self.state_snapshot(cwd)
            replan = self.run_cli(cwd, "plan", "Ship unrelated billing dashboard")

            self.assertNotEqual(first_check.returncode, 0)
            self.assertIn("plan unchanged", replan.stdout)
            self.assertEqual(first_snapshot, self.state_snapshot(cwd))

            self.add_generated_bug_evidence(cwd)
            pass_check = self.run_cli(cwd, "check")
            report_one = self.run_cli(cwd, "report", check=True).stdout.splitlines()[0]
            report_two = self.run_cli(cwd, "report", check=True).stdout.splitlines()[0]

            self.assertEqual(pass_check.returncode, 0)
            self.assertNotEqual(report_one, report_two)
            self.assertIn("VERIFIED", (cwd / report_one).read_text(encoding="utf-8"))
            self.assertIn("VERIFIED", (cwd / report_two).read_text(encoding="utf-8"))

            self.run_cli(cwd, "plan", "--force", "Add a tiny verification demo", check=True)
            forced_ledger = self.read_json(cwd / ".fable-verify" / "ledger.json")
            forced_acceptance = self.read_json(cwd / ".fable-verify" / "acceptance.json")
            forced_check = self.run_cli(cwd, "check")

            self.assertEqual("active", forced_ledger["status"])
            self.assertIsNone(forced_ledger["final_verdict"])
            self.assertTrue(all(criterion["evidence"] == [] for criterion in forced_acceptance["criteria"]))
            self.assertNotEqual(forced_check.returncode, 0)

            self.add_generated_generic_evidence(cwd)
            final_check = self.run_cli(cwd, "check")
            final_ledger = self.read_json(cwd / ".fable-verify" / "ledger.json")

            self.assertEqual(final_check.returncode, 0)
            self.assertEqual("VERIFIED", final_ledger["final_verdict"])

    def test_release_visible_files_exclude_generated_artifacts_and_local_paths(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".fable-verify/", gitignore)
        self.assertIn("__pycache__/", gitignore)

        ignored_dirs = {".git", ".fable-verify", "__pycache__"}
        forbidden_markers = ["/" + "Users/", "/var/" + "folders/"]
        offenders: list[str] = []
        for path in ROOT.rglob("*"):
            if any(part in ignored_dirs for part in path.relative_to(ROOT).parts):
                continue
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(marker in content for marker in forbidden_markers):
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual([], offenders)

    def test_missing_evidence_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])

            result = self.run_cli(cwd, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL", result.stdout)
            self.assertIn("missing required evidence type: test", result.stdout)

    def test_nonzero_command_evidence_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])

            add = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'import sys; print(\"bad\"); sys.exit(7)'",
            )
            check = self.run_cli(cwd, "check")

            self.assertEqual(add.returncode, 1)
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("command failed with exit code 7", check.stdout)

    def test_cross_criterion_evidence_reuse_fails_with_owner_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            ac_one = self.single_criterion(["test"])
            ac_two = {
                "id": "AC-002",
                "description": "A separate requirement.",
                "evidence_required": ["test"],
                "status": "pending",
                "evidence": [],
                "notes": "",
            }
            self.write_acceptance(cwd, [ac_one, ac_two])
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"owned\")'",
                check=True,
            )
            acceptance_path = cwd / ".fable-verify" / "acceptance.json"
            acceptance = self.read_json(acceptance_path)
            acceptance["criteria"][1]["evidence"] = ["EV-001"]
            acceptance_path.write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")

            result = self.run_cli(cwd, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AC-002 references evidence EV-001 owned by AC-001", result.stdout)
            self.assertIn("AC-002 is missing required evidence type: test", result.stdout)

    def test_old_same_id_evidence_does_not_satisfy_new_empty_criterion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"old proof\")'",
                check=True,
            )
            first_check = self.run_cli(cwd, "check")
            self.write_acceptance(
                cwd,
                [
                    {
                        "id": "AC-001",
                        "description": "A new unrelated requirement that reused the ID.",
                        "evidence_required": ["test"],
                        "status": "pending",
                        "evidence": [],
                        "notes": "",
                    }
                ],
            )

            second_check = self.run_cli(cwd, "check")

            self.assertEqual(first_check.returncode, 0)
            self.assertNotEqual(second_check.returncode, 0)
            self.assertIn("AC-001 is missing required evidence type: test", second_check.stdout)
            acceptance = self.read_json(cwd / ".fable-verify" / "acceptance.json")
            self.assertEqual([], acceptance["criteria"][0]["evidence"])

    def test_missing_artifact_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            criterion = self.single_criterion(["test"])
            criterion["evidence"] = ["EV-001"]
            self.write_acceptance(cwd, [criterion])
            index = {
                "evidence": [
                    {
                        "id": "EV-001",
                        "criterion_id": "AC-001",
                        "type": "test",
                        "command": "npm test",
                        "exit_code": 0,
                        "artifact_path": ".fable-verify/evidence/missing.log",
                        "summary": "Pretend tests passed",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ]
            }
            (cwd / ".fable-verify" / "evidence" / "index.json").write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
            )

            result = self.run_cli(cwd, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("artifact is missing", result.stdout)

    def test_add_evidence_missing_artifact_fails_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["log"])])
            acceptance_before = (cwd / ".fable-verify" / "acceptance.json").read_text(encoding="utf-8")
            index_before = (cwd / ".fable-verify" / "evidence" / "index.json").read_text(encoding="utf-8")

            result = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "log",
                "--artifact-path",
                "missing.log",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing artifact path", result.stderr)
            self.assertEqual(
                acceptance_before,
                (cwd / ".fable-verify" / "acceptance.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                index_before,
                (cwd / ".fable-verify" / "evidence" / "index.json").read_text(encoding="utf-8"),
            )

    def test_command_like_passive_artifacts_fail_without_mutating_state(self) -> None:
        for evidence_type in ("test", "build", "lint", "typecheck"):
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)
                    self.write_acceptance(cwd, [self.single_criterion([evidence_type])])
                    artifact = cwd / f"{evidence_type}.log"
                    artifact.write_text("passive artifact only\n", encoding="utf-8")
                    before = self.state_snapshot(cwd)

                    result = self.run_cli(
                        cwd,
                        "add-evidence",
                        "--criterion",
                        "AC-001",
                        "--type",
                        evidence_type,
                        "--artifact-path",
                        str(artifact),
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("requires command provenance", result.stderr)
                    self.assertEqual(before, self.state_snapshot(cwd))

    def test_command_like_index_record_without_command_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            criterion = self.single_criterion(["test"])
            criterion["evidence"] = ["EV-001"]
            self.write_acceptance(cwd, [criterion])
            artifact = cwd / "passive-test-note.txt"
            artifact.write_text("looks like a test receipt, but has no command\n", encoding="utf-8")
            index = {
                "evidence": [
                    {
                        "id": "EV-001",
                        "criterion_id": "AC-001",
                        "type": "test",
                        "command": None,
                        "exit_code": None,
                        "artifact_path": "passive-test-note.txt",
                        "summary": "Passive test-looking receipt",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ]
            }
            (cwd / ".fable-verify" / "evidence" / "index.json").write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
            )

            result = self.run_cli(cwd, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("EV-001 type test requires command provenance", result.stdout)
            self.assertIn("AC-001 is missing required evidence type: test", result.stdout)

    def test_diff_without_command_or_artifact_fails_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["diff"])])
            before = self.state_snapshot(cwd)

            result = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "diff",
                "--summary",
                "Trust me, the diff is scoped.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("diff evidence requires --command output or a real attached artifact", result.stderr)
            self.assertEqual(before, self.state_snapshot(cwd))

    def test_screenshot_without_real_artifact_fails_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["screenshot"])])
            before = self.state_snapshot(cwd)

            missing_artifact = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "screenshot",
                "--summary",
                "Screenshot captured.",
            )
            text_artifact = cwd / "not-an-image.txt"
            text_artifact.write_text("not actually an image\n", encoding="utf-8")
            wrong_type = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "screenshot",
                "--artifact-path",
                str(text_artifact),
            )

            self.assertNotEqual(missing_artifact.returncode, 0)
            self.assertNotEqual(wrong_type.returncode, 0)
            self.assertIn("requires a real attached image artifact", missing_artifact.stderr)
            self.assertIn("requires an image artifact", wrong_type.stderr)
            self.assertEqual(before, self.state_snapshot(cwd))

    def test_browser_placeholder_only_evidence_fails_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["browser"])])
            before = self.state_snapshot(cwd)

            result = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "browser",
                "--summary",
                "Browser flow looked fine.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("browser evidence requires --command output or a real attached artifact", result.stderr)
            self.assertEqual(before, self.state_snapshot(cwd))

    def test_file_read_placeholder_only_evidence_fails_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["file-read"])])
            before = self.state_snapshot(cwd)

            result = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--summary",
                "Read the important file.",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("file-read evidence requires --command output or a real attached artifact", result.stderr)
            self.assertEqual(before, self.state_snapshot(cwd))

    def test_directory_artifact_path_fails_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["log"])])
            artifact_dir = cwd / "artifact-dir"
            artifact_dir.mkdir()
            before = self.state_snapshot(cwd)

            result = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "log",
                "--artifact-path",
                str(artifact_dir),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Artifact paths must point to files", result.stderr)
            self.assertEqual(before, self.state_snapshot(cwd))

    def test_external_command_artifact_requires_exit_code_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])
            artifact = cwd / "external-command.log"
            artifact.write_text("captured elsewhere\n", encoding="utf-8")
            acceptance_before = (cwd / ".fable-verify" / "acceptance.json").read_text(encoding="utf-8")
            ledger_before = (cwd / ".fable-verify" / "ledger.json").read_text(encoding="utf-8")
            index_before = (cwd / ".fable-verify" / "evidence" / "index.json").read_text(encoding="utf-8")

            result = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                "external test command",
                "--artifact-path",
                str(artifact),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires --exit-code", result.stderr)
            self.assertEqual(
                acceptance_before,
                (cwd / ".fable-verify" / "acceptance.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                ledger_before,
                (cwd / ".fable-verify" / "ledger.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                index_before,
                (cwd / ".fable-verify" / "evidence" / "index.json").read_text(encoding="utf-8"),
            )

    def test_external_command_artifact_with_exit_code_zero_passes(self) -> None:
        for evidence_type in ("test", "build", "lint", "typecheck"):
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)
                    self.write_acceptance(cwd, [self.single_criterion([evidence_type])])
                    artifact = cwd / "external-command.log"
                    artifact.write_text("captured elsewhere\n", encoding="utf-8")

                    add = self.run_cli(
                        cwd,
                        "add-evidence",
                        "--criterion",
                        "AC-001",
                        "--type",
                        evidence_type,
                        "--command",
                        f"external {evidence_type} command",
                        "--artifact-path",
                        str(artifact),
                        "--exit-code",
                        "0",
                    )
                    check = self.run_cli(cwd, "check")

                    self.assertEqual(add.returncode, 0)
                    self.assertIn("Command exit code: 0", add.stdout)
                    self.assertEqual(check.returncode, 0)

    def test_command_like_command_capture_without_artifact_works(self) -> None:
        for evidence_type in ("test", "build", "lint", "typecheck"):
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)
                    self.write_acceptance(cwd, [self.single_criterion([evidence_type])])

                    add = self.run_cli(
                        cwd,
                        "add-evidence",
                        "--criterion",
                        "AC-001",
                        "--type",
                        evidence_type,
                        "--command",
                        f"{sys.executable} -c 'print(\"{evidence_type} ok\")'",
                    )
                    check = self.run_cli(cwd, "check")
                    index = self.read_json(cwd / ".fable-verify" / "evidence" / "index.json")
                    record = index["evidence"][0]

                    self.assertEqual(add.returncode, 0)
                    self.assertEqual(record["exit_code"], 0)
                    self.assertTrue((cwd / record["artifact_path"]).is_file())
                    self.assertEqual(check.returncode, 0)

    def test_external_command_artifact_with_nonzero_exit_is_recorded_and_fails(self) -> None:
        for evidence_type in ("test", "build", "lint", "typecheck"):
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)
                    self.write_acceptance(cwd, [self.single_criterion([evidence_type])])
                    artifact = cwd / "external-command.log"
                    artifact.write_text("captured failure\n", encoding="utf-8")

                    add = self.run_cli(
                        cwd,
                        "add-evidence",
                        "--criterion",
                        "AC-001",
                        "--type",
                        evidence_type,
                        "--command",
                        f"external {evidence_type} command",
                        "--artifact-path",
                        str(artifact),
                        "--exit-code",
                        "9",
                    )
                    check = self.run_cli(cwd, "check")
                    index = self.read_json(cwd / ".fable-verify" / "evidence" / "index.json")

                    self.assertEqual(add.returncode, 1)
                    self.assertEqual(9, index["evidence"][0]["exit_code"])
                    self.assertNotEqual(check.returncode, 0)
                    self.assertIn("command failed with exit code 9", check.stdout)

    def test_passive_non_command_artifacts_are_allowed(self) -> None:
        artifacts = {
            "screenshot": "screenshot.png",
            "browser": "browser.log",
            "log": "receipt.log",
            "file-read": "file-read.txt",
            "diff": "diff.patch",
            "manual-user-confirmation": "confirmation.txt",
        }
        for evidence_type, filename in artifacts.items():
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)
                    self.write_acceptance(cwd, [self.single_criterion([evidence_type])])
                    artifact = cwd / filename
                    if evidence_type == "screenshot":
                        self.write_png(artifact)
                    else:
                        artifact.write_text(f"{evidence_type} receipt\n", encoding="utf-8")

                    add = self.run_cli(
                        cwd,
                        "add-evidence",
                        "--criterion",
                        "AC-001",
                        "--type",
                        evidence_type,
                        "--artifact-path",
                        str(artifact),
                    )
                    check = self.run_cli(cwd, "check")

                    self.assertEqual(add.returncode, 0)
                    self.assertEqual(check.returncode, 0)

    def test_log_and_manual_confirmation_are_recorded_as_weak_evidence(self) -> None:
        for evidence_type in ("log", "manual-user-confirmation"):
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as temp:
                    cwd = Path(temp)
                    self.run_cli(cwd, "init", check=True)
                    self.write_acceptance(cwd, [self.single_criterion([evidence_type])])

                    add = self.run_cli(
                        cwd,
                        "add-evidence",
                        "--criterion",
                        "AC-001",
                        "--type",
                        evidence_type,
                        "--summary",
                        "Self-attested receipt.",
                    )
                    check = self.run_cli(cwd, "check")
                    index = self.read_json(cwd / ".fable-verify" / "evidence" / "index.json")

                    self.assertEqual(add.returncode, 0)
                    self.assertEqual(check.returncode, 0)
                    self.assertEqual("weak", index["evidence"][0]["strength"])
                    self.assertIn("artifact_sha256", index["evidence"][0])
                    self.assertIn("artifact_size", index["evidence"][0])

    def test_weak_evidence_cannot_be_relabelled_as_strong(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["manual-user-confirmation"])])
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "manual-user-confirmation",
                "--summary",
                "A person approved it.",
                check=True,
            )
            index_path = cwd / ".fable-verify" / "evidence" / "index.json"
            index = self.read_json(index_path)
            index["evidence"][0]["strength"] = "strong"
            index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

            check = self.run_cli(cwd, "check")

            self.assertNotEqual(check.returncode, 0)
            self.assertIn("strength metadata mismatch: expected weak, found strong", check.stdout)

    def test_external_artifact_is_copied_into_repo_local_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            cwd = temp_path / "project"
            cwd.mkdir()
            external = temp_path / "outside.log"
            external.write_text("external proof\n", encoding="utf-8")
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["log"])])

            add = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "log",
                "--artifact-path",
                str(external),
                "--summary",
                "External log copied",
                check=True,
            )
            check = self.run_cli(cwd, "check")
            index = self.read_json(cwd / ".fable-verify" / "evidence" / "index.json")
            record = index["evidence"][0]
            copied_path = cwd / record["artifact_path"]

            self.assertIn(".fable-verify/evidence/EV-001-outside.log", add.stdout)
            self.assertEqual(record["artifact_policy"], "copied-external-to-evidence")
            self.assertEqual(record["source_artifact_path"], str(external.resolve()))
            self.assertTrue(copied_path.exists())
            self.assertEqual("external proof\n", copied_path.read_text(encoding="utf-8"))
            self.assertEqual(check.returncode, 0)

    def test_valid_evidence_passes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])

            add = self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )
            result = self.run_cli(cwd, "check")

            self.assertIn("Command exit code: 0", add.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertIn("PASS", result.stdout)

    def test_manual_evidence_is_weak_for_technical_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])

            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "manual-user-confirmation",
                "--summary",
                "A person says it works.",
                check=True,
            )
            result = self.run_cli(cwd, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required evidence type: test", result.stdout)

    def test_tampered_artifact_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["file-read"])])
            artifact = cwd / "read-proof.txt"
            artifact.write_text("original file-read proof\n", encoding="utf-8")
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                str(artifact),
                check=True,
            )
            first_check = self.run_cli(cwd, "check")
            artifact.write_text("tampered file-read proof\n", encoding="utf-8")

            second_check = self.run_cli(cwd, "check")

            self.assertEqual(first_check.returncode, 0)
            self.assertNotEqual(second_check.returncode, 0)
            self.assertIn("tampered", second_check.stdout)
            self.assertIn("missing required evidence type: file-read", second_check.stdout)

    def test_missing_hash_metadata_for_strong_evidence_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            criterion = self.single_criterion(["diff"])
            criterion["evidence"] = ["EV-001"]
            self.write_acceptance(cwd, [criterion])
            artifact = cwd / "changes.patch"
            artifact.write_text("diff --git a/app.py b/app.py\n", encoding="utf-8")
            index = {
                "evidence": [
                    {
                        "id": "EV-001",
                        "criterion_id": "AC-001",
                        "type": "diff",
                        "command": None,
                        "exit_code": None,
                        "artifact_path": "changes.patch",
                        "artifact_policy": "repo-local",
                        "summary": "Legacy diff without hash metadata",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ]
            }
            (cwd / ".fable-verify" / "evidence" / "index.json").write_text(
                json.dumps(index, indent=2) + "\n",
                encoding="utf-8",
            )

            result = self.run_cli(cwd, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("legacy unverified: missing artifact hash/size metadata", result.stdout)
            self.assertIn("missing required evidence type: diff", result.stdout)

    def test_unresolved_blocker_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )
            ledger_path = cwd / ".fable-verify" / "ledger.json"
            ledger = self.read_json(ledger_path)
            ledger["blockers"] = [{"id": "B-001", "description": "Need reviewer confirmation", "resolved": False}]
            ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

            result = self.run_cli(cwd, "check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unresolved blocker: Need reviewer confirmation.", result.stdout)

    def test_report_generation_creates_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"ok\")'",
                check=True,
            )

            report = self.run_cli(cwd, "report", check=True)
            report_path = cwd / report.stdout.splitlines()[0]

            self.assertTrue(report_path.exists())
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("# Fable Verify Report", content)
            self.assertIn("Final verdict: VERIFIED", content)
            self.assertIn("SHA-256", content)
            self.assertIn("Size", content)
            self.assertIn("Integrity", content)
            self.assertIn("| EV-001 | AC-001 | test | strong | 0 |", content)
            self.assertIn("| ok | test command exited 0 |", content)

    def test_report_separates_current_proof_from_historical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["test"])])
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "test",
                "--command",
                f"{sys.executable} -c 'print(\"old proof\")'",
                "--summary",
                "Old proof receipt",
                check=True,
            )
            self.write_acceptance(
                cwd,
                [
                    {
                        "id": "AC-001",
                        "description": "A new requirement with current evidence only.",
                        "evidence_required": ["file-read"],
                        "status": "pending",
                        "evidence": [],
                        "notes": "",
                    }
                ],
            )
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--command",
                f"{sys.executable} -c 'print(\"current proof\")'",
                "--summary",
                "Current proof receipt",
                check=True,
            )

            report = self.run_cli(cwd, "report", check=True)
            content = (cwd / report.stdout.splitlines()[0]).read_text(encoding="utf-8")
            current_section = content.split("## Current Proof Evidence", 1)[1].split("## Current Proof Commands", 1)[0]
            historical_section = content.split("## Historical Evidence", 1)[1].split("## Files Changed", 1)[0]

            self.assertIn("Current proof receipt", current_section)
            self.assertNotIn("Old proof receipt", current_section)
            self.assertIn("Old proof receipt", historical_section)
            self.assertIn("Historical receipts remain in `.fable-verify/evidence/index.json`", historical_section)

    def test_report_compacts_historical_evidence_to_latest_ten_with_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            self.run_cli(cwd, "init", check=True)
            self.write_acceptance(cwd, [self.single_criterion(["log"])])
            for number in range(1, 13):
                artifact = cwd / f"old-{number:02d}.log"
                artifact.write_text(f"old proof {number}\n", encoding="utf-8")
                self.run_cli(
                    cwd,
                    "add-evidence",
                    "--criterion",
                    "AC-001",
                    "--type",
                    "log",
                    "--artifact-path",
                    str(artifact),
                    "--summary",
                    f"Old proof {number:02d}",
                    check=True,
                )
            self.write_acceptance(cwd, [self.single_criterion(["file-read"])])
            current_artifact = cwd / "current.txt"
            current_artifact.write_text("current proof\n", encoding="utf-8")
            self.run_cli(
                cwd,
                "add-evidence",
                "--criterion",
                "AC-001",
                "--type",
                "file-read",
                "--artifact-path",
                str(current_artifact),
                "--summary",
                "Current proof",
                check=True,
            )

            report = self.run_cli(cwd, "report", check=True)
            content = (cwd / report.stdout.splitlines()[0]).read_text(encoding="utf-8")
            historical_section = content.split("## Historical Evidence", 1)[1].split("## Files Changed", 1)[0]

            self.assertIn("Total historical records: 12. Showing latest 10 of 12.", historical_section)
            self.assertIn("Full historical receipts remain in `.fable-verify/evidence/index.json`.", historical_section)
            self.assertIn("| log | 12 |", historical_section)
            self.assertIn("Old proof 12", historical_section)
            self.assertNotIn("Old proof 01", historical_section)


if __name__ == "__main__":
    unittest.main()
