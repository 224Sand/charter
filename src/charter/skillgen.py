"""Generates the bootstrap skill from the role library.

The skill is the ignition for the pull loop: an MCP server cannot push, so the
build only advances while the session keeps calling charter_next. Generating
this file from the same definitions the kernel enforces means the instructions
and the enforcement can never drift apart.
"""
from pathlib import Path

from charter.library import load_methodologies, load_roles

_HEADER_TEMPLATE = """---
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
   and an optional methodology. Available methodologies: {methodology_ids}.
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
"""

_FOOTER = """
## What makes this fail

- Submitting an artifact that satisfies the shape but not the intent. A test that
  passes is not evidence of a defect; a threat entry that says "validate input" names
  no weakness.
- Dropping out of the loop after a rejection instead of fixing what the reason names.
- Playing several roles in one pass. Finish and submit one before starting the next -
  drafting them together is where they start agreeing by osmosis.
- Treating an escalation as a blocker to route around. It is a request for a human
  decision; stop and ask.
"""


def render_skill(definitions_root: Path | None = None) -> str:
    """Render SKILL.md from the current role and methodology definitions.

    Args:
        definitions_root: Optional path to a custom definitions root. If None,
                         uses the default library location.
    """
    roles = load_roles(definitions_root)
    methodologies = load_methodologies(definitions_root)

    # Generate methodology IDs list
    methodology_ids = ", ".join(sorted(methodologies.keys()))
    header = _HEADER_TEMPLATE.format(methodology_ids=methodology_ids)

    parts = [header]
    for role in roles.values():
        parts.append(
            f"\n**{role.name}** (`{role.id}`) - owes a `{role.contract.value}`.\n"
            f"{role.brief}\n")

    parts.append("\n## Methodologies\n")
    for m in methodologies.values():
        parts.append(
            f"\n**{m.name}** (`{m.id}`) - phases: {', '.join(m.phases)}. "
            f"Roles: {', '.join(m.roles)}.\n")

    parts.append(_FOOTER)
    return "".join(parts)


def write_skill(dest: Path) -> Path:
    """Write the generated skill to `dest/SKILL.md`."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "SKILL.md"
    path.write_text(render_skill())
    return path
