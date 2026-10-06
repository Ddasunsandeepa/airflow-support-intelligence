"""Atomic JSON persistence for the single-process local PoC."""
import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from backend.app.change_models import SourceRemediation

STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "source_remediations.json"
workflow_lock = RLock()


class SourceRemediationStore:
    def __init__(self, path: Path | None = None):
        self.path = path or STORE_PATH

    def all(self) -> list[SourceRemediation]:
        with workflow_lock:
            if not self.path.exists():
                return []
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("Invalid source remediation store; refusing to overwrite it.")
            return [SourceRemediation.model_validate(item) for item in data]

    def get(self, proposal_id: str) -> SourceRemediation:
        with workflow_lock:
            record = next((r for r in self.all() if r.proposal_id == proposal_id), None)
            if record is None:
                raise KeyError("Source remediation not found.")
            return record

    def save(self, record: SourceRemediation) -> SourceRemediation:
        with workflow_lock:
            records = self.all()
            records = [r for r in records if r.proposal_id != record.proposal_id] + [record]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                                 prefix=".source-review-", suffix=".tmp", delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump([r.model_dump(mode="json") for r in records], handle, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return record
