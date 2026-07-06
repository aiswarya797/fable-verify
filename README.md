<div align="center">
  <h1>
    <img src="assets/fable-verify-logo.svg" width="42" alt="Fable Verify logo">
    Fable Verify
  </h1>

  <p><strong>Proof-of-done verification for AI coding agents.</strong></p>

  <p>
    Your coding agent says <code>done</code>. Fable Verify asks:
    <code>based on what?</code>
  </p>

  <p>
    <a href="https://www.npmjs.com/package/fable-verify"><img src="https://img.shields.io/npm/v/fable-verify" alt="npm version"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
    <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/cloud-not_required-16a34a" alt="No cloud required">
    <img src="https://img.shields.io/badge/check---json-111827" alt="JSON gate">
  </p>

  <p>
    <a href="#install">Install</a> &bull;
    <a href="#best-experience-add-it-to-agentsmd">Best Agent Setup</a> &bull;
    <a href="#quickstart">Quickstart</a> &bull;
    <a href="#github-actions-pr-gate">GitHub Actions PR Gate</a> &bull;
    <a href="#realistic-demo">Realistic Demo</a> &bull;
    <a href="#what-this-is-not">What This Is Not</a>
  </p>
</div>

---

Fable Verify is a local verification gate for AI coding agents, not a model or
sandbox. It turns `done` into acceptance criteria, evidence, review notes, and a
`fable-verify check` verdict.

```text
Goal -> Criteria -> Evidence -> Review -> Check -> Report
```

It works with Codex, Claude Code, Cursor, OpenCode, shell-only agents, and CI
because it only needs repo files and local commands.

## Install

Fable Verify ships as a small npm-distributed Python CLI. It requires Python
3.10 or newer on your `PATH`.

```sh
npm install -g fable-verify
fable-verify init
```

For local development from this repository, call `./bin/fable-verify`.

## Best Experience: Add It To AGENTS.md

Fable Verify works best when it is part of the agent's normal completion loop,
not something a user has to remember to request. Add a repo instruction such as
this to `AGENTS.md`, `CLAUDE.md`, or your agent runner's system instructions:

```md
Before claiming any coding task is done, fixed, correct, verified, ready for
review, or safe to merge, use Fable Verify. If the user asks "how do you know?",
answer from current Fable Verify evidence: acceptance criteria, evidence IDs,
commands or artifacts, review notes, and the `fable-verify check` verdict.

If no current Fable Verify proof exists, do not answer from memory alone. Create
or collect the missing evidence, run the verification gate, or say the work is
not verified yet and report the exact missing criteria or blockers.
```

The skill description helps agents auto-load Fable Verify for completion-proof
questions. A repo instruction makes that behavior mandatory for the project, and
a CI or PR gate can make skipped proof visible before merge.

## What It Does

Fable Verify creates a `.fable-verify/` workspace in your repository:

```text
.fable-verify/
  goal.md
  acceptance.json
  ledger.json
  reviews.json
  evidence/
    index.json
  reports/
```

Agents and humans use these files to:

- turn a vague goal into explicit acceptance criteria;
- track a live requirements ledger;
- attach evidence from tests, builds, lints, screenshots, browser checks, logs,
  file reads, diffs, and user confirmation;
- inspect evidence artifacts and record explicit `supports`,
  `does-not-support`, or `unclear` review verdicts;
- run a machine-checkable verification gate;
- emit JSON gate output for supervisors, CI jobs, and PR workflows;
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
- **Explicit self-review:** current evidence must have a latest applicable
  review with verdict `supports`, non-empty notes, and matching artifact hash
  and byte size from the time of review.
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
capture timestamp metadata. Every review records the SHA-256 hash and byte size
that the reviewer observed. If the artifact is edited or deleted after capture
or review, or if a legacy evidence record lacks hash/size metadata,
`fable-verify check` marks it tampered, missing, or legacy unverified and fails
the gate.

This is artifact tamper evidence, not cryptographic non-repudiation. The
repo-local JSON files are still editable by someone with write access, so use
normal code review, CI, and repository controls when you need an immutable or
signed audit log.

Fable Verify checks proof shape, ownership, command exit status, artifact
integrity, and explicit review records. It does not prove that a screenshot
semantically shows the right UI or that a diff implements the correct product
decision; agents or humans still inspect the attached artifacts and record that
judgment in `reviews.json`.

## What This Is Not

