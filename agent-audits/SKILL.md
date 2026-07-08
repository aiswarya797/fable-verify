---
name: agent-audits
description: >-
  Use Agent Audits whenever a coding agent needs to make, verify, or defend a
  completion claim for code work: done, fixed, correct, verified, ready for
  review, safe to merge, or "how do you know?". Use it for proof-of-done,
  acceptance judges, PR verification gates, audit trails, completion receipts,
  supervised or autonomous coding handoffs, command output and exit-code
  evidence, stale-proof checks, tamper-evident artifacts, and repo-local reports
  tied to acceptance criteria. If no current Agent Audits proof exists, do not
  answer from memory alone; create or collect evidence, run the verification
  gate, or report the work as unverified.
---

# Agent Audits Instructions

Use this file when a coding agent should work in an agent-audit discipline using
only repo-local files, scripts, and Markdown instructions.

Agent Audits is harness-agnostic. These instructions apply in Codex, Claude
Code, Cursor, OpenCode, shell-only workflows, and any other environment that can
read files and run local commands.

## Required Loop

Follow this operating loop:

```text
Goal -> Spec -> Plan -> Work -> Evidence -> Self-Review -> Verification Gate -> Final Report
```

The agent must not claim completion unless every acceptance criterion has
supporting evidence, that evidence has been explicitly reviewed against the
acceptance criterion, and `agent-audits check` passes.

## Completion Claim Workflow

Use this bounded workflow whenever you are about to say work is done, fixed,
correct, verified, ready for review, safe to merge, or when the user asks "how
do you know?", "what proof do we have?", "did this solve the issue?", or a
similar completion-proof question.

1. Run `agent-audits status`.
2. If a current Agent Audits plan and evidence already exist, inspect the
   relevant evidence with `agent-audits show EV-###` or the appropriate viewer.
3. Run or rerun only the missing verification steps needed for the current
   acceptance criteria. Attach each result with `agent-audits add-evidence`.
4. Record explicit reviews with `agent-audits review` that explain why each
   artifact supports, does not support, or is unclear for its criterion.
5. Run `agent-audits check`.
6. If `check` passes, generate `agent-audits report` and answer from the current
   criteria, evidence IDs, commands/artifacts, review notes, and verdict.
7. If `check` fails, do not claim completion. Continue only when the next action
   is clear and bounded. Otherwise record a blocker and report the exact
   unverified criteria or evidence gaps.

Do not loop forever. After a repeated command failure, missing dependency,
unclear acceptance criterion, unavailable browser/screenshot artifact, or other
blocked proof path, stop the verification attempt, record the blocker in
`.agent-audits/ledger.json`, and say the work is not verified yet.

Evidence only counts when it is explicitly attached to the current acceptance
criterion's `evidence` array. Reports show current proof separately from
historical receipts. `test`, `build`, `lint`, and `typecheck` evidence must
include command provenance and an exit code. Current proof artifacts are hashed
with SHA-256 and byte size; if an artifact is missing, mutated, or lacks
integrity metadata, the verification gate must fail. Reviews are also hashed
against the artifact bytes observed during review; if the artifact later changes,
the supporting review is invalid.

## Enforcement Boundary

Agent Audits verifies completion evidence. It checks whether acceptance criteria
have current-plan evidence attachments, correctly owned evidence records, real
artifact paths, artifact integrity metadata, successful command evidence, no
weak evidence substitutes for technical proof, explicit supporting review
verdicts with notes, review-time artifact integrity, and no unresolved blockers.

This is an agent-audit self-checking discipline, not full policy-enforcement
parity. The CLI does not semantically understand screenshots, diffs, logs, or
code. The agent or human reviewer must inspect the artifact and record whether
it supports the criterion.

The current CLI does not block edits before planning, enforce forbidden paths,
install pre-edit hooks, or stop an agent that chooses to ignore it. Use it as a
repo-local verification gate and auditable proof trail. Do not describe it as a
sandbox, hook system, or hard edit blocker unless those controls are actually
implemented and tested.

Hard enforcement roadmap: future optional layers could add pre-edit hooks,
worktree apply gates, forbidden-path policies, or CI-required `agent-audits
check` runs. Those controls are not part of the current lightweight CLI.

## Before Starting Work

1. Read the user's goal.
2. If you are validating the Agent Audits package itself, run `npm run doctor`,
   `npm run smoke`, and `npm run eval:matrix` before release checks.
3. Run `agent-audits init`, or create the same `.agent-audits/` structure if the
   command is not on `PATH`.
4. Run `agent-audits plan "<goal>"`, provide the goal through stdin, or write the
   goal to `.agent-audits/goal.md` and run `agent-audits plan`.
5. Review `.agent-audits/acceptance.json`.
6. Treat generated criteria as workflow templates. The CLI has starting
   templates for bug fixes, UI changes, refactors, docs-only changes, and
   autonomous PR handoffs, but the agent still has to make the criteria fit the
   task.
7. Refine the criteria until each item is observable, testable, and has explicit
   `evidence_required` values.
8. Ask clarifying questions only when the goal cannot be made testable from the
   available context.

## During Work

Maintain `.agent-audits/ledger.json` as the live requirements ledger.

