import json
from pathlib import Path

from backend.app.action_models import RemediationAction


STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "actions.json"


class ActionStore:
    def __init__(self):
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._actions: dict[str, RemediationAction] = {}
        self._load()

    def _load(self) -> None:
        if not STORE_PATH.exists():
            return

        try:
            data = json.loads(
                STORE_PATH.read_text(encoding="utf-8")
            )

            for item in data:
                action = RemediationAction.model_validate(item)
                self._actions[action.action_id] = action

        except (json.JSONDecodeError, ValueError):
            self._actions = {}

    def _persist(self) -> None:
        data = [
            action.model_dump(mode="json")
            for action in self._actions.values()
        ]

        STORE_PATH.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    def save(
        self,
        action: RemediationAction,
    ) -> RemediationAction:
        self._actions[action.action_id] = action
        self._persist()
        return action

    def get(
        self,
        action_id: str,
    ) -> RemediationAction | None:
        return self._actions.get(action_id)

    def delete(self, action_id: str) -> None:
        self._actions.pop(action_id, None)
        self._persist()

    def list(self) -> list[RemediationAction]:
        return list(self._actions.values())