<div align="center">
  <h1>
    <img src="assets/agent-audits-logo.svg" width="42" alt="Agent Audits logo">
    Agent Audits
  </h1>

  <p><strong>Repo-local proof-of-done loops for AI coding agents.</strong></p>

  <p>
    Your coding agent says <code>done</code>. Agent Audits asks:
    <code>based on what?</code>
  </p>

  <p>
    <a href="https://www.npmjs.com/package/agent-audits"><img src="https://img.shields.io/npm/v/agent-audits" alt="npm version"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
    <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/cloud-not_required-16a34a" alt="No cloud required">
    <img src="https://img.shields.io/badge/check---json-111827" alt="JSON gate">
  </p>

  <p>
    <a href="#install">Install</a> &bull;
    <a href="#agent-setup">Agent Setup</a> &bull;
    <a href="#quickstart">Quickstart</a> &bull;
    <a href="#cli-reference">CLI</a> &bull;
    <a href="#proof-rules">Proof Rules</a> &bull;
    <a href="#ci-and-demos">CI And Demos</a> &bull;
    <a href="#limits">Limits</a>
  </p>
</div>

---

Agent Audits is a repo-local verification loop and completion gate for AI coding
agents, not a model or sandbox. It turns `done` into acceptance criteria,
evidence, review notes, and an `agent-audits check` verdict.

```text
Goal -> Criteria -> Evidence -> Review -> Check -> Report
```

It works with Codex, Claude Code, Cursor, OpenCode, shell-only agents, and CI
because it only needs repo files and local commands.

## Install

Agent Audits ships as a small npm package that runs a Python CLI. It requires
Python 3.10 or newer on your `PATH`.

```sh
npm install -g agent-audits
agent-audits init
```

From this repository, use `./bin/agent-audits`.

## Agent Setup

For the best experience, add this to `AGENTS.md`, `CLAUDE.md`, or your agent
runner instructions:

```md
Before claiming a coding task is done, fixed, correct, verified, ready for
review, or safe to merge, use Agent Audits.

If the user asks "how do you know?", answer from current Agent Audits evidence:
acceptance criteria, evidence IDs, commands or artifacts, review notes, and the
`agent-audits check` verdict.

If no current proof exists, collect it or say the work is not verified yet.
```

The portable Codex skill lives at [`agent-audits/SKILL.md`](agent-audits/SKILL.md).

## Quickstart

Use this pattern after an agent changes code:

```sh
agent-audits init
agent-audits plan "Fix the login redirect bug"

agent-audits add-evidence \
  --criterion AC-001 \
  --type test \
  --command "npm test"

agent-audits show EV-001
agent-audits review \
  --criterion AC-001 \
  --evidence EV-001 \
  --verdict supports \
  --notes "npm test completed with exit code 0."

agent-audits check --json
agent-audits report
```

Repeat `add-evidence`, `show`, and `review` for every acceptance criterion.
`check` should pass before the agent says the task is done.

## How It Works

`agent-audits init` creates a local `.agent-audits/` workspace:

```text
.agent-audits/
  goal.md
  acceptance.json
  ledger.json
  reviews.json
  evidence/
  reports/
```

The workflow is intentionally plain:

1. `plan` turns a goal into editable acceptance criteria.
2. `add-evidence` captures command output or attaches artifacts.
3. `show` lets the reviewer inspect the evidence.
4. `review` records whether the evidence supports the criterion.
5. `check` decides whether completion is allowed.
6. `report` writes a Markdown proof receipt.

Everything stays in repo-local files. `.agent-audits/` is ignored by default so
local proof, machine paths, and temporary reports do not ship accidentally.

## CLI Reference

| Command | Purpose |
| --- | --- |
| `agent-audits init` | Create `.agent-audits/`. Use `--force` only when replacing existing state. |
| `agent-audits plan "<goal>"` | Create starter acceptance criteria for the task. Templates cover bug fixes, UI changes, refactors, docs-only changes, and autonomous PR handoffs. |
| `agent-audits status` | Show criteria count, passing criteria, missing evidence, blockers, and whether completion is allowed. |
| `agent-audits add-evidence` | Attach `test`, `build`, `lint`, `typecheck`, `diff`, `screenshot`, `browser`, `log`, `file-read`, or `manual-user-confirmation` evidence. |
| `agent-audits show EV-001` | Inspect evidence metadata, artifact integrity, command output, and latest review state. |
| `agent-audits review` | Record `supports`, `does-not-support`, or `unclear` with notes for one criterion/evidence pair. |
| `agent-audits check` | Fail or pass the completion gate. Use `--json` for supervisors, CI, and PR workflows. |
| `agent-audits report` | Generate a Markdown report under `.agent-audits/reports/`. |

Most evidence should come from commands:

```sh
agent-audits add-evidence \
  --criterion AC-003 \
  --type test \
  --command "python -m unittest discover -s tests"
```

For artifacts captured outside Agent Audits, pass `--artifact-path`. If the
artifact represents a command result, also pass `--exit-code`.

## Proof Rules

`agent-audits check` passes only when current criteria have reviewed, valid
evidence. The important rules:

- Evidence must be attached to the current criterion.
- `test`, `build`, `lint`, and `typecheck` need a command and exit code `0`.
- `diff`, `browser`, and `file-read` need command output or a real artifact.
- `screenshot` needs an image-like artifact.
- `log` and `manual-user-confirmation` are weak evidence and cannot replace
  missing strong proof.
- Artifacts are recorded with SHA-256 hash, byte size, MIME hint, and capture
  time. Missing or changed artifacts fail the gate.
- The latest review for each current evidence item must be `supports` and must
  include notes.
- Unresolved blockers in `.agent-audits/ledger.json` keep completion closed.

Reports separate current proof from historical receipts so old evidence does
not silently support a new goal.

## CI And Demos

Use `agent-audits check --json` when another tool needs a machine-readable gate.
The JSON includes verdict, allowed status, passing criteria, missing evidence,
blockers, issues, and per-criterion status.

- GitHub Actions example: [`docs/github-actions.md`](docs/github-actions.md)
- Safe outreach wording: [`docs/outreach-positioning.md`](docs/outreach-positioning.md)
- Simple example: [`examples/simple-fix/README.md`](examples/simple-fix/README.md)
- Realistic PR demo: [`examples/realistic-pr-verification/README.md`](examples/realistic-pr-verification/README.md)

Run the realistic demo from this repository:

```sh
npm run demo:realistic
```

## Limits

Agent Audits is not a sandbox, permission system, edit blocker, CI replacement,
security review, or signed audit log. It verifies whether the agent has current
repo-local proof for a completion claim.

It also does not semantically understand screenshots, browser output, or diffs.
An agent or human still has to inspect the artifact and record the judgment with
`agent-audits review`.

Use normal code review, CI, repository permissions, and security checks for
enforcement. Use Agent Audits for completion evidence and auditable handoff.

## Development

```sh
npm test
npm run doctor
npm run smoke
npm run eval:matrix
npm run pack:check
npm run preflight
```

`npm run preflight` runs the full local release check: tests, doctor, smoke,
evaluation matrix, and package dry-run.

Validate the bundled Codex skill from your Codex home:

```sh
python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py agent-audits
```