For every implementation step:

- link the work to one or more acceptance criteria;
- add or update a `work_log` entry;
- record blockers instead of silently working around them;
- add evidence immediately after running tests, builds, lints, typechecks,
  browser checks, screenshot captures, file reads, or diff reviews;
- keep evidence artifact paths real and reviewable.
- inspect current evidence with `agent-audits show EV-###` or an appropriate
  viewer before recording a review;
- record a review with `agent-audits review` and concrete notes explaining why
  the artifact supports, does not support, or is unclear for the criterion.

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

- Agent Audits runs the command through `--command` and records stdout, stderr,
  and exit code; or
- the agent records externally captured command evidence with `--command`,
  `--artifact-path`, and `--exit-code`.

Use command evidence whenever possible:

```sh
agent-audits add-evidence --criterion AC-001 --type test --command "npm test"
```

That command captures stdout, stderr, and exit code into
`.agent-audits/evidence/`.

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
Artifacts outside the repo are copied into `.agent-audits/evidence/`, with the
original absolute source path kept in metadata. Missing artifact paths and
directories must be treated as failed evidence operations, not as evidence to fix
later.

If you pass both `--command` and `--artifact-path`, you are recording command
evidence captured outside Agent Audits. You must also pass `--exit-code`.
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
`.agent-audits/evidence/index.json` are historical receipts, not proof for a new
criterion that happens to reuse the same ID.

## Review Rules

Before final completion, every current evidence artifact must be reviewed against
its owning acceptance criterion.

Use `show` before review:

```sh
agent-audits show EV-001
```

For log-like artifacts, `show` prints metadata and a text preview. For
screenshots/images, it prints metadata and the artifact path; the reviewer must
open and inspect the image. Do not claim the CLI visually understood it.

Record a review:

```sh
agent-audits review --criterion AC-001 --evidence EV-001 --verdict supports --notes "Test log shows npm test completed with exit code 0 and all suites passed."
```

Supported verdicts:

```text
supports does-not-support unclear
```

Only `supports` can satisfy the verification gate. Missing notes, unknown
criteria/evidence, evidence owned by a different criterion, evidence not
attached to the criterion, and missing artifacts must fail review recording.

Review records live in `.agent-audits/reviews.json` and store review id,
criterion id, evidence id, verdict, notes, timestamp, reviewer kind/name, and
the artifact hash/size observed at review time. If the artifact changes after
review, the review no longer supports the gate.

## Before Final Answer

1. Run `agent-audits status`.
2. Inspect current evidence with `agent-audits show EV-###` or an appropriate
   artifact viewer.
3. Record reviews with `agent-audits review` for every current evidence
   artifact. `agent-audits check` alone is not enough.
4. Run `agent-audits check`, or `agent-audits check --json` when a supervisor,
   CI job, or PR workflow needs machine-readable output.
5. If `check` fails, continue working or clearly report what remains unverified.
6. Run `agent-audits report`.
7. In the final response, summarize the current proof evidence, self-review, and
   verdict. Do not merely say "done."

## PR And CI Gate Use

For PR verification workflows, `agent-audits check --json` is the supervisor or
CI-friendly output. It reports the verdict, whether completion is allowed,
passing criteria count, missing evidence, blockers, issues, and per-criterion
status.

Use it alongside normal CI, branch protection, code review, security review, and
repository permissions. Agent Audits records and checks completion proof; it
does not sandbox an agent, enforce permissions, or prevent edits.

Do not auto-create `supports` reviews inside CI just to make the gate pass. A
review is an agent or human judgment made after inspecting the artifact.

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
- Do not skip evidence review and rely on `agent-audits check` alone.
- Do not record `supports` unless you inspected the artifact and can explain why
  it supports the criterion in the notes.
- Do not delete verification files to make checks pass.
- Do not mark criteria as passed by hand without matching evidence.
- Do not rely on old evidence from `index.json` unless it is explicitly
  reattached to the current criterion and still represents valid proof.
- Do not record externally captured command evidence without an exit code.
- Do not use directories as evidence artifacts.
- Do not hide blockers outside `.agent-audits/ledger.json`.

## Ledger Schema

Keep `.agent-audits/ledger.json` shaped like this:

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
- every current evidence artifact has a latest applicable review with verdict
  `supports` and non-empty notes;
- every supporting review's recorded artifact hash and byte size still match the
  current artifact;
- no unresolved blockers remain;
- `agent-audits check` prints `PASS`.

If any of those are false, the final answer must say what remains unverified.

## Report Semantics

The report's current proof sections only include evidence attached to the
current acceptance criteria. Current proof rows show evidence type, strength,
command/artifact, artifact size, SHA-256 hash, and integrity status. The
Semantic Evidence Review section shows review verdicts, notes, artifact
integrity, and review integrity. This section records explicit agent/human
review; it is not proof that the CLI semantically understood screenshots, diffs,
logs, or code. Historical receipts appear in a clearly labeled, compact
Historical Evidence section summarized by count and type, with at most the
latest 10 historical records shown. Full historical receipts remain in
`.agent-audits/evidence/index.json`, but they do not support the current goal
unless reattached to the current criterion and still pass integrity and review
checks.
