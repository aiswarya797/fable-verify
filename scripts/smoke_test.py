#!/usr/bin/env python3
"""Run the happy-path Fable Verify loop in a temporary repository."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def run_cli(cli: str, cwd: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([cli, *args], cwd=cwd, text=True, capture_output=True, check=False)
    print(f"$ fable-verify {' '.join(args)}")
    print(f"exit: {result.returncode}")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != expect:
        raise SystemExit(f"expected exit {expect}, got {result.returncode} for: {' '.join(args)}")
    return result


def review_evidence(cli: str, cwd: Path, criterion: str, evidence: str, notes: str) -> None:
    run_cli(cli, cwd, "show", evidence)
    run_cli(
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


def main() -> int:
    cli = resolve_cli()
    with tempfile.TemporaryDirectory(prefix="fable-verify-smoke-") as temp:
        cwd = Path(temp)
        print(f"Temporary repo: {cwd}")
        run_cli(cli, cwd, "init")
        run_cli(cli, cwd, "plan", "Bug: login redirect fails")
        run_cli(
            cli,
            cwd,
            "add-evidence",
            "--criterion",
            "AC-001",
            "--type",
            "test",
            "--command",
            python_command("print('reproduced redirect bug')"),
        )
        run_cli(
            cli,
            cwd,
            "add-evidence",
            "--criterion",
            "AC-001",
            "--type",
            "log",
            "--command",
            python_command("print('before: redirect loop observed')"),
        )
        run_cli(
            cli,
            cwd,
            "add-evidence",
            "--criterion",
            "AC-002",
            "--type",
            "diff",
            "--command",
            python_command("print('diff reviewed: login redirect fix')"),
        )
        run_cli(
            cli,
            cwd,
            "add-evidence",
            "--criterion",
            "AC-003",
            "--type",
            "test",
            "--command",
            python_command("print('redirect regression test passed')"),
        )
        run_cli(
            cli,
            cwd,
            "add-evidence",
            "--criterion",
            "AC-004",
            "--type",
            "diff",
            "--command",
            python_command("print('scoped diff reviewed')"),
        )
        review_evidence(cli, cwd, "AC-001", "EV-001", "Test log shows the reproduction command completed with exit code 0.")
        review_evidence(cli, cwd, "AC-001", "EV-002", "Log output describes the pre-fix redirect loop observation.")
        review_evidence(cli, cwd, "AC-002", "EV-003", "Diff evidence log records the implementation review output.")
        review_evidence(cli, cwd, "AC-003", "EV-004", "Verification test log shows the regression check completed with exit code 0.")
        review_evidence(cli, cwd, "AC-004", "EV-005", "Diff review log records a scoped change review.")
        check = run_cli(cli, cwd, "check")
        if "PASS" not in check.stdout:
            raise SystemExit("check did not print PASS")
        report = run_cli(cli, cwd, "report")
        report_path = cwd / report.stdout.splitlines()[0]
        if not report_path.is_file():
            raise SystemExit(f"report was not created: {report_path}")
        print("Smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
