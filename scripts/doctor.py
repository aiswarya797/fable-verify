#!/usr/bin/env python3
"""Preflight checks for running Fable Verify in the current repository."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


MIN_PYTHON = (3, 10)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STATE_FILES = [
    Path(".fable-verify/goal.md"),
    Path(".fable-verify/acceptance.json"),
    Path(".fable-verify/ledger.json"),
    Path(".fable-verify/evidence/index.json"),
]


@dataclass
class Check:
    status: str
    name: str
    detail: str


def resolve_cli() -> str | None:
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
    return None


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def git_root(cwd: Path) -> Path | None:
    git = shutil.which("git")
    if not git:
        return None
    result = run([git, "rev-parse", "--show-toplevel"], cwd)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def check_python() -> Check:
    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info >= MIN_PYTHON:
        return Check("PASS", "Python version", f"{version} >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}")
    return Check("FAIL", "Python version", f"{version} is below {MIN_PYTHON[0]}.{MIN_PYTHON[1]}")


def check_cli(cwd: Path) -> Check:
    cli = resolve_cli()
    if not cli:
        return Check("FAIL", "fable-verify availability", "not found via FABLE_VERIFY_BIN, repo bin, or PATH")
    result = run([cli, "--help"], cwd)
    if result.returncode == 0:
        return Check("PASS", "fable-verify availability", cli)
    detail = result.stderr.strip() or result.stdout.strip() or f"{cli} --help exited {result.returncode}"
    return Check("FAIL", "fable-verify availability", detail)


def check_writable(cwd: Path) -> Check:
    try:
        with tempfile.NamedTemporaryFile(
            dir=cwd,
            prefix=".fable-verify-doctor-",
            delete=False,
        ) as handle:
            path = Path(handle.name)
            handle.write(b"ok\n")
        path.unlink(missing_ok=True)
    except OSError as exc:
        return Check("FAIL", "writable repository", str(exc))
    return Check("PASS", "writable repository", str(cwd))


def json_state_issue(path: Path) -> str | None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"invalid JSON in {path}: {exc}"
    except OSError as exc:
        return f"cannot read {path}: {exc}"
    return None


def check_state(cwd: Path) -> Check:
    state_dir = cwd / ".fable-verify"
    if not state_dir.exists():
        return Check("WARN", ".fable-verify state", "not initialized yet; run fable-verify init")
    if not state_dir.is_dir():
        return Check("FAIL", ".fable-verify state", ".fable-verify exists but is not a directory")

    missing = [str(path) for path in EXPECTED_STATE_FILES if not (cwd / path).exists()]
    if missing:
        return Check("FAIL", ".fable-verify state", "missing expected files: " + ", ".join(missing))

    for path in [
        cwd / ".fable-verify/acceptance.json",
        cwd / ".fable-verify/ledger.json",
        cwd / ".fable-verify/evidence/index.json",
    ]:
        issue = json_state_issue(path)
        if issue:
            return Check("FAIL", ".fable-verify state", issue)
    return Check("PASS", ".fable-verify state", "initialized and readable")


def check_ignored(cwd: Path) -> Check:
    git = shutil.which("git")
    if not git:
        return Check("WARN", ".fable-verify ignored", "git is not available; cannot verify ignore rules")
    root = git_root(cwd)
    if not root:
        return Check("WARN", ".fable-verify ignored", "not inside a git work tree")

    state_path = cwd / ".fable-verify"
    try:
        pathspec = str(state_path.resolve().relative_to(root))
    except ValueError:
        pathspec = str(state_path)
    if not pathspec.endswith("/"):
        pathspec += "/"
    result = run([git, "check-ignore", "-q", "--", pathspec], root)
    if result.returncode == 0:
        return Check("PASS", ".fable-verify ignored", pathspec)
    return Check("FAIL", ".fable-verify ignored", f"{pathspec} is not ignored by git")


def main() -> int:
    cwd = Path.cwd().resolve()
    checks = [
        check_python(),
        check_cli(cwd),
        check_writable(cwd),
        check_state(cwd),
        check_ignored(cwd),
    ]

    print("Fable Verify Doctor")
    for check in checks:
        print(f"{check.status:4} {check.name}: {check.detail}")

    counts = {status: sum(1 for check in checks if check.status == status) for status in ("PASS", "WARN", "FAIL")}
    print(f"Summary: {counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} failed")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
