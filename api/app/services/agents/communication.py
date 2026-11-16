"""Communication Agent: redação em linguagem natural pedagógica ancorada em fontes e cálculos."""

import time
from collections.abc import Sequence
from pathlib import Path

from app.core.config import settings
from app.domain.agents import AgentContext, AgentName, AgentStep, StepStatus, ValidationIssue
from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMProvider, LLMResponse

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
DEFAULT_PROMPT_PATH = PROMPTS_DIR / "prompt_agente_comunicacao_v1.txt"

FALLBACK_TEMPLATE = (
    "Você é o assistente financeiro educativo do Trokim.\n"
    "Responda em português do Brasil com base estrita nas evidências e cálculos.\n\n"
    "{revision_notes}\n\n"
    "EVIDÊNCIAS:\n{evidences}\n\n"
    "CÁLCULOS:\n{calculations}\n\n"
    "PREMISSAS:\n{assumptions}\n\n"
    "PERGUNTA:\n{question}\n"
)


class CommunicationAgent:
    """Agente de redação final com LLM local, ancorado em cálculos auditáveis e evidências."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_path: Path | None = None,
        temperature: float | None = None,
    ) -> None:
        self.name: AgentName = AgentName.COMMUNICATION
        self.llm_provider = llm_provider
        self.prompt_path = prompt_path or DEFAULT_PROMPT_PATH
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self._load_template()

    def _load_template(self) -> None:
        if self.prompt_path.exists():
            self.template = self.prompt_path.read_text(encoding="utf-8")
        else:
            self.template = FALLBACK_TEMPLATE

    @staticmethod
    def _format_evidences(evidences: Sequence[EvidenceChunk]) -> str:
        if not evidences:
            return "Nenhuma evidência documental necessária ou recuperada."
        lines = []
        for idx, ev in enumerate(evidences, 1):
            source_url = ev.source_url or "https://www.bcb.gov.br"
            lines.append(
                f"[{idx}] Órgão/Fonte: {ev.source_name} | Documento: {ev.document_title} | "
                f"Seção: {ev.section} | Link oficial: {source_url}\n"
                f"Conteúdo: {ev.content.strip()}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _format_calculations(calculations: Sequence[object]) -> str:
        if not calculations:
            return "Nenhum cálculo numérico sobre transações foi executado para esta consulta."
        lines = []
        for calc in calculations:
            label = getattr(calc, "label", "Cálculo")
            key = getattr(calc, "key", "")
            val = getattr(calc, "value", "")
            unit = getattr(calc, "unit", "")
            source = getattr(calc, "source", "Sistema")
            unit_str = f" {unit}" if unit else ""
            lines.append(f"- {label} ({key}): {val}{unit_str} [Fonte auditável: {source}]")
        return "\n".join(lines)

    @staticmethod
    def _format_assumptions(assumptions: Sequence[str]) -> str:
        if not assumptions:
            return "Nenhuma limitação restritiva ou premissa informada."
        return "\n".join(f"- {a}" for a in assumptions)

    @staticmethod
    def _format_revision_notes(issues: Sequence[ValidationIssue], attempt: int) -> str:
        if attempt <= 0 or not issues:
            return ""
        lines = [
            "ATENÇÃO - REVISÃO OBRIGATÓRIA DA TENTATIVA ANTERIOR:",
            "A resposta anterior foi rejeitada pela validação com os seguintes problemas:",
        ]
        for issue in issues:
            lines.append(f"- [{issue.code} / {issue.severity.value}] {issue.message}")
        lines.append("Reescreva a resposta corrigindo integralmente todos os desvios acima.")
        return "\n".join(lines)

    async def run(self, ctx: AgentContext) -> AgentStep:
        t0 = time.perf_counter()

        prompt = self.template.format(
            evidences=self._format_evidences(ctx.evidences),
            calculations=self._format_calculations(ctx.calculations),
            assumptions=self._format_assumptions(ctx.assumptions),
            revision_notes=self._format_revision_notes(ctx.issues, ctx.attempt),
            question=ctx.question,
        )

        try:
            response: LLMResponse = await self.llm_provider.generate(
                prompt=prompt,
                context_chunks=ctx.evidences or None,
                temperature=self.temperature,
            )
        except Exception as exc:
            duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
            return AgentStep(
                agent=self.name,
                status=StepStatus.FAILED,
                summary=f"Falha de comunicação com o provedor de linguagem: {exc}",
                duration_ms=duration,
                detail={"error": str(exc), "attempt": ctx.attempt + 1},
            )

        duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
        ctx.draft_answer = response.content.strip()
        ctx.model = response.model
        ctx.attempt += 1

        return AgentStep(
            agent=self.name,
            status=StepStatus.OK,
            summary="Rascunho de resposta redigido com base em evidências e cálculos.",
            duration_ms=duration,
            detail={
                "model": response.model,
                "attempt": ctx.attempt,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
            },
        )
