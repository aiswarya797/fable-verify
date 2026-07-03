# Fable Verify

Fable Verify is a repo-local workflow and verification toolkit for coding agents.
It is not a model and it is not tied to Codex, Claude Code, Cursor, OpenCode, or
any other harness. It gives an agent a plain-file discipline:

```text
Goal -> Spec -> Plan -> Work -> Evidence -> Verification Gate -> Final Report
```

The central rule is simple: when an agent uses Fable Verify as its completion
gate, it should not claim "done" unless every acceptance criterion has
supporting evidence and `fable-verify check` passes. Fable Verify turns agent
work into an auditable proof trail by checking that proof has the right shape,
is attached to the current criterion, and has not changed since capture.

Evidence only counts when it is attached to the current acceptance criterion.
Reports separate current proof from historical receipts. `test`, `build`,
`lint`, and `typecheck` evidence require command provenance and an exit code,
whether Fable Verify runs the command or records an externally captured artifact.
Artifacts are hashed with SHA-256 and byte size at capture time; `check` fails
if a current proof artifact is missing, mutated, or lacks integrity metadata.

## Install

Fable Verify ships as a small npm-distributed Python CLI. It requires Python
3.10 or newer on your `PATH`.

```sh
npm install -g fable-verify
fable-verify init
```

For local development from this repository, call `./bin/fable-verify`.

## What It Does

Fable Verify creates a `.fable-verify/` workspace in your repository:

```text
.fable-verify/
  goal.md
  acceptance.json
  ledger.json
  evidence/
    index.json
  reports/
```

Agents and humans use these files to:

- turn a vague goal into explicit acceptance criteria;
- track a live requirements ledger;
- attach evidence from tests, builds, lints, screenshots, browser checks, logs,
  file reads, diffs, and user confirmation;
- run a machine-checkable verification gate;
- generate a final evidence-backed delivery report.

Everything is local. There are no required cloud services and no hidden state.
The generated `.fable-verify/` workspace is ignored by default so local dogfood
proof, machine paths, and transient reports do not ship as product files.

## Why This Is Trustworthy

- **Current-plan proof only:** evidence must be listed in the current
  acceptance criterion's `evidence` array before it can satisfy that criterion.
- **Ownership checks:** a listed evidence ID fails the gate if its
  `criterion_id` belongs to a different criterion.
- **Real file artifacts:** evidence records must point to regular files that
  exist; directories are rejected.
- **Command-like proof is executable:** `test`, `build`, `lint`, and
  `typecheck` evidence must include command provenance.
- **Type-specific proof:** `diff`, `browser`, and `file-read` evidence require
  command output or a real attached artifact; `screenshot` evidence requires a
  real image artifact.
- **Command exits:** command evidence must carry an exit code; nonzero command
  evidence is recorded honestly and fails the gate.
- **Tamper-evident artifacts:** evidence records store SHA-256, byte size, MIME
  hint, and capture time; the gate recomputes hashes before allowing completion.
- **Weak evidence stays weak:** `log` and `manual-user-confirmation` evidence
  are labeled weak and cannot substitute for missing strong proof.
- **Blockers block:** unresolved blockers in `.fable-verify/ledger.json` keep
  completion closed.
- **Repo-local reports:** final reports show current proof first and keep old
  receipts separate as compact historical context.

## What Counts As Proof?

Fable Verify does not treat every receipt as equally strong.

Strong evidence:

- `test`, `build`, `lint`, `typecheck`: must include a command and exit code.
  Completion requires exit code `0`.
- `diff`: must include captured command output, such as `git diff` or
  `git status`, or a real attached patch/status artifact.
- `screenshot`: must include an attached image artifact. The CLI checks for
  recognizable raster image headers or an SVG document root; a renamed text file
  is rejected.
- `browser`: must include command-generated output or an attached artifact such
  as a screenshot, log, trace, or report.
