# Simple Fix Demo

This demo shows the intended Fable Verify shape for a small bug fix.
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

From the `Fable-Verify` repository root, this demo uses a throwaway workspace
and reaches `PASS` before generating the report:

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

If `check` fails, the agent is not allowed to claim the bug is fixed. It must add
the missing proof, recreate tampered evidence, or report the remaining
unverified criteria.
