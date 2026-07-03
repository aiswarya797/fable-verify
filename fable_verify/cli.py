"""Command line implementation for Fable Verify.

The code intentionally favors plain files and small functions over cleverness.
Fable Verify should be easy for any coding agent or human maintainer to inspect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FABLE_DIR = ".fable-verify"
GOAL_FILE = "goal.md"
ACCEPTANCE_FILE = "acceptance.json"
LEDGER_FILE = "ledger.json"
EVIDENCE_DIR = "evidence"
REPORTS_DIR = "reports"
EVIDENCE_INDEX_FILE = "index.json"

SUPPORTED_EVIDENCE_TYPES = {
    "test",
    "build",
    "lint",
    "typecheck",
    "diff",
    "screenshot",
    "browser",
    "log",
    "file-read",
    "manual-user-confirmation",
}

COMMAND_LIKE_EVIDENCE_TYPES = {"test", "build", "lint", "typecheck"}
WEAK_EVIDENCE_TYPES = {"log", "manual-user-confirmation"}
PROVENANCE_REQUIRED_EVIDENCE_TYPES = {"diff", "browser", "file-read"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}
ATTACHED_ARTIFACT_POLICIES = {"repo-local", "copied-external-to-evidence"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fable_path(root: Path, *parts: str) -> Path:
    return root / FABLE_DIR / Path(*parts)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def rel_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def is_inside_root(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def default_goal() -> str:
    return "# Goal\n\nDescribe the user goal here, then run `fable-verify plan`.\n"


def default_acceptance() -> dict[str, Any]:
    return {"criteria": []}


def default_ledger() -> dict[str, Any]:
    return {
        "goal": "",
        "status": "active",
        "acceptance_criteria": [],
        "work_log": [],
        "blockers": [],
        "final_verdict": None,
    }


def ensure_project(root: Path, force: bool = False) -> list[str]:
    base = fable_path(root)
    created: list[str] = []
    for directory in [base, base / EVIDENCE_DIR, base / REPORTS_DIR]:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(rel_path(root, directory))

    files = {
        base / GOAL_FILE: default_goal(),
        base / ACCEPTANCE_FILE: json.dumps(default_acceptance(), indent=2) + "\n",
        base / LEDGER_FILE: json.dumps(default_ledger(), indent=2) + "\n",
        base / EVIDENCE_DIR / EVIDENCE_INDEX_FILE: json.dumps({"evidence": []}, indent=2) + "\n",
    }
    for path, content in files.items():
        if force or not path.exists():
            write_text(path, content)
            created.append(rel_path(root, path))
    return created


def load_acceptance(root: Path) -> dict[str, Any]:
    return read_json(fable_path(root, ACCEPTANCE_FILE), default_acceptance())


def save_acceptance(root: Path, acceptance: dict[str, Any]) -> None:
    write_json(fable_path(root, ACCEPTANCE_FILE), acceptance)


def load_ledger(root: Path) -> dict[str, Any]:
    ledger = read_json(fable_path(root, LEDGER_FILE), default_ledger())
    for key, value in default_ledger().items():
        ledger.setdefault(key, value)
    return ledger


def save_ledger(root: Path, ledger: dict[str, Any]) -> None:
    write_json(fable_path(root, LEDGER_FILE), ledger)


def load_evidence_index(root: Path) -> dict[str, Any]:
    return read_json(fable_path(root, EVIDENCE_DIR, EVIDENCE_INDEX_FILE), {"evidence": []})


def save_evidence_index(root: Path, index: dict[str, Any]) -> None:
    write_json(fable_path(root, EVIDENCE_DIR, EVIDENCE_INDEX_FILE), index)


def log_work(
    ledger: dict[str, Any],
    action: str,
    criteria: list[str] | None = None,
    evidence: list[str] | None = None,
) -> None:
    ledger.setdefault("work_log", []).append(
        {
            "timestamp": utc_now(),
            "action": action,
            "criteria": criteria or [],
            "evidence": evidence or [],
        }
    )


def compact_goal(goal: str) -> str:
    lines = [line.strip() for line in goal.splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        return ""
    joined = " ".join(lines)
    return joined[:240] + ("..." if len(joined) > 240 else "")


def goal_from_sources(root: Path, args_goal: list[str]) -> str:
    if args_goal:
        return " ".join(args_goal).strip()

    if not sys.stdin.isatty():
        stdin_goal = sys.stdin.read().strip()
        if stdin_goal:
            return stdin_goal

    goal_text = read_text(fable_path(root, GOAL_FILE), "")
    cleaned = compact_goal(goal_text)
    return cleaned


def criterion(ac_id: str, description: str, evidence_required: list[str], notes: str = "") -> dict[str, Any]:
    return {
        "id": ac_id,
        "description": description,
        "evidence_required": evidence_required,
        "status": "pending",
        "evidence": [],
        "notes": notes,
    }


def normalized_goal_tokens(goal: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", goal.lower()))


def is_bug_fix_goal(goal: str) -> bool:
    bug_words = {"bug", "bugfix", "fix", "regression", "broken", "error", "failing", "failure"}
    return bool(normalized_goal_tokens(goal) & bug_words)


def generated_criteria(goal: str) -> list[dict[str, Any]]:
    goal_summary = goal.rstrip(".") if goal else "the requested change"
    notes = "Generated by the no-LLM planner; edit this criterion if the goal needs sharper wording."
    if is_bug_fix_goal(goal_summary):
        return [
            criterion("AC-001", "Bug reproduction or characterization exists.", ["test", "log"], notes),
            criterion("AC-002", f"Fix is implemented for: {goal_summary}.", ["diff"], notes),
            criterion("AC-003", "Relevant automated verification passes.", ["test"], notes),
            criterion("AC-004", "Diff is reviewed and scoped to the requested change.", ["diff"], notes),
        ]
    return [
        criterion("AC-001", "The goal is captured as explicit, testable acceptance criteria.", ["file-read"], notes),
        criterion("AC-002", f"Implementation addresses the stated goal: {goal_summary}.", ["diff"], notes),
        criterion("AC-003", "Relevant verification passes with captured output.", ["test"], notes),
    ]


def next_id(prefix: str, existing: list[dict[str, Any]]) -> str:
    highest = 0
    for item in existing:
        value = str(item.get("id", ""))
        if value.startswith(prefix + "-"):
            try:
                highest = max(highest, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}-{highest + 1:03d}"


@dataclass
class Evaluation:
    allowed: bool
    verdict: str
    issues: list[str]
    passing_criteria: int
    total_criteria: int
    criteria: list[dict[str, Any]]


def resolve_artifact_path(root: Path, artifact_path: str | None) -> Path | None:
    if not artifact_path:
        return None
    path = Path(artifact_path)
    if not path.is_absolute():
        path = root / path
    return path


def evidence_artifact_issue(root: Path, artifact_path: str | None) -> str | None:
    path = resolve_artifact_path(root, artifact_path)
    if not path:
        return "has no artifact_path"
    if not path.exists():
        return f"artifact is missing: {artifact_path}"
    if not path.is_file():
        return f"artifact is not a file: {artifact_path}"
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_integrity_metadata(path: Path) -> dict[str, Any]:
    mime_type, _encoding = mimetypes.guess_type(str(path))
    return {
        "artifact_sha256": file_sha256(path),
        "artifact_size": path.stat().st_size,
        "artifact_mime_type": mime_type or "application/octet-stream",
        "artifact_captured_at": utc_now(),
        "artifact_integrity": "sha256",
    }


def artifact_integrity_status(root: Path, record: dict[str, Any]) -> str:
    artifact_issue = evidence_artifact_issue(root, record.get("artifact_path"))
    if artifact_issue:
        return artifact_issue

    path = resolve_artifact_path(root, record.get("artifact_path"))
    assert path is not None
    expected_hash = record.get("artifact_sha256")
    expected_size = record.get("artifact_size")
    if not expected_hash or expected_size is None:
        return "legacy unverified: missing artifact hash/size metadata"

    actual_size = path.stat().st_size
    try:
        expected_size_int = int(expected_size)
    except (TypeError, ValueError):
        return f"legacy unverified: invalid artifact size metadata {expected_size!r}"
    if expected_size_int != actual_size:
        return f"tampered: artifact size changed from {expected_size} to {actual_size}"

    actual_hash = file_sha256(path)
    if str(expected_hash) != actual_hash:
        return "tampered: artifact hash mismatch"
    return "ok"


def image_like_artifact(path: Path) -> bool:
    try:
        header = path.read_bytes()[:4096]
    except OSError:
        return False
    trimmed = header.lstrip()
    return any(
        [
            header.startswith(b"\x89PNG\r\n\x1a\n"),
            header.startswith(b"\xff\xd8\xff"),
            header.startswith(b"GIF87a"),
            header.startswith(b"GIF89a"),
            header.startswith(b"RIFF") and header[8:12] == b"WEBP",
            header.startswith(b"BM"),
            header.startswith(b"II*\x00"),
            header.startswith(b"MM\x00*"),
            re.match(rb"(?:<\?xml[^>]*>\s*)?(?:<!--.*?-->\s*)*<svg(?:\s|>)", trimmed, re.I | re.S)
            is not None,
        ]
    )


def evidence_strength(evidence_type: str | None) -> str:
    return "weak" if evidence_type in WEAK_EVIDENCE_TYPES else "strong"


def record_has_attached_artifact(record: dict[str, Any]) -> bool:
    return record.get("artifact_policy") in ATTACHED_ARTIFACT_POLICIES


def evidence_record_issues(root: Path, record: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    evidence_type = record.get("type")
    if evidence_type not in SUPPORTED_EVIDENCE_TYPES:
        issues.append(f"unsupported evidence type: {evidence_type}")
        return issues

    expected_strength = evidence_strength(evidence_type)
    recorded_strength = record.get("strength")
    if recorded_strength is not None and recorded_strength != expected_strength:
        issues.append(f"strength metadata mismatch: expected {expected_strength}, found {recorded_strength}")

    command = record.get("command")
    exit_code = record.get("exit_code")
    artifact_path = record.get("artifact_path")

    if evidence_type in COMMAND_LIKE_EVIDENCE_TYPES and not command:
        issues.append(f"type {evidence_type} requires command provenance")
    if command and exit_code not in (0, "0"):
        issues.append(f"command failed with exit code {exit_code}")

    if evidence_type in PROVENANCE_REQUIRED_EVIDENCE_TYPES and not command and not record_has_attached_artifact(record):
        issues.append(
            f"type {evidence_type} requires command output or a real attached artifact; "
            "placeholder evidence is not strong proof"
        )

    artifact_issue = evidence_artifact_issue(root, artifact_path)
    if artifact_issue:
        issues.append(artifact_issue)
    else:
        path = resolve_artifact_path(root, artifact_path)
        assert path is not None
        if evidence_type == "screenshot" and not image_like_artifact(path):
            issues.append("type screenshot requires an image artifact")

        integrity_status = artifact_integrity_status(root, record)
        if integrity_status != "ok":
            issues.append(integrity_status)

    return issues


def evidence_by_id(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(record.get("id")): record for record in index.get("evidence", [])}


def has_unresolved_blockers(ledger: dict[str, Any]) -> list[str]:
    unresolved: list[str] = []
    for blocker in ledger.get("blockers", []):
        if isinstance(blocker, str) and blocker.strip():
            unresolved.append(blocker)
        elif isinstance(blocker, dict) and not blocker.get("resolved", False):
            unresolved.append(str(blocker.get("description") or blocker.get("id") or blocker))
    return unresolved


def criterion_records(
    criterion_data: dict[str, Any],
    index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = evidence_by_id(index)
    records: list[dict[str, Any]] = []
    issues: list[str] = []
    ac_id = str(criterion_data.get("id", "<missing-id>"))
    for evidence_id in criterion_data.get("evidence", []):
        evidence_id = str(evidence_id)
        record = by_id.get(evidence_id)
        if not record:
            issues.append(f"{ac_id} references unknown evidence: {evidence_id}.")
            continue
        owner = str(record.get("criterion_id", "<missing-criterion-id>"))
        if owner != ac_id:
            issues.append(
                f"{ac_id} references evidence {evidence_id} owned by {owner}; "
                "evidence can only satisfy its owning criterion."
            )
            continue
        records.append(record)
    return records, issues


def record_is_usable(root: Path, record: dict[str, Any]) -> bool:
    return not evidence_record_issues(root, record)


def evaluate(root: Path, persist: bool = False) -> Evaluation:
    acceptance = load_acceptance(root)
    ledger = load_ledger(root)
    index = load_evidence_index(root)
    criteria = acceptance.get("criteria", [])
    issues: list[str] = []
    passing = 0

    if not isinstance(criteria, list) or not criteria:
        issues.append("No acceptance criteria are defined.")
        criteria = []

    for item in criteria:
        ac_id = item.get("id", "<missing-id>")
        item_issues: list[str] = []
        required = item.get("evidence_required", [])
        if not required:
            item_issues.append(f"{ac_id} has no evidence_required values.")

        records, reference_issues = criterion_records(item, index)
        item_issues.extend(reference_issues)
        if item.get("status") == "blocked":
            item_issues.append(f"{ac_id} is blocked.")

        for record in records:
            ev_id = record.get("id", "<missing-evidence-id>")
            for issue in evidence_record_issues(root, record):
                item_issues.append(f"{ac_id} evidence {ev_id} {issue}.")

        for required_type in required:
            matches = [
                record
                for record in records
                if record.get("type") == required_type and record_is_usable(root, record)
            ]
            if not matches:
                item_issues.append(f"{ac_id} is missing required evidence type: {required_type}.")

        if item_issues:
            issues.extend(item_issues)
            if item.get("status") == "passed":
                item["status"] = "pending"
        else:
            item["status"] = "passed"
            passing += 1

    for blocker in has_unresolved_blockers(ledger):
        issues.append(f"Unresolved blocker: {blocker}.")

    allowed = not issues and bool(criteria)
    if allowed:
        verdict = "VERIFIED"
    elif passing:
        verdict = "PARTIALLY VERIFIED"
    else:
        verdict = "NOT VERIFIED"

    if persist:
        acceptance["criteria"] = criteria
        save_acceptance(root, acceptance)
        ledger["acceptance_criteria"] = criteria
        ledger["final_verdict"] = verdict
        ledger["status"] = "verified" if allowed else "active"
        save_ledger(root, ledger)

    return Evaluation(allowed, verdict, issues, passing, len(criteria), criteria)


def command_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    created = ensure_project(root, force=args.force)
    if created:
        print("Initialized Fable Verify:")
        for item in created:
            print(f"  {item}")
    else:
        print("Fable Verify already initialized; no files changed.")
    return 0


def command_plan(args: argparse.Namespace) -> int:
    root = Path.cwd()
    ensure_project(root)
    goal = goal_from_sources(root, args.goal)
    if not goal:
        print("No goal provided. Pass a goal, pipe stdin, or edit .fable-verify/goal.md.", file=sys.stderr)
        return 2

    acceptance = load_acceptance(root)
    existing = acceptance.get("criteria", [])
    if isinstance(existing, list) and existing and not args.force:
        ledger = load_ledger(root)
        current_goal = ledger.get("goal") or compact_goal(read_text(fable_path(root, GOAL_FILE), ""))
        print("Existing acceptance criteria found; plan unchanged.")
        print(
            "The supplied goal was not recorded because that would leave old criteria "
            "and evidence attached to a new goal."
        )
        print("Use --force to regenerate criteria, or manually edit .fable-verify/acceptance.json.")
        print(f"Current goal: {current_goal or '(not set)'}")
        print(f"Supplied goal: {goal}")
        return 0

    write_text(fable_path(root, GOAL_FILE), f"# Goal\n\n{goal}\n")
    acceptance["criteria"] = generated_criteria(goal)
    save_acceptance(root, acceptance)
    print(f"Generated {len(acceptance['criteria'])} acceptance criteria.")

    ledger = load_ledger(root)
    ledger["goal"] = goal
    ledger["acceptance_criteria"] = load_acceptance(root).get("criteria", [])
    ledger["status"] = "active"
    ledger["final_verdict"] = None
    log_work(ledger, "Created or updated acceptance plan.", [item["id"] for item in ledger["acceptance_criteria"]])
    save_ledger(root, ledger)
    print(f"Goal: {goal}")
    print("Next: edit .fable-verify/acceptance.json if needed, then add evidence.")
    return 0


def command_status(args: argparse.Namespace) -> int:
    root = Path.cwd()
    ensure_project(root)
    ledger = load_ledger(root)
    acceptance = load_acceptance(root)
    evaluation = evaluate(root, persist=False)
    goal = ledger.get("goal") or compact_goal(read_text(fable_path(root, GOAL_FILE), ""))
    total = evaluation.total_criteria
    missing = [issue for issue in evaluation.issues if "missing required evidence" in issue]
    blockers = has_unresolved_blockers(ledger)

    print(f"Goal: {goal or '(not set)'}")
    print(f"Acceptance criteria: {total}")
    print(f"Passing criteria: {evaluation.passing_criteria}")
    print(f"Missing evidence: {len(missing)}")
    print(f"Blockers: {len(blockers)}")
    print(f"Completion allowed: {'yes' if evaluation.allowed else 'no'}")
    if args.verbose:
        for item in acceptance.get("criteria", []):
            print(f"- {item.get('id')}: {item.get('status')} - {item.get('description')}")
        for issue in evaluation.issues:
            print(f"  ! {issue}")
    return 0


def run_evidence_command(command: str, artifact: Path) -> int:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    ended = utc_now()
    content = [
        f"$ {command}",
        f"started_at: {started}",
        f"finished_at: {ended}",
        f"exit_code: {result.returncode}",
        "",
        "## stdout",
        result.stdout,
        "",
        "## stderr",
        result.stderr,
    ]
    write_text(artifact, "\n".join(content))
    return int(result.returncode)


def safe_artifact_name(evidence_id: str, source: Path) -> str:
    source_name = source.name or "artifact"
    cleaned = "".join(char if char.isalnum() or char in ".-_" else "-" for char in source_name)
    cleaned = cleaned.strip(".") or "artifact"
    return f"{evidence_id}-{cleaned}"


def prepare_artifact_path(root: Path, evidence_id: str, artifact_arg: str | None) -> tuple[Path, str, dict[str, Any]]:
    if not artifact_arg:
        artifact = fable_path(root, EVIDENCE_DIR, f"{evidence_id}.log")
        return artifact, rel_path(root, artifact), {"artifact_policy": "created-repo-local"}

    source = Path(artifact_arg)
    if not source.is_absolute():
        source = root / source
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(str(source))
    if not source.is_file():
        raise IsADirectoryError(str(source))

    if is_inside_root(root, source):
        return source, rel_path(root, source), {"artifact_policy": "repo-local"}

    destination = fable_path(root, EVIDENCE_DIR, safe_artifact_name(evidence_id, source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return (
        destination,
        rel_path(root, destination),
        {
            "artifact_policy": "copied-external-to-evidence",
            "source_artifact_path": str(source),
        },
    )


def evidence_input_policy_issue(evidence_type: str, has_command: bool, has_artifact: bool) -> str | None:
    if evidence_type in COMMAND_LIKE_EVIDENCE_TYPES and not has_command:
        return (
            f"{evidence_type} evidence requires command provenance. "
            "Pass --command; passive artifacts do not prove executable work."
        )
    if evidence_type == "screenshot" and not has_artifact:
        return "screenshot evidence requires a real attached image artifact via --artifact-path."
    if evidence_type in PROVENANCE_REQUIRED_EVIDENCE_TYPES and not has_command and not has_artifact:
        return (
            f"{evidence_type} evidence requires --command output or a real attached artifact. "
            "Fable Verify will not create placeholder proof for this evidence type."
        )
    return None


def command_add_evidence(args: argparse.Namespace) -> int:
    root = Path.cwd()
    ensure_project(root)
    acceptance = load_acceptance(root)
    criteria = acceptance.get("criteria", [])
    criterion_data = next((item for item in criteria if item.get("id") == args.criterion), None)
    if criterion_data is None:
        print(f"Unknown criterion: {args.criterion}", file=sys.stderr)
        return 2

    if args.type not in SUPPORTED_EVIDENCE_TYPES:
        print(f"Unsupported evidence type: {args.type}", file=sys.stderr)
        return 2

    policy_issue = evidence_input_policy_issue(args.type, bool(args.command), bool(args.artifact_path))
    if policy_issue:
        print(policy_issue, file=sys.stderr)
        return 2

    if args.command and args.artifact_path and args.exit_code is None:
        print(
            "Externally captured command evidence requires --exit-code when --artifact-path is supplied.",
            file=sys.stderr,
        )
        return 2

    index = load_evidence_index(root)
    evidence_id = next_id("EV", index.get("evidence", []))
    exit_code: int | None = args.exit_code

    try:
        artifact, artifact_path, artifact_metadata = prepare_artifact_path(root, evidence_id, args.artifact_path)
    except FileNotFoundError as exc:
        print(f"Missing artifact path: {exc}", file=sys.stderr)
        return 2
    except IsADirectoryError as exc:
        print(f"Artifact paths must point to files, not directories: {exc}", file=sys.stderr)
        return 2

    if args.type == "screenshot" and not image_like_artifact(artifact):
        if artifact_metadata.get("artifact_policy") == "copied-external-to-evidence":
            artifact.unlink(missing_ok=True)
        print(
            "screenshot evidence requires an image artifact "
            f"({', '.join(sorted(IMAGE_EXTENSIONS))}) or a recognizable image header.",
            file=sys.stderr,
        )
        return 2

    if args.command:
        if args.exit_code is None and not args.artifact_path:
            exit_code = run_evidence_command(args.command, artifact)
        elif not artifact.exists():
            write_text(
                artifact,
                "\n".join(
                    [
                        f"$ {args.command}",
                        f"recorded_at: {utc_now()}",
                        f"exit_code: {exit_code}",
                        "",
                        args.summary or "Command evidence recorded from an external run.",
                    ]
                ),
            )
    elif not args.artifact_path:
        write_text(
            artifact,
            "\n".join(
                [
                    f"evidence_id: {evidence_id}",
                    f"criterion_id: {args.criterion}",
                    f"type: {args.type}",
                    f"created_at: {utc_now()}",
                    "",
                    args.summary or "Evidence recorded.",
                ]
            ),
        )

    artifact_integrity = artifact_integrity_metadata(artifact)

    record = {
        "id": evidence_id,
        "criterion_id": args.criterion,
        "type": args.type,
        "command": args.command,
        "exit_code": exit_code,
        "artifact_path": artifact_path,
        "summary": args.summary or evidence_summary(args.type, args.command, exit_code),
        "created_at": utc_now(),
        "strength": evidence_strength(args.type),
    }
    record.update(artifact_metadata)
    record.update(artifact_integrity)

    index.setdefault("evidence", []).append(record)
    save_evidence_index(root, index)
    criterion_data.setdefault("evidence", [])
    if evidence_id not in criterion_data["evidence"]:
        criterion_data["evidence"].append(evidence_id)
    save_acceptance(root, acceptance)

    ledger = load_ledger(root)
    ledger["acceptance_criteria"] = acceptance.get("criteria", [])
    log_work(ledger, f"Added {args.type} evidence: {record['summary']}", [args.criterion], [evidence_id])
    save_ledger(root, ledger)

    evaluate(root, persist=True)
    print(f"Added evidence {evidence_id} for {args.criterion}: {artifact_path}")
    if args.command:
        print(f"Command exit code: {exit_code}")
    return 0 if exit_code in (0, None) else 1


def evidence_summary(evidence_type: str, command: str | None, exit_code: int | None) -> str:
    if command:
        return f"{evidence_type} command exited {exit_code}"
    if evidence_type == "manual-user-confirmation":
        return "Manual user confirmation recorded as weak evidence"
    return f"{evidence_type} evidence recorded"


def command_check(args: argparse.Namespace) -> int:
    root = Path.cwd()
    ensure_project(root)
    evaluation = evaluate(root, persist=True)
    if evaluation.allowed:
        print("PASS")
        print("Completion allowed: every acceptance criterion has required supporting evidence.")
        return 0
    print("FAIL")
    for issue in evaluation.issues:
        print(f"- {issue}")
    print("Completion allowed: no")
    return 1


def git_changed_files(root: Path) -> str:
    try:
        repo_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if repo_result.returncode != 0:
            return repo_result.stderr.strip() or "Git status unavailable."

        repo_root = Path(repo_result.stdout.strip())
        try:
            pathspec = str(root.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            pathspec = "."

        command = ["git", "status", "--short", "--untracked-files=all"]
        if pathspec != ".":
            command.extend(["--", pathspec])
        result = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return "Git status unavailable."
    if result.returncode != 0:
        return result.stderr.strip() or "Git status unavailable."
    return result.stdout.strip() or "No changed files detected."


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    escaped_rows = [
        [" ".join(str(cell).replace("|", "\\|").splitlines()) for cell in row]
        for row in rows
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in escaped_rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def current_evidence_ids(acceptance: dict[str, Any]) -> set[str]:
    evidence_ids: set[str] = set()
    for item in acceptance.get("criteria", []):
        for evidence_id in item.get("evidence", []):
            evidence_ids.add(str(evidence_id))
    return evidence_ids


def evidence_rows(root: Path, records: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [
            record.get("id", ""),
            record.get("criterion_id", ""),
            record.get("type", ""),
            evidence_strength(record.get("type")),
            str(record.get("exit_code", "")),
            record.get("artifact_path", ""),
            str(record.get("artifact_size", "")),
            record.get("artifact_sha256", ""),
            artifact_integrity_status(root, record),
            record.get("summary", ""),
        ]
        for record in records
    ]


def command_rows(records: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [
            record.get("id", ""),
            record.get("command", ""),
            str(record.get("exit_code", "")),
            record.get("artifact_path", ""),
        ]
        for record in records
        if record.get("command")
    ]


def evidence_type_count_rows(records: list[dict[str, Any]]) -> list[list[str]]:
    counts: dict[str, int] = {}
    for record in records:
        evidence_type = str(record.get("type") or "unknown")
        counts[evidence_type] = counts.get(evidence_type, 0) + 1
    return [[evidence_type, str(count)] for evidence_type, count in sorted(counts.items())]


def command_report(args: argparse.Namespace) -> int:
    root = Path.cwd()
    ensure_project(root)
    evaluation = evaluate(root, persist=True)
    ledger = load_ledger(root)
    acceptance = load_acceptance(root)
    index = load_evidence_index(root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = fable_path(root, REPORTS_DIR, f"report-{timestamp}.md")

    criteria_rows = []
    for item in acceptance.get("criteria", []):
        criteria_rows.append(
            [
                item.get("id", ""),
                item.get("description", ""),
                item.get("status", ""),
                ", ".join(item.get("evidence_required", [])),
                ", ".join(item.get("evidence", [])),
            ]
        )

    by_id = evidence_by_id(index)
    current_ids = current_evidence_ids(acceptance)
    current_records = [
        by_id[evidence_id]
        for evidence_id in sorted(current_ids)
        if evidence_id in by_id
    ]
    historical_records = [
        record
        for record in index.get("evidence", [])
        if str(record.get("id")) not in current_ids
    ]
    current_evidence_rows = evidence_rows(root, current_records)
    current_command_rows = command_rows(current_records)
    historical_preview_records = historical_records[-10:]
    historical_summary_rows = evidence_type_count_rows(historical_records)
    historical_evidence_rows = evidence_rows(root, historical_preview_records)
    historical_count = len(historical_records)
    historical_preview_count = len(historical_preview_records)

    limitations = []
    blockers = has_unresolved_blockers(ledger)
    if blockers:
        limitations.extend([f"Unresolved blocker: {blocker}" for blocker in blockers])
    if evaluation.issues:
        limitations.extend(evaluation.issues)
    if not limitations:
        limitations.append("No known verification limitations recorded.")

    content = "\n".join(
        [
            "# Fable Verify Report",
            "",
            f"Generated: {utc_now()}",
            f"Final verdict: {evaluation.verdict}",
            "",
            "## Original Goal",
            "",
            ledger.get("goal") or compact_goal(read_text(fable_path(root, GOAL_FILE), "")) or "(not set)",
            "",
            "## Acceptance Criteria",
            "",
            markdown_table(
                ["ID", "Description", "Status", "Required Evidence", "Evidence"],
                criteria_rows or [["", "No acceptance criteria defined.", "", "", ""]],
            ),
            "",
            "## Current Proof Evidence",
            "",
            "Only evidence IDs explicitly listed on the current acceptance criteria appear here.",
            "Strong evidence is command-backed or artifact-backed and hash-checked. Weak evidence is self-attested and labeled.",
            "",
            markdown_table(
                ["ID", "Criterion", "Type", "Strength", "Exit Code", "Artifact", "Size", "SHA-256", "Integrity", "Summary"],
                current_evidence_rows or [["", "", "", "", "", "", "", "", "", "No current evidence recorded."]],
            ),
            "",
            "## Current Proof Commands",
            "",
            markdown_table(
                ["Evidence", "Command", "Exit Code", "Artifact"],
                current_command_rows or [["", "No current command evidence recorded.", "", ""]],
            ),
            "",
            "## Historical Evidence",
            "",
            "Historical receipts remain in `.fable-verify/evidence/index.json` but do not support the current goal unless reattached.",
            f"Total historical records: {historical_count}. Showing latest {historical_preview_count} of {historical_count}.",
            "Full historical receipts remain in `.fable-verify/evidence/index.json`.",
            "",
            "### Historical Summary By Type",
            "",
            markdown_table(
                ["Type", "Count"],
                historical_summary_rows or [["", "0"]],
            ),
            "",
            "### Latest Historical Receipts",
            "",
            markdown_table(
                ["ID", "Criterion", "Type", "Strength", "Exit Code", "Artifact", "Size", "SHA-256", "Integrity", "Summary"],
                historical_evidence_rows or [["", "", "", "", "", "", "", "", "", "No historical evidence recorded."]],
            ),
            "",
            "## Files Changed",
            "",
            "```",
            git_changed_files(root),
            "```",
            "",
            "## Known Limitations",
            "",
            "\n".join(f"- {item}" for item in limitations),
            "",
            f"## Final Verdict: {evaluation.verdict}",
            "",
        ]
    )
    write_text(report_path, content)

    ledger = load_ledger(root)
    ledger["final_verdict"] = evaluation.verdict
    log_work(ledger, f"Generated final report: {rel_path(root, report_path)}")
    save_ledger(root, ledger)
    print(rel_path(root, report_path))
    print(f"Final verdict: {evaluation.verdict}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fable-verify",
        description="Portable acceptance-criteria and evidence gate for coding agents.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_parser = subcommands.add_parser("init", help="Create .fable-verify files without overwriting them.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing Fable Verify files.")
    init_parser.set_defaults(func=command_init)

    plan_parser = subcommands.add_parser("plan", help="Create or update acceptance criteria from a goal.")
    plan_parser.add_argument("goal", nargs="*", help="Goal text. If omitted, stdin or .fable-verify/goal.md is used.")
    plan_parser.add_argument("--force", action="store_true", help="Regenerate existing acceptance criteria.")
    plan_parser.set_defaults(func=command_plan)

    status_parser = subcommands.add_parser("status", help="Print concise verification status.")
    status_parser.add_argument("--verbose", action="store_true", help="Print criteria and gate issues.")
    status_parser.set_defaults(func=command_status)

    evidence_parser = subcommands.add_parser("add-evidence", help="Attach evidence to an acceptance criterion.")
    evidence_parser.add_argument("--criterion", "-c", required=True, help="Acceptance criterion ID, such as AC-001.")
    evidence_parser.add_argument("--type", "-t", required=True, choices=sorted(SUPPORTED_EVIDENCE_TYPES))
    evidence_parser.add_argument("--command", help="Command to run and capture as evidence.")
    evidence_parser.add_argument("--exit-code", type=int, help="Exit code for externally captured command evidence.")
    evidence_parser.add_argument("--artifact-path", help="Existing artifact path to record instead of creating a log.")
    evidence_parser.add_argument("--summary", help="Short evidence summary.")
    evidence_parser.set_defaults(func=command_add_evidence)

    check_parser = subcommands.add_parser("check", help="Run the verification gate.")
    check_parser.set_defaults(func=command_check)

    report_parser = subcommands.add_parser("report", help="Generate a final Markdown evidence report.")
    report_parser.set_defaults(func=command_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