- `file-read`: must include command output or an attached artifact proving what
  was read.

Weak evidence:

- `log` and `manual-user-confirmation` are accepted as self-attested evidence
  and labeled `weak`. They can satisfy criteria that explicitly require those
  types, but they do not replace missing strong evidence like `test`, `diff`,
  `file-read`, or `screenshot`.

Every captured or copied artifact gets SHA-256 hash, byte size, MIME hint, and
capture timestamp metadata. If the artifact is edited or deleted after capture,
or if a legacy evidence record lacks hash/size metadata, `fable-verify check`
marks it tampered, missing, or legacy unverified and fails the gate.

This is artifact tamper evidence, not cryptographic non-repudiation. The
repo-local JSON files are still editable by someone with write access, so use
normal code review, CI, and repository controls when you need an immutable or
signed audit log.

Fable Verify checks proof shape, ownership, command exit status, and artifact
integrity. It does not prove that a screenshot semantically shows the right UI
or that a diff implements the correct product decision; reviewers still inspect
the attached artifacts.

## What This Is Not

Fable Verify is not a sandbox, not an edit blocker, and not a replacement for CI
or security review. It verifies whether an agent has enough repo-local evidence
to support a completion claim. You should still run your normal tests, reviews,
security checks, and release process.

## Enforcement Boundary

Fable Verify currently verifies completion evidence. It checks acceptance
criteria, current-plan evidence attachment, evidence ownership, artifact
existence, artifact integrity, command exit codes, weak evidence labels, and
unresolved blockers before a final completion claim.

It does not currently block file edits before planning, enforce forbidden paths,
install pre-edit hooks, or prevent an agent from ignoring the CLI. Treat it as a
repo-local verification gate and reporting layer, not as a sandbox or policy
engine.

Hard enforcement roadmap: future optional layers could add pre-edit hooks,
worktree apply gates, forbidden-path checks, or CI-required `fable-verify check`
runs. Those are not implemented in this lightweight CLI today.

## Quickstart

With the npm package installed, this creates a throwaway workspace and reaches
`PASS` before generating a report:

```sh
tmpdir="$(mktemp -d)"
cd "$tmpdir"

fable-verify init
fable-verify plan "Bug: login redirect fails"
fable-verify add-evidence --criterion AC-001 --type test --command "python -c \"print('reproduced redirect bug')\""
fable-verify add-evidence --criterion AC-001 --type log --command "python -c \"print('before: redirect loop observed')\""
fable-verify add-evidence --criterion AC-002 --type diff --command "python -c \"print('diff reviewed: login redirect fix')\""
fable-verify add-evidence --criterion AC-003 --type test --command "python -c \"print('redirect regression test passed')\""
fable-verify add-evidence --criterion AC-004 --type diff --command "python -c \"print('scoped diff reviewed')\""
fable-verify check
fable-verify report
```

From a local checkout, replace `fable-verify` with `./bin/fable-verify`.

## CLI Commands

### `fable-verify init`

Creates `.fable-verify/` if it does not already exist. The command is idempotent
and will not overwrite existing files unless you pass `--force`.

### `fable-verify plan`

Reads a goal from a CLI argument, stdin, or `.fable-verify/goal.md`, then creates
acceptance criteria in `.fable-verify/acceptance.json`.

The bundled planner is intentionally boring: without an LLM, it creates a useful
template that an agent or human can refine. If criteria already exist, `plan`
is a no-op unless `--force` is used. A no-op replan does not update
`.fable-verify/goal.md`, `ledger.json`, acceptance criteria, or evidence
attachments, because old proof must not silently appear to support a newly
supplied goal.

Use `--force` only when you intentionally want to replace the current acceptance
plan. Historical receipts remain in `.fable-verify/evidence/index.json`, but the
new generated criteria start with empty evidence lists.

### `fable-verify status`

Prints a concise status view:

- goal summary;
- total acceptance criteria;
- passing criteria;
- missing evidence;
- blockers;
- whether final completion is allowed.

Use `--verbose` for criterion-level issues.

### `fable-verify add-evidence`

Attaches evidence to an acceptance criterion. Supported types:

```text
test build lint typecheck diff screenshot browser log file-read manual-user-confirmation
```

When `--command` is provided without an external `--artifact-path`, Fable Verify
runs the command and captures stdout, stderr, and exit code into
`.fable-verify/evidence/EV-###.log`.

`test`, `build`, `lint`, and `typecheck` are command-like evidence types. They
cannot be added from a passive `--artifact-path` alone. Use `--command`, or use a
different evidence type when the artifact is only a receipt.

`diff`, `browser`, and `file-read` evidence must have command output or a real
attached artifact. Fable Verify will not create placeholder proof for those
types. `screenshot` evidence must attach an image-like file. `log` and
`manual-user-confirmation` may be recorded from a freeform summary, but they are
marked weak.

When `--artifact-path` is provided, the path must already exist and must point to
a regular file, not a directory. Missing paths and directories are rejected
before evidence state is mutated. Repo-local artifacts are recorded by relative
path. Artifacts outside the repo are copied into `.fable-verify/evidence/` and
the original absolute source path is recorded as metadata, so reports remain
repo-local and reviewable.

When `--command` and `--artifact-path` are supplied together, the command was
captured outside Fable Verify, so `--exit-code` is required. Missing exit codes
are rejected before state is mutated. Nonzero externally captured command
evidence may be recorded, but `add-evidence` returns nonzero and `check` fails.

Example:

```sh
./bin/fable-verify add-evidence \
  --criterion AC-003 \
  --type test \
  --command "python -m unittest discover -s tests"
```

Manual user confirmation is weak evidence. It only satisfies a criterion when the
criterion explicitly requires `manual-user-confirmation`.

### `fable-verify check`

Runs the verification gate. It prints `PASS` only when completion is allowed.
It prints `FAIL` with specific missing or invalid evidence otherwise.

The gate fails if:

- any acceptance criterion lacks required evidence;
- required evidence exists in `index.json` but is not attached to the current
  criterion's `evidence` array;
- a criterion references evidence owned by a different criterion;
- `test`, `build`, `lint`, or `typecheck` evidence lacks command provenance;
- `diff`, `browser`, or `file-read` evidence is only a placeholder summary;
- screenshot evidence lacks a real image artifact;
- any required command evidence has a nonzero exit code;
- command evidence captured through `--artifact-path` omits `--exit-code`;
- any evidence artifact path is missing or points to a directory;
- any current proof artifact is missing hash/size metadata or no longer matches
  its recorded SHA-256 and byte size;
- any criterion relies on weak evidence to mask missing strong proof;
- `.fable-verify/ledger.json` contains unresolved blockers.

### `fable-verify report`

Generates a Markdown report in `.fable-verify/reports/` with:

- original goal;
- acceptance criteria table;
- current proof evidence table containing only evidence attached to the current
  acceptance criteria;
- current proof commands and exit codes;
- proof strength, artifact size, SHA-256 hash, and integrity status;
- compact historical evidence section for receipts still present in `index.json`
  but not attached to the current plan, summarized by count and type with at most
  the latest 10 records shown;
- files changed from `git status --short`, when available;
- known limitations;
- final verdict: `VERIFIED`, `PARTIALLY VERIFIED`, or `NOT VERIFIED`.

## How Any Agent Can Use It

1. Read the user's goal.
2. Run `fable-verify init`.
3. Run `fable-verify plan "<goal>"`.
4. Edit `.fable-verify/acceptance.json` until every criterion is testable.
5. Work against the criteria, keeping `.fable-verify/ledger.json` current.
6. Add evidence immediately after each test, build, lint, browser check, file
   read, screenshot, or diff review.
