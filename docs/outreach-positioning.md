# Outreach Positioning

Use these snippets when talking to people asking for coding-agent proof gates,
auditability, or PR verification workflows.

## One-Liner

Fable Verify is a lightweight repo-local proof gate that records acceptance
criteria, evidence artifacts, explicit evidence review, and a final report before
an agent claims work is complete.

## Short Pitch

Fable Verify helps coding agents prove completion instead of merely saying
"done." It stores acceptance criteria, command logs, diffs, screenshots or
browser artifacts, review verdicts, artifact hashes, and final reports in a
plain `.fable-verify/` folder that teams can inspect or gate in CI.

It does not enforce permissions, sandbox an agent, or replace CI and code
review. It complements those systems by making the completion claim auditable.

## PR Workflow Pitch

For PRs, Fable Verify can act as a reviewed-proof gate: the agent captures real
evidence, inspects it, records whether each artifact supports the acceptance
criteria, and then `fable-verify check --json` gives supervisors or CI a
machine-readable verdict.

Teams can pair it with branch protection, normal test jobs, code review, and
their existing permission model.

## What It Does

- Records the user goal and acceptance criteria.
- Captures evidence such as test output, build logs, diffs, screenshots, browser
  artifacts, file reads, and user confirmations.
- Requires explicit evidence review with `supports`, `does-not-support`, or
  `unclear` verdicts.
- Hashes artifacts at capture and review time so mutation invalidates the gate.
- Generates a Markdown report and JSON gate output for supervisors.

## What It Does Not Do

- It does not enforce file permissions.
- It is not a sandbox or policy engine.
- It does not prevent an agent from editing files.
- It does not semantically understand screenshots, code, or diffs by itself.
- It does not replace CI, code review, security review, or runtime monitoring.

## Safe Claim

"Fable Verify gives teams an auditable, repo-local completion proof trail for
coding agents. It is a lightweight proof gate that complements CI, code review,
and permission systems."

## Unsafe Claims To Avoid

- "Fable Verify prevents bad edits."
- "Fable Verify sandboxes the agent."
- "Fable Verify proves the code is correct."
- "Fable Verify replaces code review."
- "Fable Verify understands screenshots or code semantics automatically."