Fable Verify is not a sandbox, not an edit blocker, and not a replacement for CI
or security review. It verifies whether an agent has enough repo-local evidence
to support a completion claim. You should still run your normal tests, reviews,
security checks, and release process.

## Outreach And PR Gate Positioning

Use the short version honestly: Fable Verify records proof of completion for
coding agents. It stores acceptance criteria, evidence artifacts, explicit
review verdicts, artifact hashes, machine-readable gate output, and final
reports in repo-local files.

It does not enforce permissions, sandbox an agent, prevent edits, or replace CI,
code review, security review, or existing permission systems. It complements
those controls by making the final "done" claim auditable.

See [`docs/outreach-positioning.md`](docs/outreach-positioning.md) for safe
positioning snippets and [`docs/github-actions.md`](docs/github-actions.md) for
using `fable-verify check --json` as a PR gate.

## Enforcement Boundary

Fable Verify currently verifies completion evidence and evidence-backed
self-review. It checks acceptance criteria, current-plan evidence attachment,
evidence ownership, artifact existence, artifact integrity, command exit codes,
weak evidence labels, review verdicts and notes, review-time artifact integrity,
and unresolved blockers before a final completion claim.

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
fable-verify show EV-001
fable-verify review --criterion AC-001 --evidence EV-001 --verdict supports --notes "Reproduction test log shows exit code 0 and the expected redirect bug output."
fable-verify show EV-002
fable-verify review --criterion AC-001 --evidence EV-002 --verdict supports --notes "Log output documents the pre-fix redirect loop observation."
fable-verify show EV-003
fable-verify review --criterion AC-002 --evidence EV-003 --verdict supports --notes "Diff evidence output supports that the login redirect fix was reviewed."
fable-verify show EV-004
fable-verify review --criterion AC-003 --evidence EV-004 --verdict supports --notes "Regression test log shows the verification command exited 0."
fable-verify show EV-005
fable-verify review --criterion AC-004 --evidence EV-005 --verdict supports --notes "Diff review output supports that the change was scoped."
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

The planner includes lightweight templates for common coding-agent workflows:
bug fixes, UI changes, refactors, docs-only changes, and autonomous PR handoffs.
They are starting points, not a substitute for reviewing and sharpening the
criteria for the actual task.

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

### `fable-verify show`

Prints evidence metadata before review:

- evidence ID, owning criterion, type, strength, summary;
- command and exit code, when present;
- artifact path, recorded hash/size, current hash/size, and integrity status;
- latest review status, when present;
- a text preview for log-like UTF-8 artifacts.

For screenshots and other images, `show` prints metadata and the artifact path.
It does not claim to visually understand the image; the reviewer must inspect
the file with an appropriate viewer.

Example:

```sh
./bin/fable-verify show EV-001
```

### `fable-verify review`

Records an explicit review verdict for one evidence artifact against one
acceptance criterion:

```sh
./bin/fable-verify review \
  --criterion AC-003 \
  --evidence EV-001 \
  --verdict supports \
  --notes "Test log shows python -m unittest completed with exit code 0."
```

Supported verdicts are:

```text
supports does-not-support unclear
```

Only `supports` can satisfy `check`. Review notes are required. The command
rejects unknown criteria, unknown evidence, evidence owned by a different
criterion, evidence not attached to the criterion, and missing artifacts. Each
review records the current artifact SHA-256 hash and byte size, so later
artifact mutation invalidates the review.

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
- any current evidence has no review, an empty review note, or a latest review
  verdict other than `supports`;
- the latest supporting review's recorded artifact hash/size no longer matches
  the current artifact;
- any criterion relies on weak evidence to mask missing strong proof;
- `.fable-verify/ledger.json` contains unresolved blockers.

Use `--json` when a supervisor, CI job, or PR workflow needs machine-readable
output:

```sh
fable-verify check --json
```

The JSON output includes:

- `verdict`: `VERIFIED`, `PARTIALLY VERIFIED`, or `NOT VERIFIED`;
- `allowed`: whether the final completion claim is currently allowed;
- `passing_criteria` and `total_criteria`;
- `missing_evidence`;
- `blockers`;
- `issues`;
- `criteria` with criterion IDs, descriptions, required evidence, attached
  evidence, and current status.

### `fable-verify report`

Generates a Markdown report in `.fable-verify/reports/` with:

- original goal;
- acceptance criteria table;
- current proof evidence table containing only evidence attached to the current
  acceptance criteria;
