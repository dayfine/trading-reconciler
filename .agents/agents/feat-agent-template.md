---
name: feat-agent-template
description: Template and contract for all feat-* agent definitions. Every feat-agent must include the required sections below. This file is read by the health-scanner to verify compliance.
harness: template
---

# Feat-Agent Definition Template

This document defines the required structure for every `feat-*.md` agent definition.
When creating a new feature agent, copy this template and fill in the feature-specific
sections. Do not omit required sections — the health-scanner checks for their presence.

---

## Required sections (every feat-agent must have all of these)

### 1. Frontmatter

```yaml
---
name: feat-<feature-name>
description: <one-line description of what this agent builds>
---
```

### 2. Session startup sequence

The agent must read these at the start of every session, in order:

1. `dev/agent-feature-workflow.md` — shared workflow
2. `CLAUDE.md` — code patterns and idioms
3. `dev/decisions.md` — human guidance
4. `dev/status/<feature>.md` — resume from where you left off
5. `docs/design/<eng-design-N-feature>.md` — the feature's design doc
6. Any additional design docs relevant to this feature
7. **If the dispatch prompt mentions an "Approved plan" under the
   pre-flight context, read `dev/plans/<name>-<date>.md` first — its
   §Approach and §Out of scope are binding.** See
   `.agents/agents/lead-orchestrator.md` §Step 3.5 for when plans
   are produced.
8. **If the dispatch prompt contains a `## Rework mode` block, this is
   an intra-run rework dispatch — not a fresh session.** The branch
   already exists, QC flagged findings, and you must address the items
   listed in the pasted `dev/reviews/<feature>.md` content. Follow the
   rework-mode rules exactly: address every checked-fail item, no new
   scope, use `fix(review): ` commit subjects, do not open a new PR or
   flip the draft flag. See `.agents/agents/lead-orchestrator.md`
   §Step 5a (rework decision) and §Step 4 "Rework Mode prompt" for the
   full contract.
9. State the session plan before writing any code

### 3. Branch and status file

```
Your branch: feat/<feature-name>
Status file: dev/status/<feature>.md
```

Include a `## VCS choice (automatic)` section alongside the branch info:

```markdown
## VCS choice (automatic)

If `$PROJECT_IN_CONTAINER` is set (GHA runs), use **git** — jj is not
available. Each session: `git fetch origin && git checkout -b feat/<name> origin/main`.
Commit with `git commit`, push with `git push origin HEAD`.

Otherwise (local runs), use **jj** with a per-session workspace. The
orchestrator's dispatch prompt tells you the exact commands — follow
those over any jj/git references in the examples in this file. See
`.agents/agents/lead-orchestrator.md` §"Step 4: Spawn feature agents"
for the authoritative dispatch shape.
```

### 4. Allowed Tools (required, verbatim or adjusted)

```markdown
## Allowed Tools

Read, Write, Edit, Glob, Grep, Bash (build/test commands only), WebFetch.
Do not use the Agent tool (no subagent spawning).
```

### 5. Max-Iterations Policy (required, verbatim)

```markdown
## Max-Iterations Policy

If after **3 consecutive build-fix cycles** `dune build && dune runtest` is still
failing: stop, report your partial state and the specific blocker, update
`dev/status/<feature>.md` to BLOCKED, and end the session. Do not continue
looping — diminishing returns set in quickly and looping wastes budget.
```

### 6. Acceptance Checklist (required, feature-specific items)

