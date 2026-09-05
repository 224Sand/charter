# Charter v2 — Independent Review Without the Token Bill

**Status:** Approved 2026-09-05 — decision #1 locked to *block*; plan at [../plans/2026-09-05-charter-v2.md](../plans/2026-09-05-charter-v2.md)
**Date:** 2026-09-05
**Builds on:** [v1 design](2026-09-05-governed-delivery-mcp-design.md) §7.4, which deferred genuine independence to v2

---

## 1. What v1 does not deliver

v1 ships a gate that cannot fire.

`no_self_signoff` compares `signoff.role` to `signoff.producer_role`. But `producer_role` comes
from `Council._producer_for()`, a hardcoded convention — the developer's producer is `"author"`,
everyone else's is `"developer"`. For the three v1 roles those values can never collide, so the
gate returns `allowed=True` on every real call site. It is exercised in `tests/test_gates.py`
and correct in isolation, and it protects nothing in the shipping product.

v1 is honest about this. `INDEPENDENCE_STATEMENT`, the `machine.py` docstring, the generated
skill and the README all say the same thing: roles are separated by label, every role is played
by the same calling agent, and separation is structural rather than identity-verified. What
carries the weight in v1 is the artifact contract — a test that genuinely fails, a CWE with a
concrete attack path — not the role boundary.

**v2's job is to make the role boundary real too, without becoming expensive enough that nobody
uses it.**

## 2. The tension, stated plainly

Two requirements point in opposite directions.

**Independence wants separate sessions.** A single agent submitting as `developer` and then as
`qa` has correlated blind spots regardless of what it labels itself.

**Cost wants one session.** This project's own build used subagent-driven development: a fresh
implementer per task, a fresh reviewer per task, re-reviews on every fix round. Twenty-six
dispatches at 50–145k tokens each. The orchestration cost more than the code it produced. A v2
that spawns a session per role reproduces exactly that bill.

Designing around the tension rather than picking a side is the whole content of this document.

## 3. Why charter can win where subagent-driven development lost

The cost in SDD was **cold-start exploration**. Each subagent was handed a task and a repository
and had to rebuild understanding: read the brief, find the files, infer the conventions, derive
the context its predecessor already had.

Charter's roles never explore. A role is handed a bounded artifact and the contract it owes:

> You are AppSec. Sprint 3, task 7. Here is the change summary and the three files it cites.
> Produce a `threat_entry` naming a CWE and a concrete attack path.

That is kilobytes. The reason it can be kilobytes is the property v1 already proved: **the build
record is the context.** A session with zero prior history reconstructs full state from
`.charter/` — roster, phase, sign-offs, defects, transcript — without reading the project.

So a role pass costs on the order of the artifact under review, not the project it lives in.

## 4. The asymmetry that buys the saving

Not every role needs a separate identity.

**The developer works in the main session.** That is where the code is being written, where the
context already exists, and where separation buys nothing — the developer is the producer, and
producers do not need to be independent of themselves. Zero additional cost.

**Only reviewing roles need a distinct identity**, and a review pass is inherently small: look at
this bounded artifact, apply this lens, produce this contract.

Net shape per task: the main session plus two short bounded review sessions — not N cold full
ones.

## 5. Design principles

Inherited from v1 and still binding: Claude Code is the brain and charter is the spine; an
approval is only valid when backed by a checkable artifact; methodology first, roster derived;
cite or drop; powerful, not bureaucratic; everything inspectable.

New in v2:

1. **The record is the context.** A role pass reads `.charter/` and the artifact. Never the repo.
2. **Bounded handover.** `next()` returns a minimal sufficient package. This is a constraint
   charter is held to by a test, not an aspiration.
3. **Cost is measured, not assumed.** If a review pass is getting expensive, `status` says so
   before the bill does.
4. **Claim exactly what is proven.** v2 proves two sign-offs came from different server
   processes. It does not prove they came from different reasoning. Say so.

## 6. Connection identity

**The mechanism.** charter's server runs as a stdio subprocess; each MCP client connection spawns
its own process. At startup the server generates a random `connection_id` (uuid4) and holds it in
memory for the life of that process. Every sign-off is stamped with it.

**Why it cannot be forged.** The agent never supplies the id. It is not a tool parameter, it is
not derived from anything the caller sends, and there is no tool that sets it. The server reads
its own. This is the entire reason to prefer it over a declared `agent_id`, which an agent could
set to anything.

**What the gate becomes.** `no_self_signoff` stops comparing role labels and starts comparing
identities: a reviewing role's sign-off on a given tree is refused when its `connection_id`
matches the `connection_id` of the developer's sign-off on that same tree.

This also retires `_producer_for()` — the synthetic convention is replaced by a recorded fact.

