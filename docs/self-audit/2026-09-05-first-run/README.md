# Self-audit, first run — charter pointed at itself

Charter was asked to govern a change to its own codebase. **The build did not
complete**, and that is the useful part.

## What the record shows

`transcript.jsonl`, verbatim: the developer pass was accepted; QA was issued and
**rejected twice**, then stopped with one attempt remaining rather than
manufacture evidence.

Rejection 1 — charter refused a submission it could not verify:

> cannot verify tests/test_loop.py::…: pytest is not available to the
> interpreter charter is running under

Rejection 2 — charter refused a test that proved nothing:

> …passes against the current tree, so it is not evidence of defect T-1

## What it found

1. **A shipping bug.** The first rejection led to `uv sync --extra dev`, which put
   the project's real virtualenv in play and exposed that `mcp>=1.2` resolved to
   2.1.1 — a major version whose decorator API charter does not use. Charter's MCP
   server was broken against the SDK its own `pyproject.toml` selects. Every fresh
   install would have hit it. The failure had been masked because the suite was
   running under an unrelated interpreter that happened to have mcp 1.x.

2. **A design flaw in charter's own loop.** The reviewing agent — a separate
   context with its own connection id — concluded that QA's `failing_test`
   contract could not honestly be satisfied, because the loop ran
   developer → qa and handed QA a tree where the fix was already applied. Red
   after green. Fixed in `7359399`.

3. **A limit on what the contract checks.** `validate_failing_test` verifies
   *mechanism* (pytest's exit code), not *meaning* — it cannot distinguish a
   genuine regression test from any other failing assertion.

## Why this is published

A tool that governs code review is trivially easy to demo successfully and
trivially easy to fake. This is the opposite artifact: charter run against its own
repository, refusing its author, with the rejections left in.