```markdown
## PR sizing

Prefer **one new module per PR** — the unit is `(module.ml, module.mli,
test/test_module.ml)` plus its `dune` entry. Three to four files,
typically 200–500 LOC. This is the "small CL" discipline from
https://google.github.io/eng-practices/review/developer/small-cls.html
applied to OCaml: a module is the natural reviewable unit because its
`.mli` is the contract, the `.ml` is the implementation against that
contract, and the test pins the observable behavior — reviewing them
together is high-signal; reviewing them apart is low-signal.

**Rules:**

- **One new module ⇒ one PR.** If your work introduces a new
  `.ml` + `.mli` pair, that pair (plus its tests + dune entry) is the
  PR. Wiring that consumes the new module belongs in a separate PR
  stacked on top.
- **Multiple new modules ⇒ stacked PRs.** Each module gets its own
  branch + PR; second module's branch bases off the first module's
  branch. Use `jst submit` so the stack is reviewable in order.
- **Hard cap: ~500 LOC per PR.** If your draft commit exceeds 500
  LOC, stop and look for a module boundary you crossed. Almost always
  the right split is "the new module" vs "the wiring that consumes it."
  Status-file edits, plan files, and test fixtures don't count toward
  the cap — they're context, not implementation.
- **Pre-PR self-check:** before pushing, run `jj diff --stat`. If
  output crosses two new-module boundaries (or one new module + its
  consumer wiring), split before pushing — not after review asks for
  it. Splitting after a PR opens means re-doing CI, re-running QC,
  and re-anchoring reviewer context; splitting before is a 10-minute
  `jj` rearrange.
- **Does not apply to:** small bug fixes (a 50-LOC patch touching one
  module is a single PR by definition), single-file refactors, or
  status-file-only updates. Apply when introducing new modules or
  meaningfully extending existing ones.

If your plan-file decomposition (per `dev/plans/*.md`) names increments
that are 800+ LOC, that's a smell — the increment crosses a module
boundary that should be its own increment. Surface it in the dispatch
prompt's `## Plan context` so the orchestrator can re-decompose, or
split it inline yourself if obvious.

## Acceptance Checklist

QC agents will verify all of the following. Satisfy every item before setting
status to READY_FOR_REVIEW.

- [ ] <feature-specific item derived from the engineering design doc>
- [ ] <...>
- [ ] Every public function in every `.ml` is exported in the corresponding `.mli` with a doc comment
- [ ] No function exceeds 50 lines
- [ ] PR diff respects `## PR sizing` rules (≤500 LOC, one new module per PR; status / plan / fixtures don't count)
- [ ] All configurable parameters routed through config record — no magic numbers
- [ ] `dune build && dune runtest` passes with zero warnings **on a clean checkout of the branch** — not just on your local worktree. If you are running in `isolation: "worktree"` (the orchestrator default), your working copy is usually but not always a clean checkout — follow `.agents/rules/worktree-isolation.md` to verify (`jj diff --stat` pre-commit, branch ancestry check pre-push, PR file list post-push). If you are NOT in a worktree (rare, legacy runs), re-verify by checking that every module your branch references is either in your commits or already on `main@origin` — do not rely on files sitting in the shared working copy that you did not explicitly commit.
- [ ] `dune build @fmt` passes (formatter in check mode; equivalent: `dune fmt` produces no diff)
- [ ] `Interface stable: YES` is set in `dev/status/<feature>.md` once `.mli` is finalized
- [ ] **PR description is non-empty.** `jst submit` does NOT populate the PR body from commit messages — the body field stays empty unless you write it explicitly. After `jst submit`, run `gh pr edit <N> --body-file <path>` (or `curl PATCH /pulls/<N> -d '{"body":"..."}'`) to set the body. The description should mirror the extended commit message: what changed, why, test plan. Bodies matter for reviewers scanning `gh pr list` and for future archaeology. Empty-body PRs were an observed gap — see run-5 on 2026-04-19.
```

### 7. Status file format (required, feature-specific fields)

Document the canonical format for `dev/status/<feature>.md` that this agent must
maintain. The canonical sections are:

```markdown
## Last updated: YYYY-MM-DD
## Status
IN_PROGRESS | READY_FOR_REVIEW | MERGED

## Interface stable
YES | NO

## Completed
(what is merged and done — no done items belong in Follow-up)

## In Progress
(current session work)

## Blocking Refactors
(items that must be resolved before downstream features can depend on this one;
the lead-orchestrator dispatches these before feat-agents on each run)

## Follow-up
(non-blocking open items; the orchestrator counts these for maintenance cycles;
remove items once addressed — this is a backlog, not a ledger)

## Known gaps
(long-horizon items with no immediate action needed; informational only;
the orchestrator does not act on this section)
```

**Rules:**
- Remove done items from `## Follow-up` immediately — do not accumulate history there
- Omit `## Recent Commits` — git log is authoritative; PR numbers belong in `## Completed`
- `## Blocking Refactors` takes priority over feature work on the next run
- `## Known gaps` is never empty-checked by automation; it is for human awareness only

### 8. Index row update — DO NOT EDIT `dev/status/_index.md` IN A FEATURE PR

`dev/status/_index.md` is owned by the orchestrator. `lead-orchestrator`
reconciles it in Step 5.5 against every `dev/status/*.md` at end-of-run.

Feature PRs that also edit `_index.md` almost always collide with a
sibling PR editing the same row, producing a merge conflict for every
merge after the first. Don't cause that pain.

Only update your own `dev/status/<feature>.md`. The orchestrator will
reflect it in the index on the next run.

**Exception — adding a new track:** if this PR introduces a new track
(new status file), add the corresponding row to `_index.md` in this PR
too. The orchestrator won't know about the track otherwise.

---

## Architecture constraint

Every feat-agent must respect the layer boundary:

- <PROJECT_NAME>-specific logic belongs in new modules alongside the existing ones — **not** inside the shared core modules.
- If a change to a shared module is genuinely application-agnostic (i.e., it would
  benefit any consumer), it is permitted — but the agent must
  note it explicitly in its status file and qc-behavioral will assess it
- When in doubt: build alongside, don't modify

---

## Extensibility notes (for harness maintainers)

When adding a new feat-agent for a future feature:

1. Copy this template as `.agents/agents/feat-<name>.md`
2. Fill in the feature-specific parts: design doc path, branch name, acceptance
   checklist items derived from the design doc
3. Add a status file at `dev/status/<name>.md` using the standard format
4. Add the feature to `dev/decisions.md` if there are priority or sequencing notes
5. The lead-orchestrator will pick it up automatically on the next run (T4-C)
6. The health-scanner will verify the agent definition contains all required sections

The harness practices (tool subset, iteration cap, checklist format, structured QC
output) are defined here and in the QC agent definitions — they apply to all feat-agents
automatically. No changes to the QC agents or orchestrator are needed for new features.
