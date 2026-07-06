# Realistic PR Verification Demo

This demo exercises a full proof-gate loop in a temporary git repository using
real artifacts instead of placeholder receipts.

Run it from the Fable Verify repository root:

```sh
npm run demo:realistic
```

The script creates a small HTML project, commits a baseline, makes a UI change,
and then records:

- `git diff -- index.html test/home.test.js` as implementation evidence;
- an SVG screenshot artifact as visual evidence;
- `npm test` as real command evidence;
- `git status --short && git diff --stat` as scoped-change evidence;
- `fable-verify show` output before each review;
- `fable-verify review` records with `supports` notes;
- `fable-verify check --json` supervisor output;
- a generated final Markdown report.

The screenshot artifact is deliberately simple and local. Fable Verify records
its path, byte size, and hash, but a reviewer still has to inspect it and record
why it supports the UI criterion. The CLI does not visually understand the
image.

This is the outreach-safe claim: Fable Verify records proof of completion and
checks that the proof has been reviewed. It does not sandbox the agent, enforce
permissions, or replace CI and code review.
