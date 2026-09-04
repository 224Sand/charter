# Governed Multi-Role Delivery for AI Coding Agents

**Status:** Approved 2026-09-05 — implementation plan to follow
**Date:** 2026-09-05
**Supersedes:** the markdown-only `role-council` Claude Skill (this repo, as of 2026-08-28)

> **Name:** `charter`. **Stack:** Python. Both decided 2026-09-05 — see §12.

---

## 1. Problem

AI coding agents are competent generalists. Given a real build, one voice does everything:
writes the code, reviews the code, tests the code, and declares it done. Three failures follow,
and they are the same three that limit every autonomous coding agent on the market:

**Circular verification.** The model that wrote the bug writes the test that misses it. An agent
cannot be its own QA, because its blind spots are correlated across both passes. "It works" is
asserted, never demonstrated.

**Long-horizon decay.** Real builds take days and many sessions. Context compacts, sessions end,
machines sleep. Constraints agreed on day one are gone by day six. The failure mode is not a
visible error — it is confidently going sideways for forty minutes.

**Stuck loops.** The same fix, the same failure, again. Without an escalation path an agent will
retry a dead approach indefinitely.

Existing tooling addresses neither:

| Category | Examples | What it does | What it misses |
|---|---|---|---|
| Persona / sub-agent | `sub-agents-mcp`, `Orchestrator-mcp`, CrewAI crews | Multiple AI voices review code | Role-play. Zero enforcement — a role can approve anything, or nothing |
| Agent governance | MS Agent Governance Toolkit, Aperion Shield, Agent Hooks | Blocks `rm -rf`, `DROP TABLE`, force-push | **Safety**, not craft. Stops harm; says nothing about whether the work is any good |

Nobody governs **craft**. That position is open.

## 2. What this is

An MCP server that turns a Claude Code / Cursor / Codex session into a governed team of senior
specialists, and keeps it governed across a build that spans days.

You attach it, hand it an idea, and it drives the session through a full delivery lifecycle —
brainstorming, requirements, architecture, implementation, QA, security review — with a named
role responsible for each pass and a machine-checkable artifact required before that role may
sign off. When you later tweak the product, the council re-derives what that invalidated and
which roles must re-review.

**The load-bearing insight: Claude Code is the compute. This is the conductor and the memory.**

That single constraint removes the three most expensive problems in autonomous coding agents:

| Autonomous-agent hard problem | How we avoid it |
|---|---|
| Sandboxed execution infrastructure | Claude Code already runs on the user's machine with their permissions |
| Environment reality (private deps, auth, tribal setup) | Same — it is the user's real environment, not a synthetic VM |
| Token economics | The user brings their own subscription. We never hold the bill |

And it leaves us attacking exactly the three that remain unsolved:

| Autonomous-agent hard problem | What we build |
|---|---|
| Long-horizon coherence | A durable build record that survives context compaction and session death |
| Circular self-verification | Enforced artifact contracts + no role signs off its own work |
| Stuck-loop recovery | Retry ceiling → escalation, not infinite retry |

This is not a smaller Devin. It is the governance layer Devin-class agents lack.

## 3. Non-goals

Held deliberately, and cheaply violated if not written down:

- **No sandboxed code execution.** The calling agent has Bash/Edit/Write. We never reimplement it.
- **No infrastructure provisioning, no deploy platform.** The agent runs the user's own deploy commands.
- **No bundled LLM.** The calling agent *is* the model. We hold no API keys by default.
- **No monetization surface.** No accounts, no auth, no telemetry, no hosted service, no
  free-vs-pro split. Everything runs locally and belongs to the user. This is a contribution and
  a credibility artifact, not a business.
- **Not a Devin competitor.** We do not compete on autonomy. We compete on whether the work is
  actually senior.
- **No fixed role roster.** A roster identical across two very different projects is a bug.

## 4. Design principles

1. **Claude Code is the brain; we are the spine.** Every temptation to do the agent's job is scope creep.
2. **An approval is only valid when backed by a checkable artifact.** Prose can be copied and faked. A contract cannot.
3. **No role signs off its own work.** The rule that stops multi-role collapsing into one voice agreeing with itself.
4. **Methodology first, roster derived.** Scrum has no Change Control Board; Waterfall has no retrospective. A roster picked before a methodology is a cast list, not governance.
5. **Cite or drop.** A claim that cannot point to a real artifact is not council material. Manufactured consensus and manufactured conflict are equally dishonest.
6. **Powerful, not bureaucratic.** The developer must feel like they have a senior team behind them, never like they are filing paperwork. Governance that feels like compliance gets ripped out. This is the primary UX constraint and it outranks completeness.
7. **Everything is inspectable.** Any block must state which role, which contract, and what is missing. No black boxes.

