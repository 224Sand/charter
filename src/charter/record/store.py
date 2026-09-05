"""Persistence for the build record.

Everything is human-readable and git-diffable on purpose: a reviewer should be
able to read the governance trail without our tooling.
"""
import json
from pathlib import Path

from charter.kernel.models import Roster
from charter.record.models import BuildState, Signoff, TranscriptEvent

CHARTER_DIR = ".charter"


class RecordStore:
    def __init__(self, repo: Path):
        self.repo = Path(repo)
        self.root = self.repo / CHARTER_DIR

    # ---- paths -----------------------------------------------------------
    @property
    def _charter(self) -> Path:
        return self.root / "charter.json"

    @property
    def _state(self) -> Path:
        return self.root / "state.json"

    @property
    def _signoffs(self) -> Path:
        return self.root / "signoffs.jsonl"

    @property
    def _transcript(self) -> Path:
        return self.root / "transcript.jsonl"

    # ---- lifecycle -------------------------------------------------------
    def exists(self) -> bool:
        return self._charter.is_file()

    def init(self, roster: Roster, idea: str, phase: str) -> None:
        """Start a build. `phase` is the methodology's opening phase -- passed
        in rather than guessed, since Scrum opens at requirements and CI/CD at
        implementation, and only the caller holds the MethodologyDef."""
        self.root.mkdir(parents=True, exist_ok=True)
        self._charter.write_text(json.dumps(
            {"idea": idea, "roster": roster.model_dump(mode="json")}, indent=2))
        self._signoffs.touch()
        self._transcript.touch()
        self.save_state(BuildState(phase=phase, task_id="T-1"))

    # ---- reads / writes --------------------------------------------------
    def load_roster(self) -> Roster:
        data = json.loads(self._read(self._charter))
        return Roster(**data["roster"])

    def load_idea(self) -> str:
        return json.loads(self._read(self._charter))["idea"]

    def load_state(self) -> BuildState:
        return BuildState(**json.loads(self._read(self._state)))

    def save_state(self, state: BuildState) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._state.write_text(json.dumps(state.model_dump(mode="json"), indent=2))

    def append_signoff(self, signoff: Signoff) -> None:
        self._append(self._signoffs, signoff.model_dump(mode="json"))

    def signoffs(self) -> list[Signoff]:
        return [Signoff(**row) for row in self._read_lines(self._signoffs)]

    def append_event(self, event: TranscriptEvent) -> None:
        self._append(self._transcript, event.model_dump(mode="json"))

    def events(self) -> list[TranscriptEvent]:
        return [TranscriptEvent(**row) for row in self._read_lines(self._transcript)]

    # ---- helpers ---------------------------------------------------------
    def _read(self, path: Path) -> str:
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} not found -- run `charter init` in this repository first")
        return path.read_text()

    def _append(self, path: Path, row: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")

    def _read_lines(self, path: Path) -> list[dict]:
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
