"""The loop.

An MCP server cannot push, only answer -- so the build advances because the
calling agent keeps asking `next()`. This class owns what "next" means.
"""
from pathlib import Path

from pydantic import BaseModel, ValidationError

from charter.contracts.models import parse_artifact
from charter.contracts.validators import validate
from charter.gates.checks import no_self_signoff, role_coverage
from charter.kernel.models import ArtifactKind
from charter.record.models import Assignment, Signoff, TranscriptEvent
from charter.record.store import RecordStore
from charter.vcs import tree_sha

MAX_ATTEMPTS = 3


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


class Council:
    def __init__(self, store: RecordStore, repo: Path):
        self.store = store
        self.repo = Path(repo)

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
            return SubmitResponse(
                accepted=False,
                reason="no assignment is outstanding; call next() first")
        if role != current.role:
            return SubmitResponse(
                accepted=False, attempts_remaining=self._remaining(current),
                reason=f"the outstanding assignment belongs to "
                       f"{current.role!r}, not {role!r}")

        self.store.append_event(TranscriptEvent(event="submitted", role=role))

        try:
            artifact = parse_artifact(artifact_data)
        except ValidationError as exc:
            return self._reject(state, current, f"malformed artifact: {exc}")

        result = validate(ArtifactKind(current.contract), artifact, self.repo)
        if not result.accepted:
            return self._reject(state, current, result.reason)

        producer = self._producer_for(current.role)
        signoff = Signoff(role=current.role, producer_role=producer,
                          artifact=artifact, tree_sha=tree_sha(self.repo))
        gate = no_self_signoff(signoff)
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
        signed = [s.role for s in self.store.signoffs() if s.tree_sha == sha]
        return StatusResponse(
            phase=state.phase, task_id=state.task_id,
            methodology=roster.methodology, roles=roster.role_ids(),
            signed_off=signed,
            outstanding=[r for r in roster.role_ids() if r not in signed],
            escalated=state.escalated, escalation_reason=state.escalation_reason,
            passes=len([e for e in self.store.events() if e.event == "submitted"]),
        )

    # ---- internals -------------------------------------------------------
    def _issue(self, roster, state, sha: str) -> Assignment:
        signed = {s.role for s in self.store.signoffs() if s.tree_sha == sha}
        role = next(r for r in roster.roles if r.id not in signed)
        return Assignment(
            role=role.id, phase=state.phase, task_id=state.task_id,
            contract=role.contract.value, attempt=1,
            instruction=(
                f"You are {role.name}. {role.brief}\n\n"
                f"Phase: {state.phase}. Task: {state.task_id}.\n"
                f"Before you may sign off you must submit a "
                f"`{role.contract.value}` artifact via charter.submit()."),
        )

    def _producer_for(self, role: str) -> str:
        """Who produced the work this role is approving.

        v1 convention: the developer produces, everyone else reviews. Recorded
        explicitly so `no_self_signoff` has something real to check and so the
        rule keeps working unchanged when v2 runs one session per role.
        """
        return "developer" if role != "developer" else "author"

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