## 5. Architecture

### 5.1 The pull-loop truth

**MCP servers cannot push. They only answer.** Tools are request/response; the server cannot
autonomously drive a session. So "the council runs the build" is really a pull loop the calling
agent sustains:

```
Claude Code  →  charter.next()
                   ← "You are QA Lead. Sprint 3, task 7. D-004 is open.
                      Produce a failing test that reproduces it before you may approve."

Claude Code  →  (does the work with its own tools: Bash, Edit, Write)

Claude Code  →  charter.submit(role="qa", artifact={...})
                   ← REJECTED: contract `failing_test` requires a test that fails
                     against the current tree. Attached test passes. Re-issue same role.

Claude Code  →  charter.submit(role="qa", artifact={...})
                   ← ACCEPTED. Sign-off recorded. State advanced.

Claude Code  →  charter.next()
                   ← "You are AppSec. Sprint 3, task 7 touched the auth path..."
```

The loop closes because the agent keeps calling `next()`. What makes it *keep* calling is the
bootstrap skill plus a `CLAUDE.md` entry. **That is the real job of the plug-and-play tier — it
is not a lite version, it is the ignition.**

### 5.2 Layers

| Layer | Responsibility | Depends on |
|---|---|---|
| **Kernel** | methodology → roster (deterministic, no LLM) · artifact contracts · gates | nothing |
| **Build record** | append-only durable state: sprints, decisions, defects, sign-offs + evidence | kernel (for schema) |
| **Loop** | phase state machine; `next` / `submit` / `status`; rejection and re-issue | kernel, record |
| **MCP surface** | exposes the loop as tools to any MCP client | loop |
| **Bootstrap skill** | ignition + the discipline that keeps a session in the loop | generated from kernel |
| **CI gate** *(v1.1)* | reads the same record; fails a PR on missing role coverage or self-signoff | record |

Each layer is usable and testable without the one above it. The kernel has no I/O. The record has
no LLM. The loop has no MCP. This is what makes the CI gate a thin adapter later rather than a
rebuild.

## 6. The build record

**This is the heart of the system, and the part nobody can reproduce with a clever prompt.**

SandScope took nine sprints. No agent session survives that. The record on disk is the build's
memory — it is what makes `next()` answerable on day six by a session that has never seen days
one through five.

Stored at `.charter/` in the target repository, human-readable, git-committable:

```
.charter/
  charter.json        methodology in force, active roster, why each role is active
  state.json          current phase, sprint, task, what is blocked and on whom
  decisions/          one file per decision: what, who decided, under which role's authority
  defects/            defect log with status and owning role
  signoffs/           per-role approvals, each with its artifact and validation result
  transcript.jsonl    append-only event log — every next/submit/reject, timestamped
```

Three properties are non-negotiable:

- **Append-only.** History is never rewritten. A rejected submission stays visible; that is the audit trail.
- **Human-readable and diffable.** It is committed to git. A reviewer reads it without our tooling.
- **Self-describing.** A session with zero prior context reconstructs the full build state from these files alone.

Re-entrance falls out of this for free. A user tweak is new input against existing state: the
council re-derives which decisions it invalidates and which roles must re-review — because the
decisions and their dependencies are recorded, not remembered.

## 7. Components

### 7.1 Methodology engine
**Does:** maps a methodology to its active role set and its decision points. Pure functions over
YAML definitions. Zero LLM — the same project always yields the same roster, which is what makes
the governance auditable.
**Use:** `roster_for(methodology, project_signals) -> Roster`
**Depends on:** methodology + role definition files.

### 7.2 Role library
**Does:** holds each role's brief (what this role instinctively looks for, its real failure modes,
the questions a senior actually asks) and its artifact contract. Grounded in real standards where
they exist — CWE and OWASP ASVS for AppSec, test-design heuristics for QA, ADR practice for
architecture.
**Use:** `role("appsec") -> RoleDef`
**Depends on:** nothing. Plain YAML — the portable intellectual core.

### 7.3 Artifact contracts
**Does:** defines and validates what each role must produce to complete a pass. Not prose — a
schema plus a real check.

