from openai import OpenAI

from agents.ats import ATSScorer
from base import BaseAgent
from schemas.workflow import WorkflowState
from planner import PlanerAgent
from writer import WriterAgent
from verifier import VerifierAgent

class Orchestrator(BaseAgent):
    def __init__(self, client: OpenAI):
        self.pipeline = [
            PlanerAgent(client=client),
            WriterAgent(client=client),
            VerifierAgent(client=client),
            ATSScorer(client=client)
        ]

    def run(self, state: WorkflowState) -> WorkflowState:
        for agent in self.pipeline:
            agent_name = agent.__class__.__name__
            state.logs.append(f"Starting {agent_name}...")

            state = agent.run(state)

            state.logs.append(f"Finished {agent_name}!")
        return state