**What this honestly proves, and does not.** It proves two sign-offs came from two server
processes. Three ways that falls short of proving independent reasoning, all of which v2
discloses rather than papers over:

- **A server restart mid-session** produces a new id, so one session can look like two. Charter
  cannot distinguish a restart from a genuinely new session.
- **A deliberately adversarial agent** could restart the server to manufacture independence.
  Charter governs cooperative agents; it raises the cost of collapsing roles, it does not make it
  impossible.
- **A human clicking through two sessions without reading** satisfies the mechanism and defeats
  the point. Charter enforces structure, never diligence.

The honest v2 claim is therefore: *sign-offs are proven to come from distinct processes, and each
still carries its own checkable artifact.* That is materially stronger than v1, where the gate
proved nothing. It is not "verified independent review," and the product must not say it is.

## 7. The bounded handover

`next()` returns, and is limited to:

| Field | Content | Bound |
|---|---|---|
| role brief | the role's lens, from the library | one paragraph |
| contract | the artifact kind owed, and its shape | schema, not prose |
| artifact under review | the producer's submitted artifact | the artifact itself |
| cited files | the paths that artifact names | paths, not contents |
| build position | phase, task, open defects for this task | the record's own fields |

What it must never contain: repository contents, directory listings, git history, or any other
role's reasoning. The reviewing role reads what it needs *itself*, with its own tools, from the
paths it was given — the same discipline v1 already applies to the calling agent.

**This is enforced, not requested.** A test asserts the `next()` payload contains no file
contents and stays under a byte ceiling for a fixture build. When someone later adds a helpful
"here's the file for convenience" field, that test fails.

## 8. Cost accounting

`StatusResponse` gains a small cost section: passes issued, passes rejected, bytes handed over per
role, and distinct connections seen. None of it is a token count — charter cannot see the model's
billing — but bytes handed over is the quantity charter actually controls, and it is the leading
indicator of a handover that has started to bloat.

The point is not precision. It is that the design principle has a number attached to it, so a
regression is visible.

## 9. What changes in the code

| Component | Change |
|---|---|
| `mcp_server.py` | server generates `connection_id` at startup; `Handlers` carries it |
| `record/models.py` | `Signoff` gains `connection_id`; `producer_role` retired |
| `gates/checks.py` | `no_self_signoff` compares connection ids against the tree's developer sign-off |
| `loop/machine.py` | `_producer_for()` deleted; `next()` payload bounded; cost counters |
| `skillgen.py` | generated skill explains the two-session flow and what it does and does not prove |
| README | same, in the same substance as `INDEPENDENCE_STATEMENT` |

Backward compatibility: a v1 record has no `connection_id` on its sign-offs. Charter must read it
without crashing, and must say the independence check is unavailable for those rows rather than
silently passing them. An old record that quietly satisfies a new gate is exactly the failure this
project exists to prevent.

## 10. Non-goals

- **charter does not spawn sessions.** It has no LLM and no agent. It enforces; the user or the
  host orchestrates. Any design where charter starts an agent is out of scope.
- **No host-specific internals.** Nothing that depends on Claude Code's Task tool or any other
  host's private surface — it must work identically under Cursor and Codex.
- **Not an adversarial-agent defence.** Stated in §6 and disclosed in the product.
- **No remote/hosted mode.** charter reads the local tree, the local git state and the local test
  suite. A hosted charter would be governing a copy, which is worse than not governing at all.

## 11. Open decisions

| # | Decision | Recommendation |
|---|---|---|
| 1 | Does a missing second session **block** or **warn**? | **BLOCK — locked 2026-09-05.** A warning that can be ignored is v1's problem again. The block message must name exactly what to do. |
| 2 | Byte ceiling for the `next()` payload | Start at 8 KB for the fixture build and tighten once real handovers are measured. The number matters less than having one. |
| 3 | Does the developer role also need an id recorded? | **Yes** — it is the baseline every reviewer is compared against. It just never needs to be *different* from anything. |

## 12. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Two-session flow feels like friction and gets bypassed | **Highest** | The block message must say exactly what to do. Measure adoption against v1's one-session flow before defending the design |
| Server restart falsely reads as independence | High | Disclosed in §6, in the skill and in the README. Cannot be fixed from inside an MCP server |
| Cost saving does not materialise in practice | High | §8's counters exist precisely to find this out early rather than argue about it |
| v1 records silently pass the new gate | Medium | §9's backward-compatibility rule, with a test asserting an old row reports *unavailable* rather than *passed* |
| Scope creeps toward orchestration | Medium | §10, revisited at every phase boundary |

---

## Appendix: what v2 does not change

The kernel, the artifact contracts and their validators, the append-only record, the phase state
machine, the retry ceiling and escalation, and the CLI all stand. v2 is a change to *who is
recorded as having done a pass* and *how much is handed to them* — the mechanism that made v1
worth building is untouched.
