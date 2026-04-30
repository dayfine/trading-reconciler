---
harness: template
---

# Feature Agent Workflow

Read by all feature agents at session start. Contains the shared workflow, commit discipline, and session procedures.

## Branch setup

**Always branch from the trunk/mainline.** Never branch from another feature branch, even if that feature is a dependency. Wait for dependencies to land in the main branch first (the dependency gate in your agent file enforces this).

```bash
# <TODO: Add your project-specific VCS commands for syncing and branching here>
# Example: git checkout -b feat/<your-feature> origin/main
```

Never commit to the main branch directly.

## Development workflow

Work **one module at a time**. Full cycle per module:

1. Write interface/skeleton → `<build_cmd>` passes → **commit**
2. Write tests → follow test patterns → **commit**
3. Implement → follow project idioms → `<build_cmd> && <test_cmd>` passes → **commit**
4. Run code formatter (`<format_cmd>`) → **commit if anything changed**

If you use a containerized environment, execute commands inside the container:
```bash
# <TODO: Add your project-specific container execution command here>
# Example: docker exec <container-name> bash -c 'cd /workspace && <build_cmd>'
```

After each commit, tag the change and push.
```bash
# <TODO: Add your project-specific VCS commands for committing and pushing here>
# Example: git add . && git commit -m "feat: your commit message" && git push
```

Check your work:
```bash
# <TODO: Add your project-specific VCS commands for checking status/diff here>
# Example: git status, git diff
```

## Commit discipline

- **One module per commit** — never batch multiple modules together
- **Target 200–300 lines per commit** (hard max ~400 including tests)
- **Push after every commit** — don't accumulate local-only work
- Each commit must build cleanly on its own

## Submitting for review

At session end, submit your work for review:

```bash
# <TODO: Add your project-specific commands for creating/updating PRs here>
# Example: gh pr create --fill
```

## At the end of every session

Before returning:

1. `<build_cmd> && <test_cmd>` passes cleanly on your branch
2. All changes committed and pushed — nothing uncommitted
3. `dev/status/<your-feature>.md` updated (see your agent file for the exact fields)
4. If all work is complete and tests pass: set status to `READY_FOR_REVIEW`
5. Create or update Pull Requests for your work.
