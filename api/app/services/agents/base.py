from typing import Protocol

from app.domain.agents import AgentContext, AgentName, AgentStep


class Agent(Protocol):
    name: AgentName

    async def run(self, ctx: AgentContext) -> AgentStep:
        """Executa a lógica do agente, muta o contexto e devolve o passo registrado."""
        ...
