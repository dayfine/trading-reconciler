# AI Agent Instructions (CLAUDE.md / .geminirules)

This file is automatically read by AI coding assistants (like Claude Code, Gemini, or Cursor) when this repository is opened.

**CRITICAL INSTRUCTION FOR ALL AI AGENTS:**
You are operating in a workspace powered by the `agent-harness` framework. Before executing any task, you MUST auto-discover your role and workflow by reading the relevant playbooks inside the `.agents/agents/` directory (e.g., `lead-orchestrator.md`, `code-health.md`, `qc-structural.md`).

This repository is a template/scaffolding for orchestration harnesses. It reminds the agent of the three-layer model.

## What this repo is

A template / scaffolding for Claude Code orchestration harnesses. It
ships generic agents (lead-orchestrator, harness-maintainer,
health-scanner, code-health, qc-structural, qc-behavioral) plus
GitHub Actions workflows and `dev/` directory contracts (status,
plans, lib helpers).

See `README.md` for the full inventory and how to consume.

## Three-layer model

Every file under `.agents/agents/` and `.agents/rules/` carries a
YAML frontmatter `harness:` field with one of three values:

- `reusable` — ship as-is. Generic across any project.
- `template` — skeleton with `<TODO>` placeholders that each
  consuming project copies and fills in.
- `project` — project-specific (domain rules, tool lists, lint
  names). Lives only in the consuming project, never in this template.

When extending the harness here, only add `reusable` or `template`
files. Anything `project` belongs in the consuming repo.

## Consuming projects

A consuming project gets its own `CLAUDE.md` that points at its
codebase and project-specific rules (e.g. language patterns, domain
references). The harness layer is loaded on top and provides the
orchestration. The two CLAUDE.md files do not conflict — one is about
the project, one is about the agentic harness.

## Source

Extracted from a production system on 2026-04-26 per
`dev/plans/harness-template-extraction-2026-04-26.md` §Phase 2 in
the source repo.
