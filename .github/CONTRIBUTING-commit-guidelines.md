<!--
  Drop-in commit-message section for each repo's CONTRIBUTING.md.
  Replaces the mis-targeted guidance currently in performance-tools
  (Azure Boards / JIRA / heci / lms scopes) and fills the gap in the
  repos that have no commit guidance at all.
-->

## Commit message guidelines

Every commit and every squash-merge title in this repository follows the
[Conventional Commits](https://www.conventionalcommits.org/) standard. This keeps
`git log` readable like a changelog, lets us auto-generate release notes from
`feat` and `fix` commits, and lets a reviewer understand a change before opening
the diff.

### Format

```
<type>(<optional scope>): <subject>
<BLANK LINE>
<optional body — the "why", wrapped at ~72 chars>
<BLANK LINE>
<optional footer — BREAKING CHANGE / issue refs / Signed-off-by>
```

- The **header** (`<type>(<scope>): <subject>`) is mandatory and must be ≤ 72 characters.
- Use the **imperative mood**: "add", "fix", "drop" — not "added" / "fixes".
- Do **not** use GitHub's default "Update `<file>`" title. The file list already shows which files changed; the message must say *what* and *why*.

### Type — required, one of:

| Type       | Use for                                                              |
| ---------- | ------------------------------------------------------------------- |
| `feat`     | A new feature or capability                                         |
| `fix`      | A bug fix                                                           |
| `perf`     | A change that improves performance                                  |
| `refactor` | A code change that neither fixes a bug nor adds a feature           |
| `docs`     | Documentation only                                                  |
| `test`     | Adding or correcting tests                                          |
| `build`    | Build system, Dockerfiles, compose, Makefile, or dependencies       |
| `ci`       | CI/CD workflows and automation                                     |
| `style`    | Formatting/whitespace only, no behaviour change                     |
| `chore`    | Routine maintenance that doesn't fit above (e.g. version bumps)     |
| `revert`   | Reverts a previous commit (body: `This reverts commit <hash>.`)     |

### Scope — optional, but encouraged

A short area of the codebase, lowercase. Pick one that fits the repo, e.g.
`benchmark`, `stream-density`, `ui`, `backend`, `pipeline`, `docker`, `compose`,
`makefile`, `models`, `docs`, `rag`, `tts`, `asr`, `alert-service`. Reviewers may
ask you to add or correct a scope.

### Breaking / result-changing commits

If a change alters benchmark results or breaks compatibility, mark it either with
a `!` after the type/scope **or** a `BREAKING CHANGE:` footer:

```
fix(stream-density)!: change latency metric default from avg to p95

BREAKING CHANGE: benchmark numbers are no longer comparable to pre-2026.2 runs.
```

### Sign your work (DCO)

Every commit must be signed off under the
[Developer Certificate of Origin](https://developercertificate.org/). Add the
sign-off automatically with:

```bash
git commit -s -m "fix(stream-density): drop unused fail threshold"
```

### Examples

```
feat(benchmark): add p95 latency to consolidated metrics CSV
fix(stream-density): drop unused fail threshold
docs(readme): add Docker Compose prerequisite
refactor(ui): extract AlertCard severity badge into helper
perf(rag): cache embedding model between requests
```