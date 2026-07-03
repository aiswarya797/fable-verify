# Fable Verify Agent Instructions

Use this file when a coding agent should work in a Fable-like discipline using
only repo-local files, scripts, and Markdown instructions.

Fable Verify is harness-agnostic. These instructions apply in Codex, Claude
Code, Cursor, OpenCode, shell-only workflows, and any other environment that can
read files and run local commands.

## Required Loop

Follow this operating loop:

```text
Goal -> Spec -> Plan -> Work -> Evidence -> Verification Gate -> Final Report
```

The agent must not claim completion unless every acceptance criterion has
supporting evidence and `fable-verify check` passes.

Evidence only counts when it is explicitly attached to the current acceptance
criterion's `evidence` array. Reports show current proof separately from
historical receipts. `test`, `build`, `lint`, and `typecheck` evidence must
include command provenance and an exit code. Current proof artifacts are hashed
with SHA-256 and byte size; if an artifact is missing, mutated, or lacks
integrity metadata, the verification gate must fail.

## Enforcement Boundary

Fable Verify verifies completion evidence. It checks whether acceptance criteria
have current-plan evidence attachments, correctly owned evidence records, real
artifact paths, artifact integrity metadata, successful command evidence, no
weak evidence substitutes for technical proof, and no unresolved blockers.

The current CLI does not block edits before planning, enforce forbidden paths,
install pre-edit hooks, or stop an agent that chooses to ignore it. Use it as a
repo-local verification gate and auditable proof trail. Do not describe it as a
sandbox, hook system, or hard edit blocker unless those controls are actually
implemented and tested.

Hard enforcement roadmap: future optional layers could add pre-edit hooks,
worktree apply gates, forbidden-path policies, or CI-required `fable-verify
check` runs. Those controls are not part of the current lightweight CLI.

## Before Starting Work

1. Read the user's goal.
2. Run `fable-verify init`, or create the same `.fable-verify/` structure if the
   command is not on `PATH`.
3. Run `fable-verify plan "<goal>"`, provide the goal through stdin, or write the
   goal to `.fable-verify/goal.md` and run `fable-verify plan`.
4. Review `.fable-verify/acceptance.json`.
5. Refine the criteria until each item is observable, testable, and has explicit
   `evidence_required` values.
6. Ask clarifying questions only when the goal cannot be made testable from the
   available context.

## During Work

Maintain `.fable-verify/ledger.json` as the live requirements ledger.

For every implementation step:

- link the work to one or more acceptance criteria;
- add or update a `work_log` entry;
- record blockers instead of silently working around them;
- add evidence immediately after running tests, builds, lints, typechecks,
  browser checks, screenshot captures, file reads, or diff reviews;
- keep evidence artifact paths real and reviewable.

Do not mark a criterion complete without evidence.

## Evidence Rules

Supported evidence types:

```text
test build lint typecheck diff screenshot browser log file-read manual-user-confirmation
```

`log` and `manual-user-confirmation` are weak/self-attested evidence. They can
satisfy criteria that explicitly require those types, but they must not satisfy
technical criteria that require strong evidence.

`test`, `build`, `lint`, and `typecheck` are command-like evidence types. They
must be captured with command provenance:

- Fable Verify runs the command through `--command` and records stdout, stderr,
  and exit code; or
- the agent records externally captured command evidence with `--command`,
  `--artifact-path`, and `--exit-code`.

Use command evidence whenever possible:

```sh
fable-verify add-evidence --criterion AC-001 --type test --command "npm test"
```

That command captures stdout, stderr, and exit code into
`.fable-verify/evidence/`.

Type-specific proof rules:

- `test`, `build`, `lint`, and `typecheck` require `--command` and a successful
  exit code to pass the gate.
- `diff` requires captured command output or a real attached patch/status
  artifact. Placeholder summaries are not proof.
- `screenshot` requires an attached image artifact. The CLI checks image-like
  extensions or recognizable image headers.
- `browser` requires command-generated output or an attached artifact such as a
  screenshot, log, trace, or report.
- `file-read` requires captured command output or an attached artifact proving
  what was read.
- `log` and `manual-user-confirmation` may use freeform summaries, but they are
  weak evidence.

Do not record placeholder-only evidence for strong types.

