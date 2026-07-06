#!/usr/bin/env python3
"""Run a realistic PR-verification demo in a temporary git repository."""

from __future__ import annotations

import json
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


def run(
    command: list[str],
    cwd: Path,
    expect: int = 0,
    display_command: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    display = display_command or command
    print("$ " + " ".join(shlex.quote(part) for part in display))
    print(f"exit: {result.returncode}")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != expect:
        raise SystemExit(f"expected exit {expect}, got {result.returncode}: {' '.join(command)}")
    return result


def run_cli(cli: str, cwd: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    return run([cli, *args], cwd, expect=expect, display_command=["fable-verify", *args])


def write_baseline_project(cwd: Path) -> None:
    (cwd / ".gitignore").write_text(".fable-verify/\n", encoding="utf-8")
    (cwd / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "  <body>",
                "    <main>",
                "      <h1>Welcome</h1>",
                "      <p>Proof gate pending.</p>",
                "    </main>",
                "  </body>",
                "</html>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (cwd / "package.json").write_text(
        json.dumps(
            {
                "name": "fable-verify-realistic-demo",
                "private": True,
                "scripts": {"test": "node test/home.test.js"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    test_dir = cwd / "test"
    test_dir.mkdir()
    (test_dir / "home.test.js").write_text(
        "\n".join(
            [
                "const assert = require('node:assert/strict');",
                "const fs = require('node:fs');",
                "",
                "const html = fs.readFileSync('index.html', 'utf8');",
                "assert.match(html, /Welcome/);",
                "assert.match(html, /Proof gate pending/);",
                "console.log('baseline homepage assertions passed');",
                "",
            ]
        ),
        encoding="utf-8",
    )


def apply_ui_change(cwd: Path) -> Path:
    (cwd / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "  <body>",
                "    <main>",
                "      <h1>Proof gate ready</h1>",
                "      <p>Every completion claim needs evidence, review, and a report.</p>",
                "    </main>",
                "  </body>",
                "</html>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (cwd / "test" / "home.test.js").write_text(
        "\n".join(
            [
                "const assert = require('node:assert/strict');",
                "const fs = require('node:fs');",
                "",
                "const html = fs.readFileSync('index.html', 'utf8');",
                "assert.match(html, /Proof gate ready/);",
                "assert.match(html, /evidence, review, and a report/);",
                "console.log('updated homepage assertions passed');",
                "",
            ]
        ),
        encoding="utf-8",
    )
    artifacts = cwd / "artifacts"
    artifacts.mkdir()
    screenshot = artifacts / "proof-gate-after.svg"
    screenshot.write_text(
        "\n".join(
            [
                '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">',
                '  <rect width="960" height="540" fill="#f7fafc"/>',
                '  <rect x="96" y="120" width="768" height="300" rx="12" fill="#ffffff" stroke="#1f2937"/>',
                '  <text x="140" y="230" font-family="Arial" font-size="48" fill="#111827">Proof gate ready</text>',
                '  <text x="140" y="300" font-family="Arial" font-size="28" fill="#374151">Evidence, review, and report captured.</text>',
                "</svg>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return screenshot


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
    with tempfile.TemporaryDirectory(prefix="fable-verify-realistic-demo-") as temp:
        cwd = Path(temp)
        print(f"Temporary demo repo: {cwd}")
        run(["git", "init"], cwd)
        run(["git", "config", "user.email", "demo@example.invalid"], cwd)
        run(["git", "config", "user.name", "Fable Verify Demo"], cwd)
        write_baseline_project(cwd)
        run(["git", "add", "."], cwd)
        run(["git", "commit", "-m", "baseline demo app"], cwd)

        screenshot = apply_ui_change(cwd)
        run_cli(cli, cwd, "init")
        run_cli(cli, cwd, "plan", "UI change: add proof gate ready homepage")
        run_cli(
            cli,
            cwd,
            "add-evidence",
            "--criterion",
            "AC-001",
            "--type",
            "diff",
            "--command",
            "git diff -- index.html test/home.test.js",
        )
        run_cli(
            cli,
            cwd,
            "add-evidence",
            "--criterion",
            "AC-002",
            "--type",
            "screenshot",
            "--artifact-path",
            str(screenshot),
            "--summary",
            "SVG screenshot artifact of the updated homepage state.",
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
            "npm test",
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
            "git status --short && git diff --stat",
        )
        review_evidence(cli, cwd, "AC-001", "EV-001", "git diff shows the homepage and test updates for the proof gate UI.")
        review_evidence(cli, cwd, "AC-002", "EV-002", "Reviewer inspected the SVG screenshot artifact and it shows the proof gate ready state.")
        review_evidence(cli, cwd, "AC-003", "EV-003", "npm test completed with exit code 0 and updated homepage assertions passed.")
        review_evidence(cli, cwd, "AC-004", "EV-004", "git status and diff stat show the scoped demo UI/test files changed.")
        check = run_cli(cli, cwd, "check", "--json")
        payload = json.loads(check.stdout)
        if payload["verdict"] != "VERIFIED":
            raise SystemExit(f"expected VERIFIED, got {payload['verdict']}")
        report = run_cli(cli, cwd, "report")
        report_path = cwd / report.stdout.splitlines()[0]
        if not report_path.is_file():
            raise SystemExit(f"report was not created: {report_path}")
        print(f"Realistic demo passed; report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
