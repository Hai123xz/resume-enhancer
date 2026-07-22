from abc import ABC, abstractmethod
from schemas.workflow import WorkflowState

class BaseAgent(ABC):

    @abstractmethod
    def run(self, state : WorkflowState) -> WorkflowState:
        pass