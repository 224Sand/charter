"""The loop.

An MCP server cannot push, only answer -- so the build advances because the
calling agent keeps asking `next()`. This class owns what "next" means.

Independence note: roles are separated by label, and each role must submit its
own contract artifact before it may sign off. In this v1 configuration every
role is played by the same calling agent, so the separation `no_self_signoff`
enforces is structural (label and artifact-of-record), not identity-verified
-- a single agent honestly submitting as "developer" and then as "qa"
satisfies both labels. `StatusResponse.independence` states this plainly so
it is never mistaken for a stronger guarantee than the mechanism provides.
"""
from pathlib import Path

from pydantic import BaseModel, ValidationError

from charter.contracts.models import parse_artifact
from charter.contracts.validators import validate
from charter.gates.checks import (_PRODUCER_ROLE, no_self_signoff,
                                  role_coverage)
from charter.kernel.models import ArtifactKind
from charter.record.models import Assignment, Signoff, TranscriptEvent
from charter.record.store import RecordStore
from charter.vcs import tree_sha

MAX_ATTEMPTS = 3

INDEPENDENCE_STATEMENT = (
    "roles are separated by label, and each must submit its own contract "
    "artifact before it may sign off; but every role in this build is played "
    "by the same calling agent, so independence here is structural (label "
    "and artifact-of-record), not identity-verified."
)



def _cited_paths(artifact) -> list[str]:
    """The paths an artifact names, whatever kind it is."""
    for field in ("files", "affected_files"):
        if hasattr(artifact, field):
            return list(getattr(artifact, field))
    if hasattr(artifact, "test_path"):
        return [artifact.test_path]
    return []


class NextResponse(BaseModel):
    kind: str                      # "assignment" | "done" | "escalated"
    assignment: Assignment | None = None
    reason: str = ""


class SubmitResponse(BaseModel):
    accepted: bool
    reason: str = ""
    attempts_remaining: int = MAX_ATTEMPTS
    escalated: bool = False


class StatusResponse(BaseModel):
    phase: str
    task_id: str
    methodology: str
    roles: list[str]
    signed_off: list[str]
    outstanding: list[str]
    escalated: bool
    escalation_reason: str = ""
    passes: int
    # What the handover is costing. Not token counts -- charter cannot see the
    # model's billing -- but bytes handed over is the quantity charter controls,
    # and it is the leading indicator of a handover that has started to bloat.
    passes_issued: int = 0
    passes_rejected: int = 0
    bytes_handed_over: int = 0
    distinct_connections: int = 0
    independence: str = INDEPENDENCE_STATEMENT


