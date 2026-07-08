# Simple Fix Demo

This demo shows the intended Agent Audits shape for a small bug fix.
Evidence that proves tests or diffs is command-backed. The log receipt is weak
evidence and only satisfies the criterion that explicitly asks for a `log`.
Every captured artifact is hashed so later edits fail the gate. The agent also
inspects each evidence artifact and records a review verdict before `check` can
pass.

## Goal

Fix a bug and prove it is fixed.

Concrete example:

```text
Fix the login redirect bug and prove it works.
```

## Acceptance Criteria

| ID | Description | Evidence Required |
| --- | --- | --- |
| AC-001 | Bug reproduction exists. | `test`, `log` |
| AC-002 | Fix is implemented. | `diff` |
| AC-003 | Test passes. | `test` |
| AC-004 | Diff shows scoped change. | `diff` |

## Commands

From the Agent Audits repository root, this demo uses a throwaway workspace
and reaches `PASS` before generating the report:

```sh
tmpdir="$(mktemp -d)"
AGENT_AUDITS="$PWD/bin/agent-audits"
cd "$tmpdir"

"$AGENT_AUDITS" init
"$AGENT_AUDITS" plan "Bug: login redirect fails"
"$AGENT_AUDITS" add-evidence --criterion AC-001 --type test --command "python -c \"print('reproduced redirect bug')\""
"$AGENT_AUDITS" add-evidence --criterion AC-001 --type log --command "python -c \"print('before: redirect loop observed')\""
"$AGENT_AUDITS" add-evidence --criterion AC-002 --type diff --command "python -c \"print('diff reviewed: login redirect fix')\""
"$AGENT_AUDITS" add-evidence --criterion AC-003 --type test --command "python -c \"print('redirect regression test passed')\""
"$AGENT_AUDITS" add-evidence --criterion AC-004 --type diff --command "python -c \"print('scoped diff reviewed')\""
"$AGENT_AUDITS" show EV-001
"$AGENT_AUDITS" review --criterion AC-001 --evidence EV-001 --verdict supports --notes "Reproduction test log shows exit code 0 and the expected redirect bug output."
"$AGENT_AUDITS" show EV-002
"$AGENT_AUDITS" review --criterion AC-001 --evidence EV-002 --verdict supports --notes "Log output documents the pre-fix redirect loop observation."
"$AGENT_AUDITS" show EV-003
"$AGENT_AUDITS" review --criterion AC-002 --evidence EV-003 --verdict supports --notes "Diff evidence output supports that the login redirect fix was reviewed."
"$AGENT_AUDITS" show EV-004
"$AGENT_AUDITS" review --criterion AC-003 --evidence EV-004 --verdict supports --notes "Regression test log shows the verification command exited 0."
"$AGENT_AUDITS" show EV-005
"$AGENT_AUDITS" review --criterion AC-004 --evidence EV-005 --verdict supports --notes "Diff review output supports that the change was scoped."
"$AGENT_AUDITS" check
"$AGENT_AUDITS" report
```

If `check` fails, the agent is not allowed to claim the bug is fixed. It must add
the missing proof, recreate tampered evidence, or report the remaining
unverified criteria.