- current proof commands and exit codes;
- proof strength, artifact size, SHA-256 hash, and integrity status;
- semantic evidence review table with review verdicts, notes, artifact
  integrity, and review-time integrity;
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
7. Inspect each current evidence artifact with `fable-verify show EV-###`, or an
   equivalent artifact viewer for screenshots/images.
8. Record a review for each current evidence artifact with
   `fable-verify review`, using `supports`, `does-not-support`, or `unclear`
   and concrete notes.
9. Run `fable-verify check` before claiming completion. `check` alone is not
   enough unless the evidence has already been inspected and reviewed.
10. If the gate passes, run `fable-verify report` and summarize the current proof
   evidence.
11. If the gate fails, continue working or report exactly what remains
    unverified.

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

## Review Record Schema

Review records are stored in `.fable-verify/reviews.json`. The latest review for
a criterion/evidence pair is the one used by `check`.

```json
{
  "id": "RV-001",
  "criterion_id": "AC-001",
  "criterion_description": "Relevant automated verification passes.",
  "evidence_id": "EV-001",
  "evidence_type": "test",
  "verdict": "supports",
  "notes": "Test log shows npm test completed with exit code 0.",
  "reviewed_at": "2026-07-03T00:00:00+00:00",
  "reviewer_kind": "agent",
  "reviewer_name": "codex",
  "artifact_path": ".fable-verify/evidence/EV-001.log",
  "artifact_sha256": "f4b2...",
  "artifact_size": 1234,
  "artifact_integrity": "sha256"
}
```

The review is a recorded reviewer judgment. It is not an assertion that Fable
Verify semantically understood the artifact.

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
"$FABLE_VERIFY" show EV-001
"$FABLE_VERIFY" review --criterion AC-001 --evidence EV-001 --verdict supports --notes "Reproduction test log shows exit code 0 and the expected redirect bug output."
"$FABLE_VERIFY" show EV-002
"$FABLE_VERIFY" review --criterion AC-001 --evidence EV-002 --verdict supports --notes "Log output documents the pre-fix redirect loop observation."
"$FABLE_VERIFY" show EV-003
"$FABLE_VERIFY" review --criterion AC-002 --evidence EV-003 --verdict supports --notes "Diff evidence output supports that the login redirect fix was reviewed."
"$FABLE_VERIFY" show EV-004
"$FABLE_VERIFY" review --criterion AC-003 --evidence EV-004 --verdict supports --notes "Regression test log shows the verification command exited 0."
"$FABLE_VERIFY" show EV-005
"$FABLE_VERIFY" review --criterion AC-004 --evidence EV-005 --verdict supports --notes "Diff review output supports that the change was scoped."
"$FABLE_VERIFY" check
"$FABLE_VERIFY" report
```

See [`examples/simple-fix/README.md`](examples/simple-fix/README.md) for a
demo-sized scenario and
[`examples/realistic-pr-verification/README.md`](examples/realistic-pr-verification/README.md)
for a temporary git repo demo that records real `git diff`, `npm test`,
screenshot, review, JSON check, and report evidence.

Run the realistic demo from this repository:

```sh
npm run demo:realistic
```

## Development

Run the test suite:

```sh
npm test
```

Run the local doctor to confirm the CLI can run from the current checkout:

```sh
npm run doctor
```

Run a full happy-path smoke check in a temporary repository:

```sh
npm run smoke
```

Run the realistic PR-verification demo:

```sh
npm run demo:realistic
```

Run the canned evaluation matrix. It intentionally verifies both expected
passing and expected failing gates:

```sh
npm run eval:matrix
```

Before publicizing a release candidate, run the complete local preflight:

```sh
npm run preflight
```

That expands to unit tests, doctor, smoke, eval matrix, and package dry-run.
For the Codex skill check, run the skill validator from your Codex home against
the `fable-verify/` skill directory.

```sh
python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py fable-verify
```

For PR gate examples, see
[`docs/github-actions.md`](docs/github-actions.md). For outreach-safe wording,
see [`docs/outreach-positioning.md`](docs/outreach-positioning.md).

## Release Hygiene

`.fable-verify/` is generated runtime state and is listed in `.gitignore`.
Keep dogfood evidence local, or publish a deliberately curated and sanitized
artifact under `examples/` or docs. Release-visible files should not contain
local machine paths such as user home directories or temporary OS folders.