7. Run `fable-verify check` before claiming completion.
8. If the gate passes, run `fable-verify report` and summarize the current proof
   evidence.
9. If the gate fails, continue working or report exactly what remains unverified.

The portable agent instruction file lives at
[`fable-verify/SKILL.md`](fable-verify/SKILL.md).

## Acceptance Criteria Schema

```json
{
  "criteria": [
    {
      "id": "AC-001",
      "description": "User-visible behavior or requirement",
      "evidence_required": ["test", "diff"],
      "status": "pending",
      "evidence": [],
      "notes": ""
    }
  ]
}
```

## Evidence Record Schema

Evidence records are stored in `.fable-verify/evidence/index.json`.
They only count for the current goal when their IDs are attached to the relevant
criterion in `.fable-verify/acceptance.json`.

For `test`, `build`, `lint`, and `typecheck`, the record must include a
`command` and `exit_code`. Strong evidence records must have artifact integrity
metadata. Passive artifact-only records are valid only where the evidence type
allows an attached artifact.

```json
{
  "id": "EV-001",
  "criterion_id": "AC-001",
  "type": "test",
  "command": "npm test",
  "exit_code": 0,
  "artifact_path": ".fable-verify/evidence/EV-001.log",
  "summary": "Unit tests passed",
  "created_at": "2026-07-03T00:00:00+00:00",
  "strength": "strong",
  "artifact_policy": "created-repo-local",
  "artifact_sha256": "f4b2...",
  "artifact_size": 1234,
  "artifact_mime_type": "text/plain",
  "artifact_captured_at": "2026-07-03T00:00:00+00:00",
  "artifact_integrity": "sha256"
}
```

External artifacts copied into the repo also include:

```json
{
  "artifact_policy": "copied-external-to-evidence",
  "source_artifact_path": "/absolute/path/to/original.log"
}
```

## Example Workflow

Goal:

```text
Fix the login redirect bug and prove it works.
```

Acceptance criteria:

| ID | Criterion | Evidence |
| --- | --- | --- |
| AC-001 | Bug reproduction exists. | `test`, `log` |
| AC-002 | Fix is implemented. | `diff` |
| AC-003 | Test passes. | `test` |
| AC-004 | Diff shows scoped change. | `diff` |

Commands:

```sh
tmpdir="$(mktemp -d)"
FABLE_VERIFY="$PWD/bin/fable-verify"
cd "$tmpdir"

"$FABLE_VERIFY" init
"$FABLE_VERIFY" plan "Bug: login redirect fails"
"$FABLE_VERIFY" add-evidence --criterion AC-001 --type test --command "python -c \"print('reproduced redirect bug')\""
"$FABLE_VERIFY" add-evidence --criterion AC-001 --type log --command "python -c \"print('before: redirect loop observed')\""
"$FABLE_VERIFY" add-evidence --criterion AC-002 --type diff --command "python -c \"print('diff reviewed: login redirect fix')\""
"$FABLE_VERIFY" add-evidence --criterion AC-003 --type test --command "python -c \"print('redirect regression test passed')\""
"$FABLE_VERIFY" add-evidence --criterion AC-004 --type diff --command "python -c \"print('scoped diff reviewed')\""
"$FABLE_VERIFY" check
"$FABLE_VERIFY" report
```

See [`examples/simple-fix/README.md`](examples/simple-fix/README.md) for a
demo-sized scenario.

## Development

Run the test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests
```

Run a smoke check:

```sh
tmpdir="$(mktemp -d)"
(cd "$tmpdir" && /absolute/path/to/Fable-Verify/bin/fable-verify init)
```

## Release Hygiene

`.fable-verify/` is generated runtime state and is listed in `.gitignore`.
Keep dogfood evidence local, or publish a deliberately curated and sanitized
artifact under `examples/` or docs. Release-visible files should not contain
local machine paths such as user home directories or temporary OS folders.
