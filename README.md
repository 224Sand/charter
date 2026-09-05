# charter

**Governed multi-role delivery for AI coding agents.**

Claude Code, Cursor and Codex are competent generalists: one voice writes the code,
reviews the code, tests the code and declares it done. Charter makes that voice work as a
team of senior specialists instead, and enforces it — a role must produce a
machine-checkable artifact before it may sign off, and no role may sign off its own work.

The calling agent does all the execution. Charter is the conductor and the memory.

## Install

**Claude Code (recommended)** — one step, and it installs the server *and* the skill that
drives it:

```
/plugin marketplace add 224Sand/charter
/plugin install charter@charter
```

The two halves matter. The MCP server only answers when asked; it cannot push. Something has
to tell the calling agent to keep calling `charter_next` until the build is `done`, and that
is the bundled skill. Install the server without it and you get four tools nobody calls.

**Cursor, Codex, or manual MCP config:**

```json
{ "mcpServers": { "charter": { "command": "uvx",
    "args": ["--from", "git+https://github.com/224Sand/charter", "charter", "serve"] } } }
```

Then generate the skill yourself, since nothing else will:

```bash
charter gen-skill --dest .claude/skills/charter
```

`SKILL.md` is rendered from the same role and methodology definitions the kernel enforces, so
the instructions your agent reads and the rules it is held to cannot drift apart. That is
checked, not asserted: `tests/test_plugin.py` fails if the shipped copy goes stale.

## Use

```bash
charter init "harden the login path"     # derive the roster from the methodology
charter status                            # who has signed off, who is outstanding
```

Then in your agent session: call `charter_next`, do that role's work, call
`charter_submit` with its artifact, and keep going until it reports `done`.

`charter init` refuses to run against a repository that already has a charter — there is
no force flag. If you genuinely want to restart, delete the `.charter/` directory and
init again.

## What a role owes

| Role | Contract | Rejected when |
|---|---|---|
| Developer | `change_summary` | cites a file that does not exist |
| QA | `failing_test` | the named test **passes** — that is not evidence of a defect |
| AppSec | `threat_entry` | no CWE id, or an attack path too vague to act on |

Three failures on the same contract escalate to you rather than looping.

## Independence, honestly stated

Roles are separated by label, and each must submit its own contract artifact before it
may sign off. But in this v1, every role in a build is played by the same calling agent
— so the separation `no_self_signoff` enforces is structural (label and
artifact-of-record), not identity-verified. A single agent honestly submitting as
"developer" and then as "qa" satisfies both labels. What carries the weight is not that
different agents are involved; it is that each role must produce its own distinct,
checkable artifact before it may sign off. `charter_status` reports this same limitation
back to you as `independence`, so it is never mistaken for a stronger guarantee than the
mechanism provides.

## What the role separation proves

Charter stamps every server connection with an id the caller cannot set, records it on
each sign-off, and **refuses a review submitted from the same connection that produced the
work**. The practical shape: do the building in your main session, and run reviewing roles
from a second session on the same repository.

That proves a sign-off came from a separate process, and it still carries its own
checkable artifact. It does **not** prove independent reasoning — a server restart, an
agent deliberately restarting it, or a person clicking through two sessions without
reading all satisfy the mechanism. The artifact contract is what carries the weight;
identity raises the cost of collapsing the roles, it does not make it impossible.

`charter status` reports how many passes were issued and rejected, how many distinct
connections signed off, and how many bytes charter handed over — so a review pass that
starts getting expensive is visible before your bill is.

## One deployment requirement

QA's `failing_test` contract works by actually running the named test, so **charter must run
under an interpreter that can execute this repository's tests** — pytest importable, and the
project's own dependencies available. If pytest cannot run, charter refuses the submission and
says so; it never treats "could not run" as "the test failed", because that would accept any
submission as evidence.

In practice: run the server from the same environment you run your tests in, rather than a
bare `uvx` install, on projects with their own dependencies.

## Why the state lives on disk

Real builds outlast a session. `.charter/` holds the roster, current state, every
sign-off with its evidence, and an append-only transcript — human-readable and
git-diffable. A session with no prior context resumes the build from these files alone.

## License

MIT.
