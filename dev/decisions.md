---
harness: project
---

# Decisions log

Human-authored guidance for agents. Read at session start by every
feat-agent (per `dev/agent-feature-workflow.md`) and the orchestrator
(per `.agents/agents/lead-orchestrator.md` Step 1).

Most-recent decisions on top.

---

## 2026-04-30 — Phase 1 implementation kickoff

- **Authoritative spec**: `PHASE_1_SPEC.md` is the contract. Any
  ambiguity not covered there is an open question, not an
  implementer's call. Open questions get filed as a comment on the
  Phase 1 milestone.
- **Language**: Python 3.11+. `pandas` permitted but not required —
  the reconciler's math is small enough to run on stdlib if a contributor
  prefers. Tests via `pytest`.
- **Test discipline**: TDD per fixture. For each of the 13 fixtures in
  PHASE_1_SPEC.md §10, write the expected JSON output BEFORE the code
  that makes it pass. Fixture #6 is load-bearing — it must fail under
  any row-walk implementation and pass only under event-walk.
- **PR chain over parallel tracks**: Phase 1 is small + sequential, so
  one track (`phase-1-reconciler`) with a chain of stacked PRs, not
  parallel feat-* tracks. Revisit for Phase 2.
- **Walk semantics is non-negotiable**: event-walk. Reviewers reject
  any PR that introduces row-walk logic, even as an "optimization."
  See PHASE_1_SPEC.md §1.1 + §5.

## 2026-04-30 — Agent harness adoption

- Bootstrapped via `agent-harness init`. See PR #2.
- Filed `dayfine/agent-harness#14` for three first-run polish issues
  (missing `.gitignore`, blind `CLAUDE.md` overwrite, stale stub
  comment in `bin/agent-harness`).
- `qc-structural-authority.md` and `qc-behavioral-authority.md` not
  yet written. Defer until first feat-agent dispatch needs them.
- `dev/lib/run-in-env.sh` ships generic; Python adaptation deferred to
  the first feat-agent that runs `pytest`.

## 2026-04-29 — Project bootstrap

- This repo exists because `trading-1`'s internal QC shares the same
  OCaml accounting code that generates the trades. External
  reconciler in a separate language closes the same-bug-passes-same-test
  hole. See `README.md` §"Why this lives in a separate repo".
- Phase boundaries fixed in README §Roadmap. Don't expand Phase 1
  scope — the value is in shipping the first version fast and
  validating the contract.
