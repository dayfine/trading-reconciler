---
harness: project
---

# Feature Agent Workflow (OCaml + jj + Docker Example)

Read by all feature agents at session start. Contains the shared workflow,
commit discipline, and session procedures.

## Branch setup

**Always branch from `main@origin`.** Never branch from another feature branch,
even if that feature is a dependency. Wait for dependencies to land in `main`
first (the dependency gate in your agent file enforces this).

```bash
jj git init --colocate 2>/dev/null || true
jj git fetch

# If your feature branch already exists on the remote (resuming a session):
jj new feat/<your-feature>@origin

# If starting fresh (bookmark does not exist on remote yet):
jj new main@origin
jj bookmark create feat/<your-feature> -r @
jj git push --bookmark feat/<your-feature>
```

Never commit to `main` directly.

## Development workflow

Work **one module at a time**. Full cycle per module:

1. Write `.mli` interface + skeleton → `dune build` passes → **commit**
2. Write tests → follow `CLAUDE.md` §"Test Patterns" (Matchers library) → **commit**
3. Implement → follow `CLAUDE.md` §"OCaml Idioms and Best Practices" → `dune build && dune runtest` passes → **commit**
4. `dune fmt` → **commit if anything changed**

Build/test inside Docker:
```bash
docker exec <container-name> bash -c \
  'cd /workspaces/<PROJECT_NAME>/<PROJECT_DIR> && <TOOLCHAIN_INIT_CMD> && <build_cmd> && <test_cmd>'
```

After each commit, tag the change with a per-module bookmark and push.
**This repo uses `jj` — never use bare `git` commands** (see `CLAUDE.md` §"Development Workflow"):
```bash
jj describe -m "your commit message"   # no git add needed
jj bookmark create <feature>/<module> -r @   # e.g. screener/sma, portfolio-stops/types
jj git push --bookmark <feature>/<module>
```

Also keep the top-level feature bookmark pointing at your latest change:
```bash
jj bookmark set feat/<your-feature> -r @
jj git push --bookmark feat/<your-feature>
```

Check your work:
```bash
jj status      # what changed
jj diff        # full diff
jj log -n 10  # recent history
```

## Commit discipline

- **One module per commit** — never batch multiple modules together
- **Target 200–300 lines per commit** (hard max ~400 including tests)
- **Push after every commit** — don't accumulate local-only work
- Each commit must build cleanly on its own

## Submitting for review (stacked PRs)

At session end, submit the full stack as stacked PRs using `jst`:

```bash
GH_TOKEN=$(echo "protocol=https\nhost=github.com" | git credential fill | grep ^password | cut -d= -f2)
GH_TOKEN=$GH_TOKEN jst submit feat/<your-feature>
```

This creates one PR per module bookmark, each targeting the one below it, so
reviewers can read changes one module at a time. Re-run after each session to
update existing PRs.

## Troubleshooting jst

### `Unexpected token '<', ..."commitId":<Error: No"... is not valid JSON`

**Cause:** jst's jj template calls `normal_target.commit_id()` on every local bookmark. If any bookmark is **conflicted** (shown as `(conflicted):` in `jj bookmark list`), jj emits `<Error: No normal target>` inline instead of a commit ID, producing invalid JSON.

**Fix:**
```bash
# Find conflicted bookmarks
jj bookmark list --revisions "mine() ~ trunk()" | grep conflicted

# Delete the offending bookmark (these are typically stale local artifacts
# that were never pushed to origin)
jj bookmark delete <conflicted-bookmark-name>
```

Then re-run `jst submit`.

## At the end of every session

Before returning:

1. `dune build && dune runtest` passes clean on your branch
2. All changes committed and pushed — nothing uncommitted
3. `dev/status/<your-feature>.md` updated (see your agent file for the exact fields)
4. If all work is complete and tests pass: set status to `READY_FOR_REVIEW`
5. Run `jst submit feat/<your-feature>` to create/update stacked PRs
