"""Generates the bootstrap skill from the role library.

The skill is the ignition for the pull loop: an MCP server cannot push, so the
build only advances while the session keeps calling charter_next. Generating
this file from the same definitions the kernel enforces means the instructions
and the enforcement can never drift apart.
"""
from pathlib import Path

from charter.library import load_methodologies, load_roles

_HEADER = """---
name: charter
description: Run a build under a governed role charter. Use whenever starting or continuing
  a project with charter installed - assigns roles by methodology, requires each role to
  produce a checkable artifact before it may sign off, and never lets a role approve its own
  work. Keep calling charter_next until it reports done.
---

# Charter

You are working under a role charter. One voice writing, reviewing and approving its own
work is the failure this exists to prevent, so the build advances one named role at a time
and each role owes a specific artifact before it may sign off.

## The loop

1. Call `charter_next`. It returns the role you are now playing, its brief, and the
   artifact contract it owes.
2. Do that role's work with your own tools. Stay in that role - do not solve the next
   role's problem because you can see it.
3. Call `charter_submit` with the artifact. If it is rejected, read the reason and fix
   what it names. You get three attempts before it escalates to the human.
4. **Keep calling `charter_next`** until it returns `done` or `escalated`. This is the
   whole discipline, and it decays exactly when work gets urgent - which is precisely
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


def render_skill() -> str:
    """Render SKILL.md from the current role and methodology definitions."""
    parts = [_HEADER]
    for role in load_roles().values():
        parts.append(
            f"\n**{role.name}** (`{role.id}`) - owes a `{role.contract.value}`.\n"
            f"{role.brief}\n")

    parts.append("\n## Methodologies\n")
    for m in load_methodologies().values():
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
