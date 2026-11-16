from typing import Protocol, runtime_checkable

from app.domain.agents import AgentContext, AgentName, AgentStep


@runtime_checkable
class Agent(Protocol):
    name: AgentName

    async def run(self, ctx: AgentContext) -> AgentStep: ...