If you pass `--artifact-path`, the path must already exist and must be a regular
file, not a directory. Repo-local artifacts are recorded by relative path.
Artifacts outside the repo are copied into `.fable-verify/evidence/`, with the
original absolute source path kept in metadata. Missing artifact paths and
directories must be treated as failed evidence operations, not as evidence to fix
later.

If you pass both `--command` and `--artifact-path`, you are recording command
evidence captured outside Fable Verify. You must also pass `--exit-code`.
Without it, `add-evidence` fails and must not mutate state. A nonzero
`--exit-code` may be recorded, but it returns nonzero and the verification gate
must fail.

Every captured or copied artifact stores SHA-256 hash, byte size, MIME hint, and
capture timestamp metadata. Do not edit evidence artifacts after capture. If an
artifact changes, rerun or reattach the evidence so the hash matches the current
proof. This is artifact tamper evidence, not an immutable signed ledger; normal
repository review and CI controls still matter.

Evidence belongs to exactly one criterion. An evidence ID listed under a
different criterion does not satisfy that criterion and should be fixed rather
than ignored.

Evidence also belongs to the current acceptance plan only when the current
criterion lists that evidence ID. Old records left in
`.fable-verify/evidence/index.json` are historical receipts, not proof for a new
criterion that happens to reuse the same ID.

## Before Final Answer

1. Run `fable-verify status`.
2. Run `fable-verify check`.
3. If `check` fails, continue working or clearly report what remains unverified.
4. Run `fable-verify report`.
5. In the final response, summarize the current proof evidence and final
   verdict. Do not merely say "done."

## Forbidden Behavior

- Do not claim tests passed unless command output was captured.
- Do not record `test`, `build`, `lint`, or `typecheck` proof from a passive
  artifact alone.
- Do not record `diff`, `browser`, `file-read`, or `screenshot` proof from a
  placeholder summary.
- Do not claim UI works unless screenshot or browser evidence exists.
- Do not claim a file was changed unless git diff, git status, or file evidence
  exists.
- Do not edit or replace evidence artifacts after capture without recording new
  evidence.
- Do not ignore failed checks.
- Do not delete verification files to make checks pass.
- Do not mark criteria as passed by hand without matching evidence.
- Do not rely on old evidence from `index.json` unless it is explicitly
  reattached to the current criterion and still represents valid proof.
- Do not record externally captured command evidence without an exit code.
- Do not use directories as evidence artifacts.
- Do not hide blockers outside `.fable-verify/ledger.json`.

## Ledger Schema

Keep `.fable-verify/ledger.json` shaped like this:

```json
{
  "goal": "",
  "status": "active",
  "acceptance_criteria": [],
  "work_log": [
    {
      "timestamp": "ISO timestamp",
      "action": "Short description",
      "criteria": ["AC-001"],
      "evidence": ["EV-001"]
    }
  ],
  "blockers": [],
  "final_verdict": null
}
```

`blockers` may contain strings or objects. If an object is used, set
`"resolved": true` when the blocker is no longer active.

## Completion Standard

Final completion is allowed only when:

- every acceptance criterion is satisfied;
- every required evidence type is present;
- every satisfying evidence ID is listed on the current acceptance criterion;
- every evidence record used by a criterion has a matching `criterion_id`;
- `test`, `build`, `lint`, and `typecheck` evidence includes command
  provenance;
- command evidence exits with code `0`;
- `diff`, `browser`, `file-read`, and `screenshot` evidence satisfies its
  type-specific proof policy;
- every evidence artifact path exists and points to a regular file;
- every current proof artifact has SHA-256 and byte size metadata and still
  matches that metadata;
- no unresolved blockers remain;
- `fable-verify check` prints `PASS`.

If any of those are false, the final answer must say what remains unverified.

## Report Semantics

The report's current proof sections only include evidence attached to the
current acceptance criteria. Current proof rows show evidence type, strength,
command/artifact, artifact size, SHA-256 hash, and integrity status. Historical
receipts appear in a clearly labeled, compact Historical Evidence section
summarized by count and type, with at most the latest 10 historical records
shown. Full historical receipts remain in `.fable-verify/evidence/index.json`,
but they do not support the current goal unless reattached to the current
criterion and still pass integrity checks.