class Council:
    def __init__(self, store: RecordStore, repo: Path,
                 connection_id: str | None = None):
        self.store = store
        self.repo = Path(repo)
        # Stamped on every sign-off this process records. None means the caller
        # did not supply one, which the independence gate reports as
        # unavailable rather than treating as a pass.
        self.connection_id = connection_id

    # ---- public API ------------------------------------------------------
    def next(self) -> NextResponse:
        state = self.store.load_state()
        if state.escalated:
            return NextResponse(kind="escalated", reason=state.escalation_reason)

        roster = self.store.load_roster()
        sha = tree_sha(self.repo)

        coverage = role_coverage(roster, self.store.signoffs(), sha)
        if coverage.allowed:
            return NextResponse(
                kind="done",
                reason="every role in the roster has signed off the current tree")

        if state.current is not None:
            return NextResponse(kind="assignment", assignment=state.current)

        assignment = self._issue(roster, state, sha)
        state.current = assignment
        self.store.save_state(state)
        self.store.append_event(TranscriptEvent(
            event="issued", role=assignment.role,
            detail=f"attempt {assignment.attempt}"))
        return NextResponse(kind="assignment", assignment=assignment)

    def submit(self, role: str, artifact_data: dict) -> SubmitResponse:
        state = self.store.load_state()
        current = state.current
        if current is None:
            reason = "no assignment is outstanding; call next() first"
            self.store.append_event(TranscriptEvent(
                event="rejected", role=role, detail=reason))
            return SubmitResponse(accepted=False, reason=reason)
        if role != current.role:
            reason = (f"the outstanding assignment belongs to "
                      f"{current.role!r}, not {role!r}")
            self.store.append_event(TranscriptEvent(
                event="rejected", role=current.role,
                detail=f"{reason} (submitted as {role!r})"))
            return SubmitResponse(
                accepted=False, attempts_remaining=self._remaining(current),
                reason=reason)

        self.store.append_event(TranscriptEvent(event="submitted", role=role))

        try:
            artifact = parse_artifact(artifact_data)
        except ValidationError as exc:
            return self._reject(state, current, f"malformed artifact: {exc}")

        result = validate(ArtifactKind(current.contract), artifact, self.repo)
        if not result.accepted:
            return self._reject(state, current, result.reason)

        signoff = Signoff(role=current.role, artifact=artifact,
                          tree_sha=tree_sha(self.repo),
                          connection_id=self.connection_id)
        gate = no_self_signoff(signoff, self.store.signoffs(),
                               self.store.load_roster())
        if not gate.allowed:
            return self._reject(state, current, gate.reason)

        self.store.append_signoff(signoff)
        self.store.append_event(TranscriptEvent(event="accepted", role=role))
        state.current = None
        self.store.save_state(state)
        return SubmitResponse(accepted=True, attempts_remaining=MAX_ATTEMPTS)

    def status(self) -> StatusResponse:
        state = self.store.load_state()
        roster = self.store.load_roster()
        sha = tree_sha(self.repo)
        events = self.store.events()
        signed = [s.role for s in self.store.signoffs() if s.tree_sha == sha]
        return StatusResponse(
            phase=state.phase, task_id=state.task_id,
            methodology=roster.methodology, roles=roster.role_ids(),
            signed_off=signed,
            outstanding=[r for r in roster.role_ids() if r not in signed],
            escalated=state.escalated, escalation_reason=state.escalation_reason,
            passes=len([e for e in self.store.events() if e.event == "submitted"]),
            passes_issued=len([e for e in events if e.event == "issued"]),
            passes_rejected=len([e for e in events if e.event == "rejected"]),
            bytes_handed_over=(
                len(state.current.model_dump_json().encode())
                if state.current is not None else 0),
            distinct_connections=len(
                {s.connection_id for s in self.store.signoffs()
                 if s.connection_id is not None}),
            independence=INDEPENDENCE_STATEMENT,
        )

    # ---- internals -------------------------------------------------------
    def _issue(self, roster, state, sha: str) -> Assignment:
        signoffs = self.store.signoffs()
        signed = {s.role for s in signoffs if s.tree_sha == sha}
        role = next(r for r in roster.roles if r.id not in signed)
        produced = next(
            (s for s in signoffs
             if s.role == _PRODUCER_ROLE and s.tree_sha == sha), None)
        reviewing = produced.artifact if (
            produced and role.id != _PRODUCER_ROLE) else None
        cited = _cited_paths(reviewing) if reviewing else []
        return Assignment(
            reviewing=reviewing, cited_paths=cited,
            role=role.id, phase=state.phase, task_id=state.task_id,
            contract=role.contract.value, attempt=1,
            instruction=(
                f"You are {role.name}. {role.brief}\n\n"
                f"Phase: {state.phase}. Task: {state.task_id}.\n"
                f"Before you may sign off you must submit a "
                f"`{role.contract.value}` artifact via charter.submit()."
                + (f"\n\nUnder review: a {reviewing.kind} citing "
                   f"{', '.join(cited)}. Open those files yourself -- charter "
                   f"hands over references, not contents."
                   if reviewing else "")),
        )

    def _remaining(self, current: Assignment) -> int:
        return max(MAX_ATTEMPTS - current.attempt, 0)

    def _reject(self, state, current: Assignment, reason: str) -> SubmitResponse:
        self.store.append_event(TranscriptEvent(
            event="rejected", role=current.role, detail=reason))
        if current.attempt >= MAX_ATTEMPTS:
            state.escalated = True
            state.escalation_reason = (
                f"{current.role!r} failed its {current.contract} contract "
                f"{MAX_ATTEMPTS} times. Last reason: {reason}")
            state.current = None
            self.store.save_state(state)
            self.store.append_event(TranscriptEvent(
                event="escalated", role=current.role, detail=reason))
            return SubmitResponse(accepted=False, reason=reason,
                                  attempts_remaining=0, escalated=True)

        state.current = current.model_copy(update={"attempt": current.attempt + 1})
        self.store.save_state(state)
        return SubmitResponse(accepted=False, reason=reason,
                              attempts_remaining=MAX_ATTEMPTS - current.attempt)
