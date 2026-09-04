"""Methodology -> active roster.

Deterministic and LLM-free on purpose: the same methodology always yields the
same roster in the same order, which is what makes the governance auditable.
"""
from charter.kernel.models import MethodologyDef, RoleDef, Roster


class UnknownMethodology(Exception):
    """The methodology, or a role it names, is not defined."""


def roster_for(
    methodology_id: str,
    methodologies: dict[str, MethodologyDef],
    roles: dict[str, RoleDef],
) -> Roster:
    """Derive the active roster. Order follows the methodology's declaration."""
    methodology = methodologies.get(methodology_id)
    if methodology is None:
        raise UnknownMethodology(
            f"{methodology_id!r} is not a defined methodology; "
            f"known: {sorted(methodologies)}"
        )

    active: list[RoleDef] = []
    for role_id in methodology.roles:
        role = roles.get(role_id)
        if role is None:
            raise UnknownMethodology(
                f"methodology {methodology_id!r} names role {role_id!r}, "
                f"which is not defined"
            )
        if methodology_id not in role.activates_on:
            continue
        active.append(role)

    if not active:
        raise UnknownMethodology(
            f"methodology {methodology_id!r} activates no roles"
        )
    return Roster(methodology=methodology_id, roles=active)
