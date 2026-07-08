# GitHub Actions PR Gate

Use Agent Audits in CI when a pull request includes a reviewable proof bundle
that CI can read. The gate checks repo-local acceptance criteria, current
evidence, explicit reviews, artifact integrity, and blockers.

Agent Audits complements normal CI. Keep your regular test, lint, typecheck,
security, and code-review requirements. Agent Audits answers a narrower
question: "Does this PR carry reviewed evidence for its completion claim?"

## Important Boundary

By default, `.agent-audits/` is ignored because local evidence can include
machine paths, transient logs, or sensitive output. A PR gate needs one of these
approaches:

- Commit a sanitized proof bundle for the PR, using `git add -f` for the
  specific `.agent-audits/` files that are safe to publish.
- Restore a proof bundle from a trusted artifact store before running
  `agent-audits check`.
- Generate mechanical CI evidence in the workflow, then require a separate
  reviewed proof bundle before merge.

Do not auto-record `supports` reviews in CI just to make the gate pass. A review
is an agent or human judgment that the artifact supports the acceptance
criterion.

## Minimal PR Gate

```yaml
name: Agent Audits

on:
  pull_request:

jobs:
  agent-audits:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install Agent Audits
        run: npm install -g agent-audits

      - name: Check reviewed proof bundle
        run: |
          set +e
          agent-audits check --json > agent-audits-check.json
          status=$?
          cat agent-audits-check.json
          exit "$status"

      - name: Upload Agent Audits report data
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: agent-audits-check
          path: |
            agent-audits-check.json
            .agent-audits/reports/*.md
```

## Local Package Development

From this repository before publishing:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- uses: actions/setup-node@v4
  with:
    node-version: "20"
- run: npm ci --ignore-scripts
- run: ./bin/agent-audits check --json
```

## Suggested Branch Protection

Require both:

- your normal CI job, such as `npm test`, lint, build, typecheck, or browser
  tests;
- the Agent Audits job that runs `agent-audits check --json`.

This keeps execution proof and semantic review proof separate instead of asking
one tool to do everything.