| Role | Contract | Validated by | v1 |
|---|---|---|---|
| Developer | `change_summary` | must cite the files changed and the decision it implements | ✅ |
| QA | `failing_test` | the test must actually fail against the current tree before the fix, and pass after | ✅ |
| AppSec | `threat_entry` | must name a CWE ID and a concrete attack path; "consider validating input" is rejected | ✅ |
| Architect | `decision_record` | must name the rejected alternative and its cost; a record listing only advantages is rejected | — |
| BA | `requirement_trace` | must cite the requirement ID the change traces to | — |

**Use:** `validate(role, artifact, repo_state) -> Accepted | Rejected(reason)`
**Depends on:** role library, git access for the checks that need the tree.

### 7.4 Gates
**Does:** cross-cutting rules the loop enforces. `no_self_signoff` (the role that produced the
work may not be the role that approves it). `role_coverage` (a phase cannot close while a
required role has not run). `staleness` (a sign-off against a tree that has since changed is
void).
**Use:** `check(state, proposed_transition) -> Allowed | Blocked(reason)`
**Depends on:** build record.

**How `no_self_signoff` works when one session plays every role.** This is the obvious objection
and it deserves a straight answer: the independence is *structural*, not *model* independence.
The record stores which role produced each artifact; the gate refuses a sign-off where
`producer_role == approver_role`. Three things make that more than bookkeeping:

1. **Separate passes with only the artifact as interface.** The approving role is issued the
   artifact and its own contract — not the producer's reasoning. It cannot inherit the argument
   that justified the work, only the work itself.
2. **The contract is objective.** A test that fails before a fix and passes after is evidence
   regardless of who wrote it. This is what actually breaks the correlation between the
   producer's blind spots and the approver's — not the role label.
3. **The record makes it auditable.** Every pass is timestamped in `transcript.jsonl`, so
   collapsed or skipped independence is visible after the fact.

Stated honestly: one model playing both parts still has partially correlated blind spots. We do
not claim otherwise. The artifact contract is the mechanism that carries the weight here; the
role separation is what forces the artifact to exist. Genuinely independent passes — one session
per role — are a v2 upgrade on this same architecture, and the gate does not change when they
arrive.

### 7.5 Loop / phase state machine
**Does:** owns what happens next. Holds the phase graph (idea → requirements → architecture →
implementation → verification → release), issues the next role assignment, routes submissions to
validation, records outcomes, and decides advance-vs-re-issue-vs-escalate.
**Use:** `next(record)`, `submit(record, role, artifact)`, `status(record)`
**Depends on:** kernel, record.

### 7.6 MCP surface
**Does:** exposes `next`, `submit`, `status`, plus read-only resources for the charter and the
defect log. Thin — no logic of its own.
**Depends on:** loop.

### 7.7 Bootstrap skill
**Does:** the ignition. A generated `SKILL.md` that tells a session to attach the server, call
`next()`, and keep calling it. Generated *from* the role library so the skill and the code can
never drift.
**Depends on:** role library.

## 8. Data flow

```
idea ──► charter.init ──► methodology engine ──► roster ──► charter.json
                                                              │
        ┌─────────────────────────────────────────────────────┘
        ▼
   ┌── next() ──► role assignment + contract + context from record
   │       │
   │       ▼
   │  calling agent does the work (its own tools)
   │       │
   │       ▼
   │  submit(role, artifact)
   │       │
   │       ├──► contract validation ──► gates ──┐
   │       │                                     │
   │       │◄── REJECTED (reason, retry n/3) ◄───┤
   │       │                                     │
   │       │    ESCALATE (n=3) ──► human ────────┤
   │       │                                     │
   │       └──► ACCEPTED ──► record signoff ─────┘
   │                              │
   └──────────────────────────────┘
                                  │
                    phase complete? ──► advance ──► ... ──► release
```

## 9. Error handling and edge cases

**Termination.** "Loop until a product is made" needs a checkable definition or it never stops.
Done is: every acceptance criterion in the requirements artifact has a passing verification
artifact, every required role has signed off on the current tree, and no blocking defect is open.
Not a vibe — a predicate over the record.

**Rejection loops.** A role failing the same contract three times escalates to the human with the
three attempts and the validator's reasons attached. Never infinite retry. (Same pattern as the
3-retry ceiling in the multi-agent orchestration platform.)

**Session death mid-pass.** A submission is either fully recorded or not recorded. On restart,
an issued-but-unsubmitted assignment is simply re-issued — the record is the truth, not the
session.

