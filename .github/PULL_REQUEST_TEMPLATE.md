<!--
Thank you for your contribution. Keep the title in Conventional Commits form:
    <type>(<optional scope>): <short imperative summary>
Examples:
    fix(stream-density): drop unused fail threshold
    docs(readme): add Docker Compose prerequisite
    feat(benchmark)!: change latency metric default to p95   # ! = breaking
See CONTRIBUTING.md for the full commit-message guidelines.
-->

## What are you changing?
<!-- One or two sentences on WHAT changed and WHY. The reviewer should be able to
     understand the intent before opening the diff. -->

## Issue this PR closes
close: #<issue_number>

## PR Checklist
<!-- Tick each box. Put an explanation next to any box you cannot tick. -->

- [ ] **Title follows Conventional Commits** (`<type>(<scope>): <summary>`) and reads like a changelog entry — not "Update <file>".
- [ ] **Commits are signed off** (`git commit -s`, Developer Certificate of Origin).
- [ ] **Each commit is single-purpose** — one fix or one change per commit, features and fixes not mixed.
- [ ] **Tests added/updated** for new or changed behaviour, and the suite passes locally.
- [ ] **Documentation updated** (README, docs/, comments) where the change affects it.
- [ ] **No commented-out or dead code, and no debug prints** left behind.
- [ ] **Added a label** to the PR for discoverability.
- [ ] **New dependencies** (if any) have a compatible license and are listed below with a reason.

## Does this change results or break compatibility?
<!-- Answer both. If YES to either, the title/commit MUST carry `!` or a
     `BREAKING CHANGE:` footer, and you must describe the impact here. -->

- Changes benchmark/measurement results: **No** / **Yes** — <details>
- Breaks compatibility with other modules or repos: **No** / **Yes** — <details>

## Security
<!-- Does this PR touch auth, secrets, input validation, crypto, network exposure,
     or dependencies with known CVEs? -->

- Security-relevant change: **No** / **Yes** — <details>

## Test instructions
<!-- How can a reviewer verify this change? Commands, configs, expected output. -->

## Related PRs in other repositories
<!-- Link any companion PRs, e.g. intel-retail/performance-tools#123 -->
