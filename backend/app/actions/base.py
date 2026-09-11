from abc import ABC, abstractmethod

from backend.app.action_models import ActionRequest


class ActionExecutor(ABC):
    """
    Base interface for all controlled remediation executors.

    Executors perform only explicitly supported actions.
    They must never execute arbitrary commands supplied by
    an LLM or user.
    """

    @abstractmethod
    def supports(self, action: ActionRequest) -> bool:
        """
        Return True when this executor supports the requested action.
        """
        raise NotImplementedError

    @abstractmethod
    def execute(self, action: ActionRequest) -> dict:
        """
        Execute the validated action and return a structured result.
        """
        raise NotImplementedError