**The agent ignores the loop.** The most likely real failure. The bootstrap skill can be
forgotten under pressure — exactly when the role that would have objected is the one being
skipped. Mitigation: `status()` reports drift (work landed in the tree with no corresponding
sign-off), and the v1.1 CI gate catches it at the merge boundary where it cannot be ignored.

**Token cost.** Every role pass is real inference; a governed multi-sprint build is expensive.
The design states this honestly rather than hiding it. `status()` reports passes consumed, and
roster scope is the user's lever.

**Conflicting roles.** Genuine unresolved disagreement between two roles blocks and escalates to
the human. We do not auto-resolve — the disagreement is the value.

## 10. Testing strategy

- **Kernel** — pure functions, exhaustively unit-tested. Same methodology + signals always yields the same roster.
- **Contracts** — each validator gets a known-good and a known-bad fixture. The known-bad must be rejected; a validator that only ever passes is not a validator. (Pattern proven in SandScope: four guard scripts ship their own regression test proving they fail on a bad fixture.)
- **Gates** — self-signoff and staleness tested against constructed records.
- **Loop** — state machine transitions tested without MCP or LLM in the path.
- **Resumability** — the acceptance test that matters: build a record to sprint 3, discard all in-memory state, restart, and assert `next()` returns the identical assignment.
- **End-to-end** — one narrow scripted build against a fixture repo, asserting the record's final shape.

## 11. v1 scope

Ship the **mechanism** at 90%, then scale content into it. Five roles with enforced contracts
beat twenty with prose briefs; adding roles later is easy, retrofitting mechanism quality is not.

**In v1:**
- Kernel: 2 methodologies (Scrum, CI/CD), 3 roles (Developer, QA, AppSec)
- Artifact contracts for those 3, with real validators
- Gates: `no_self_signoff`, `role_coverage`
- Build record, fully resumable
- Loop with rejection, retry ceiling, escalation
- MCP server: `next` / `submit` / `status`
- Bootstrap skill, generated
- Proof: one real end-to-end governed build

**Explicitly deferred:** the remaining methodologies and roles, the CI gate and GitHub Action,
parallel role sessions, review mode over historical repos.

**The v1 bar is the loop, proven end to end.** Not breadth.

## 12. Decisions

All locked 2026-09-05.

| # | Decision | Outcome | Rationale |
|---|---|---|---|
| 1 | **Stack** | **Python** | Technically a coin flip for this workload — it calls APIs, validates schemas, runs git. Python wins on one toolchain (no committed `ncc` bundle), build velocity, and coherence with SandScope / the orchestration platform / the RAG harness / jobagent. Costs ~5-10s of `setup-uv` on the Action. |
| 2 | **Name** | **`charter`** | Means the founding document establishing roles, authority, and what a decision requires — literally what this is. Ties to SandScope's own 17-role delivery charter. PyPI name available. Rejected: `docket`, `rollcall` (both free but semantically lighter); `quorum`, `warrant`, `cadre`, `praxis` (taken). |
| 3 | **v1 roster** | Developer, QA, AppSec | The three with the sharpest, most obviously checkable contracts. BA and Architect follow immediately after. |

Consequences: package `charter` on PyPI, repo `224Sand/charter`, state directory `.charter/`,
MCP tools namespaced `charter.*`, installed via `uvx charter`. The GitHub repo keeps the
`role-council` name until the v1 release, at which point it is renamed (GitHub redirects the
old URL, so nothing breaks).

## 13. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Feels like bureaucracy** | **Highest.** Kills adoption outright | Principle 6 outranks completeness. Every block states role, contract, and what is missing. Ruthlessly prune any gate that does not change an outcome |
| Agent silently abandons the loop | High | `status()` drift detection; CI gate at the merge boundary in v1.1 |
| Contracts too rigid for real work | High | Contracts validate *shape and evidence*, never content. A role may legitimately answer "nothing to weigh in on here" |
| Token cost deters use | Medium | Honest reporting; roster scope as the user's lever |
| Loses to a well-funded incumbent | Medium | The niche is craft governance, not autonomy. Incumbents compete on autonomy |
| Scope creep into building an executor | Medium | Non-goals in §3, revisited at every phase boundary |

---

## Appendix: what carries over

The existing `SKILL.md` and `references/` are not discarded. The methodology tables and role
archetype briefs are the seed of the role library (§7.2) — the same content, moved from prose an
agent is asked to follow into data the kernel enforces. The prompting discipline becomes the
bootstrap skill (§7.7), generated rather than hand-maintained.
