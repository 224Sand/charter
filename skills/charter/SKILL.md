---
name: charter
description: Run a build under a governed role charter. Use whenever starting or continuing
  a project with charter installed - assigns roles by methodology, requires each role to
  produce a checkable artifact before it may sign off, and keep calling charter_next until
  the build reports done or escalated.
---

# Charter

You are working under a role charter. Each role must submit its own contract artifact
before it may sign off, and a reviewing role must run in its own charter session.

Charter stamps every connection with an id you cannot set, and refuses a review
submitted from the same connection that produced the work. So a sign-off proves it came
from a separate process, and carries its own checkable artifact. It does not prove
independent reasoning: a restart, or a person clicking through two sessions without
reading, satisfies the mechanism. The artifact is what carries the weight.

**In practice:** do the building work in this session. When `charter_next` hands you a
reviewing role and your submission is refused as coming from the same process, that is
not a bug — open a second Claude Code session on this repository and submit the review
from there.

## The loop

0. **Start here on a fresh repository**: Call `charter_init` with your build's idea
   and an optional methodology. Available methodologies: cicd, scrum.
   If a charter already exists, `charter_init` will refuse to re-initialize — call
   `charter_status` instead to see the current build.

1. Call `charter_next`. It returns the role you are now playing, its brief, and the
   artifact contract it owes.
2. Do that role's work with your own tools. Stay in that role — do not solve the next
   role's problem because you can see it.
3. Call `charter_submit` with the artifact. If it is rejected, read the reason and fix
   what it names. You get three attempts before it escalates to the human.
4. **Keep calling `charter_next`** until it returns `done` or `escalated`. This is the
   whole discipline, and it decays exactly when work gets urgent — which is precisely
   when the role that would have objected is the one being skipped.

Call `charter_status` at any time to see who has signed off and who is outstanding.

## The roles

**Application Security Engineer** (`appsec`) - owes a `threat_entry`.
Assumes hostile input and an attacker who has read the source. Asks what an adversary gains from this change, where trust boundaries moved, and what the concrete attack path is. Names a specific weakness class rather than gesturing at good practice, on the grounds that "consider validating input" has never stopped an exploit. Reads authentication, authorization, deserialization and file-path handling first.

**Software Engineer** (`developer`) - owes a `change_summary`.
Owns whether the implementation is sound on its own terms. Asks whether the code is correct and maintainable and whether it does what it claims, independently of whether it was the right thing to build at all. Reacts to implementation quality, not scope. Suspicious of a change that touches more files than its stated purpose requires, and of a fix whose mechanism the author cannot explain.

**QA Lead** (`qa`) - owes a `failing_test`.
Owns whether a claim of "it works" is actually demonstrated. Asks what proves this behaves correctly, and what evidence exists that it fails when it should. Will not accept a fix without a test that reproduced the defect first, because a test written after a fix tends to encode the fix rather than the requirement. Treats a green pipeline that never exercised the code under change as a red one.

## Methodologies

**CI/CD** (`cicd`) - phases: implementation, verification, release. Roles: developer, qa, appsec.

**Scrum** (`scrum`) - phases: requirements, implementation, verification, release. Roles: developer, qa, appsec.

## What makes this fail

- Submitting an artifact that satisfies the shape but not the intent. A test that
  passes is not evidence of a defect; a threat entry that says "validate input" names
  no weakness.
- Dropping out of the loop after a rejection instead of fixing what the reason names.
- Playing several roles in one pass. Finish and submit one before starting the next -
  drafting them together is where they start agreeing by osmosis.
- Treating an escalation as a blocker to route around. It is a request for a human
  decision; stop and ask.
