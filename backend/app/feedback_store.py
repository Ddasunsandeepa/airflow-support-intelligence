"""Small JSON evaluation store for a single backend process; no action side effects."""

import json
import os
import tempfile
from pathlib import Path
from threading import Lock

from backend.app.feedback_models import RemediationFeedback


STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "remediation_feedback.json"
_store_lock = Lock()


class FeedbackStore:
    def __init__(self, path: Path | None = None):
        self.path = path if path is not None else STORE_PATH

    def _load(self) -> list[RemediationFeedback]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Feedback store must contain a JSON list.")
        # Invalid existing records must never be silently discarded/overwritten.
        return [RemediationFeedback.model_validate(item) for item in data]

    def get_for_action(self, action_id: str) -> RemediationFeedback | None:
        with _store_lock:
            return next((item for item in self._load() if item.action_id == action_id), None)

    def save(self, feedback: RemediationFeedback) -> RemediationFeedback:
        """First submission wins per action; retries return the saved record.

        Reload under the process lock to preserve other actions' feedback. An
        atomic replacement prevents partial JSON files if a write fails.
        """
        with _store_lock:
            records = self._load()
            existing = next((item for item in records if item.action_id == feedback.action_id), None)
            if existing is not None:
                return existing
            records.append(feedback)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.path.parent,
                    prefix=".feedback-", suffix=".tmp", delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    json.dump([item.model_dump(mode="json") for item in records], temporary, indent=2)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                temporary_path.replace(self.path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
            return feedback
