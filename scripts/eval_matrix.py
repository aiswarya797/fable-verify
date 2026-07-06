#!/usr/bin/env python3
"""Exercise canned pass/fail verification scenarios against the CLI."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ScenarioResult:
    name: str
    expected_gate: str
    ok: bool
    detail: str


def resolve_cli() -> str:
    candidates: list[str | None] = [
        os.environ.get("FABLE_VERIFY_BIN"),
        str(PROJECT_ROOT / "bin" / "fable-verify"),
        shutil.which("fable-verify"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() or shutil.which(candidate):
            return candidate
    raise SystemExit("fable-verify not found via FABLE_VERIFY_BIN, repo bin, or PATH")


def python_command(code: str) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([sys.executable, "-c", code])
    return shlex.join([sys.executable, "-c", code])


def run_cli(cli: str, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([cli, *args], cwd=cwd, text=True, capture_output=True, check=False)


def review_evidence(cli: str, cwd: Path, criterion: str, evidence: str, notes: str) -> tuple[bool, str]:
    show = run_cli(cli, cwd, "show", evidence)
    if show.returncode != 0:
        return False, show.stderr.strip() or show.stdout.strip()
    review = run_cli(
        cli,
        cwd,
        "review",
        "--criterion",
        criterion,
        "--evidence",
        evidence,
        "--verdict",
        "supports",
        "--notes",
        notes,
    )
    if review.returncode != 0:
        return False, review.stderr.strip() or review.stdout.strip()
    return True, review.stdout.strip()


def write_acceptance(cwd: Path, required: list[str]) -> None:
    data = {
        "criteria": [
            {
                "id": "AC-001",
                "description": "A testable requirement.",
                "evidence_required": required,
                "status": "pending",
                "evidence": [],
                "notes": "",
            }
        ]
    }
    (cwd / ".fable-verify" / "acceptance.json").write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


def in_workspace(cli: str, scenario: Callable[[str, Path], tuple[bool, str]]) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="fable-verify-eval-") as temp:
        cwd = Path(temp)
        init = run_cli(cli, cwd, "init")
        if init.returncode != 0:
            return False, init.stderr.strip() or init.stdout.strip()
        return scenario(cli, cwd)


def missing_evidence_fails(cli: str, cwd: Path) -> tuple[bool, str]:
    write_acceptance(cwd, ["test"])
    check = run_cli(cli, cwd, "check")
    ok = check.returncode != 0 and "missing required evidence type: test" in check.stdout
    return ok, "gate failed for missing test evidence" if ok else check.stdout


def good_command_evidence_passes(cli: str, cwd: Path) -> tuple[bool, str]:
    write_acceptance(cwd, ["test"])
    add = run_cli(
        cli,
        cwd,
        "add-evidence",
        "--criterion",
        "AC-001",
        "--type",
        "test",
        "--command",
        python_command("print('ok')"),
    )
    reviewed, review_detail = review_evidence(
        cli,
        cwd,
        "AC-001",
        "EV-001",
        "Test log shows command output and exit code 0.",
    )
    check = run_cli(cli, cwd, "check")
    ok = add.returncode == 0 and reviewed and check.returncode == 0 and "PASS" in check.stdout
    return ok, "gate passed with reviewed command-backed test evidence" if ok else check.stdout or add.stderr or review_detail


def unreviewed_evidence_fails(cli: str, cwd: Path) -> tuple[bool, str]:
    write_acceptance(cwd, ["test"])
    add = run_cli(
        cli,
        cwd,
        "add-evidence",
        "--criterion",
        "AC-001",
        "--type",
        "test",
        "--command",
        python_command("print('ok')"),
    )
    check = run_cli(cli, cwd, "check")
    ok = (
        add.returncode == 0
        and check.returncode != 0
        and "has not been reviewed against the acceptance criterion" in check.stdout
    )
    return ok, "gate failed because evidence was not reviewed" if ok else check.stdout or add.stderr


def nonzero_command_evidence_fails(cli: str, cwd: Path) -> tuple[bool, str]:
    write_acceptance(cwd, ["test"])
    add = run_cli(
        cli,
        cwd,
        "add-evidence",
        "--criterion",
        "AC-001",
        "--type",
        "test",
        "--command",
        python_command("import sys; print('bad'); sys.exit(7)"),
    )
    check = run_cli(cli, cwd, "check")
    ok = add.returncode == 1 and check.returncode != 0 and "command failed with exit code 7" in check.stdout
    return ok, "gate failed for nonzero command evidence" if ok else check.stdout or add.stdout or add.stderr


def tampered_artifact_fails(cli: str, cwd: Path) -> tuple[bool, str]:
    write_acceptance(cwd, ["file-read"])
    artifact = cwd / "read-proof.txt"
    artifact.write_text("original proof\n", encoding="utf-8")
    add = run_cli(
        cli,
        cwd,
        "add-evidence",
        "--criterion",
        "AC-001",
        "--type",
        "file-read",
        "--artifact-path",
        str(artifact),
    )
    reviewed, review_detail = review_evidence(
        cli,
        cwd,
        "AC-001",
        "EV-001",
        "File-read artifact contents support the criterion before tampering.",
    )
    first_check = run_cli(cli, cwd, "check")
    artifact.write_text("tampered proof\n", encoding="utf-8")
    second_check = run_cli(cli, cwd, "check")
    ok = (
        add.returncode == 0
        and reviewed
        and first_check.returncode == 0
        and second_check.returncode != 0
        and "tampered" in second_check.stdout
        and "latest review" in second_check.stdout
    )
    return ok, "gate failed after reviewed artifact tampering" if ok else second_check.stdout or add.stderr or review_detail


def missing_artifact_fails(cli: str, cwd: Path) -> tuple[bool, str]:
    write_acceptance(cwd, ["file-read"])
    artifact = cwd / "read-proof.txt"
    artifact.write_text("original proof\n", encoding="utf-8")
    add = run_cli(
        cli,
        cwd,
        "add-evidence",
        "--criterion",
        "AC-001",
        "--type",
        "file-read",
        "--artifact-path",
        str(artifact),
    )
    reviewed, review_detail = review_evidence(
        cli,
        cwd,
        "AC-001",
        "EV-001",
        "File-read artifact exists and supports the criterion before deletion.",
    )
    artifact.unlink()
    check = run_cli(cli, cwd, "check")
    ok = add.returncode == 0 and reviewed and check.returncode != 0 and "artifact is missing" in check.stdout
    return ok, "gate failed after artifact deletion" if ok else check.stdout or add.stderr or review_detail


def main() -> int:
    cli = resolve_cli()
    scenarios: list[tuple[str, str, Callable[[str, Path], tuple[bool, str]]]] = [
        ("missing evidence fails", "FAIL", missing_evidence_fails),
        ("good command evidence passes", "PASS", good_command_evidence_passes),
        ("unreviewed evidence fails", "FAIL", unreviewed_evidence_fails),
        ("nonzero command evidence fails", "FAIL", nonzero_command_evidence_fails),
        ("tampered artifact fails", "FAIL", tampered_artifact_fails),
        ("missing artifact fails", "FAIL", missing_artifact_fails),
    ]
    results = [
        ScenarioResult(name, expected_gate, *in_workspace(cli, scenario))
        for name, expected_gate, scenario in scenarios
    ]

    print("Fable Verify Eval Matrix")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status:4} {result.name} (expected gate {result.expected_gate}): {result.detail}")
    passed = sum(1 for result in results if result.ok)
    print(f"Summary: {passed}/{len(results)} scenarios behaved as expected")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
