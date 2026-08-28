# role-council

![claude skill](https://img.shields.io/badge/claude-skill-CC785C) ![license](https://img.shields.io/badge/license-MIT-green) ![two modes](https://img.shields.io/badge/modes-operating%20%2B%20review-blue)

**Assigns delivery roles by methodology, then either works under them live or replays a repository's real history through them.** Pick Scrum, Kanban, SAFe, Waterfall, or CI/CD; the methodology determines who exists and what a decision requires; name a role before every substantive action; never let one role sign off its own work.

A retrospective where every role agrees on everything isn't a review — it's a rubber stamp with labels on it. This exists to force real disagreement onto the record the way a real cross-functional team produces it: a developer calling something clean, QA approving it on visual grounds, a BA flagging it against the actual requirement, a TPM asking whether the numbers even make sense.

## Two modes

**Operating mode** — assign roles for a session or a whole project and work under them.

```
Role: QA Lead — verifying the fix against a failing case first.
```

Named *before* the action, not after. A role named afterwards is a label on work already done; named first, it changes what you do next, because it tells you what you're optimising for. The methodology decides where a stop is required — Sprint Review in Scrum, a phase gate in Waterfall, the point of pull in Kanban — so execution inside an already-approved decision continues without a stop on every line.

**Review mode** — replay a git repository's real history through those roles.

```
## D-001 — a test suite reported 0% errors when the real rate was 56.6%
- QA Lead: the sample was 22 questions written by the person who built the gate...
- Business Analyst: a 0% error rate should have triggered a question before...
- TPM: this changes how I'd read every other reported metric in this project...
```

Every reaction cites a real defect ID, commit, or file. If a claim can't be cited, it's dropped rather than invented — a role-perspective feature is trivially fakeable, and manufactured disagreement is exactly as dishonest as manufactured consensus.

## Why methodology comes first

Scrum has no Change Control Board. Waterfall has no retrospective. Kanban has no sprint. A role set picked before a methodology produces a committee that can't decide anything, because nobody knows what a decision *is* on this project. `references/methodologies.md` covers Scrum, Kanban, SAFe, Waterfall/stage-gate, and CI/CD as a delivery layer — each with its real authority table, where a decision is actually made, and its characteristic failure mode (Scrum: a retrospective action nobody checks at the next retrospective; CI/CD: a pipeline whose green result doesn't exercise the code under change).

`references/role-archetypes.md` is the library of individual role lenses — what a BA looks for versus a DevOps engineer versus an AppSec engineer — used once the methodology has picked the active roster.

## Using it

Copy this repository into `.claude/skills/role-council/` in any project, or point a Claude Code session at this path directly. It has no dependency on the project it's used in — both reference files are self-contained, and the methodology library and role archetypes generalize to any codebase or team.

Review mode works best on a repo with *some* real history — a defect log, ADRs, closed PRs with review comments, or at minimum commits with real fixes in them. A brand-new repo with one commit has nothing for the council to react to yet.

## What makes it fail

- Skipping the methodology step — a cast list is not a governance structure
- Naming the role after the work — it becomes a label instead of a constraint
- Inventing an opinion with no citation, or manufacturing conflict for drama
- A fixed roster that looks identical across two very different projects
- Quietly dropping the discipline mid-session, which happens exactly when work gets urgent — precisely when the role that would object is the one being skipped

## Origin

Extracted from [SandScope](https://github.com/224Sand/sandscope), an agent-reliability platform whose entire build ran under a named-role charter. Its defect log already contained real per-role friction — a QA reaction, a BA reaction, a TPM reaction, on the record for the same incidents — and it became clear that discipline was worth having on any repository, not just one. SandScope's own [council retrospective](https://github.com/224Sand/sandscope/blob/main/docs/00-governance/COUNCIL_RETROSPECTIVE.md) is this skill's first real output.

## License

MIT. Fork it, change the role library, point it at your own project or process.
