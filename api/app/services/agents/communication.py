"""Communication Agent: redação em linguagem natural pedagógica ancorada em fontes e cálculos."""

import re
import time
from collections.abc import Sequence
from pathlib import Path

from app.core.config import settings
from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    CalculationResult,
    IssueSeverity,
    StepStatus,
    ValidationIssue,
)
from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMProvider, LLMResponse
from app.services.financial_number_validation import check_financial_numbers

MODEL_UNAVAILABLE_MESSAGE = "Modelo de linguagem indisponível; não foi possível redigir a resposta."
DRAFT_NOT_GROUNDED_CODE = "DRAFT_NOT_GROUNDED"
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
DEFAULT_PROMPT_PATH = PROMPTS_DIR / "prompt_agente_comunicacao_v2.txt"

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
        max_tokens: int | None = None,
    ) -> None:
        self.name: AgentName = AgentName.COMMUNICATION
        self.llm_provider = llm_provider
        self.prompt_path = prompt_path or DEFAULT_PROMPT_PATH
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
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
            source_url = ev.source_url or "URL não fornecida"
            quoted_content = " ".join(
                f"{sentence} [{index}]"
                for index, sentence in CommunicationAgent._evidence_sentences([ev], start=idx)
            )
            lines.append(
                f"[{idx}] Órgão/Fonte: {ev.source_name} | Documento: {ev.document_title} | "
                f"Seção: {ev.section} | Link oficial: {source_url}\n"
                f"Conteúdo: {quoted_content}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _format_calculations(calculations: Sequence[CalculationResult]) -> str:
        if not calculations:
            return "Nenhum cálculo numérico sobre transações foi executado para esta consulta."
        return "\n".join(
            f"- {line}" for line in CommunicationAgent._calculation_lines(calculations)
        )

    @staticmethod
    def _evidence_sentences(
        evidences: Sequence[EvidenceChunk], start: int = 1
    ) -> list[tuple[int, str]]:
        sentences = []
        for index, evidence in enumerate(evidences, start):
            content = " ".join(evidence.content.split())
            for sentence in re.split(r"(?<=[.!?])\s+", content):
                if sentence:
                    sentences.append((index, sentence))
        return sentences

    @staticmethod
    def _calculation_lines(calculations: Sequence[CalculationResult]) -> list[str]:
        lines = []
        for calculation in calculations:
            unit = f" {calculation.unit}" if calculation.unit else ""
            lines.append(
                f"{calculation.label} ({calculation.key}): {calculation.value}{unit} "
                f"[Fonte auditável: {calculation.source}]"
            )
        return lines

    @classmethod
    def _is_supported_draft(cls, draft: str, ctx: AgentContext) -> bool:
        """Aceita apenas frases literais citadas e resultados determinísticos exatos."""
        remaining = " ".join(draft.split())
        if not remaining:
            return False
        if ctx.financial:
            return remaining == " ".join(cls._safe_draft(ctx).split())
        if ctx.assumptions:
            return False

        citations = [int(value) for value in _CITATION_PATTERN.findall(remaining)]
        if any(value < 1 or value > len(ctx.evidences) for value in citations):
            return False

        matched_citations = []
        matched_evidence = False
        for index, sentence in cls._evidence_sentences(ctx.evidences):
            quoted = f"{sentence} [{index}]"
            if quoted in remaining:
                remaining = remaining.replace(quoted, " ", 1)
                matched_citations.append(index)
                matched_evidence = True
        if sorted(citations) != sorted(matched_citations):
            return False

        for calculation in cls._calculation_lines(ctx.calculations):
            calculation = " ".join(calculation.split())
            if calculation not in remaining:
                return False
            remaining = remaining.replace(calculation, " ", 1)

        if ctx.evidences and not matched_evidence:
            return False
        residue = _CITATION_PATTERN.sub(" ", remaining)
        residue = re.sub(r"[\s,;:|•–—*-]+", "", residue)
        return not residue

    @classmethod
    def _safe_draft(cls, ctx: AgentContext) -> str:
        """Monta resposta com trechos, valores e lacunas recebidos no contexto."""
        parts = [
            f"{sentence} [{index}]" for index, sentence in cls._evidence_sentences(ctx.evidences)
        ]
        parts.extend(cls._calculation_lines(ctx.calculations))
        if ctx.assumptions:
            parts.append("Premissas e limitações:")
            parts.extend(f"- {assumption}" for assumption in ctx.assumptions)
            if not ctx.financial:
                parts.append("Você pode esclarecer essas premissas ou fornecer os dados indicados?")
        if not parts:
            return "Não recebi evidências, cálculos ou premissas suficientes para responder."
        return "\n".join(parts)

    @staticmethod
    def _numeric_values(text: str) -> set[str]:
        """Compara representações literais, preservando sinal, precisão e unidade."""
        without_citations = _CITATION_PATTERN.sub(" ", text)
        pattern = (
            r"(?:R\$\s*)?[+-]?\d+(?:[.,]\d+)*"
            r"(?:\s*(?:%|reais\b|BRL\b|meses\b|dias\b|anos\b))?"
        )
        return {
            re.sub(r"\s+", "", match).casefold()
            for match in re.findall(pattern, without_citations, flags=re.IGNORECASE)
        }

    @classmethod
    def _has_unsupported_numbers(cls, draft: str, ctx: AgentContext) -> bool:
        supported_text = [ctx.question]
        supported_text.extend(
            f"{evidence.document_title} {evidence.section} {evidence.content}"
            for evidence in ctx.evidences
        )
        supported_text.extend(
            f"{calc.label} {calc.key} {calc.value} {calc.unit or ''} {calc.source}"
            for calc in ctx.calculations
        )
        supported: set[str] = set()
        for text in supported_text:
            supported.update(cls._numeric_values(text))
        return not cls._numeric_values(draft).issubset(supported)

    @staticmethod
    def _format_assumptions(assumptions: Sequence[str]) -> str:
        if not assumptions:
            return "Nenhuma limitação restritiva ou premissa informada."
        return "\n".join(f"- {a}" for a in assumptions)

    @staticmethod
    def _format_revision_notes(issues: Sequence[ValidationIssue], attempt: int) -> str:
        blockers = [issue for issue in issues if issue.severity == IssueSeverity.BLOCKER]
        if attempt <= 0 or not blockers:
            return ""
        lines = [
            "ATENÇÃO - REVISÃO OBRIGATÓRIA DA TENTATIVA ANTERIOR:",
            "A resposta anterior foi rejeitada pela validação com os seguintes problemas:",
        ]
        for issue in blockers:
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
            question=(
                f"Consulta de dados importados: {ctx.financial.intent.value}. "
                "Explique os cálculos e suas limitações."
                if ctx.financial
                else ctx.question
            ),
        )

        try:
            response: LLMResponse = await self.llm_provider.generate(
                prompt=prompt,
                context_chunks=ctx.evidences or None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:
            duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
            ctx.draft_answer = None
            ctx.model = None
            ctx.attempt += 1
            return AgentStep(
                agent=self.name,
                status=StepStatus.FAILED,
                summary=MODEL_UNAVAILABLE_MESSAGE,
                duration_ms=duration,
                detail={"error_type": type(exc).__name__, "attempt": ctx.attempt},
            )

        duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
        generated_answer = response.content.strip()
        answer_supported = self._is_supported_draft(generated_answer, ctx)
        ctx.draft_answer = generated_answer if answer_supported else self._safe_draft(ctx)
        replaced_codes = {DRAFT_NOT_GROUNDED_CODE}
        if ctx.financial:
            replaced_codes.add("NUMBER_NOT_SUPPORTED")
        ctx.issues = [issue for issue in ctx.issues if issue.code not in replaced_codes]
        if (
            not ctx.financial
            and not answer_supported
            and self._has_unsupported_numbers(generated_answer, ctx)
        ):
            ctx.issues.append(
                ValidationIssue(
                    code=DRAFT_NOT_GROUNDED_CODE,
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        "O rascunho não pôde ser confirmado como cópia literal das evidências "
                        "e dos resultados de cálculo fornecidos."
                    ),
                )
            )
        if ctx.financial:
            ctx.issues.extend(
                check_financial_numbers(generated_answer, ctx.calculations, ctx.assumptions)
            )
        ctx.model = response.model
        ctx.attempt += 1

        return AgentStep(
            agent=self.name,
            status=StepStatus.OK,
            summary=(
                "Rascunho redigido com base nos dados fornecidos."
                if answer_supported
                else "Rascunho substituído por conteúdo apoiado nos dados recebidos."
            ),
            duration_ms=duration,
            detail={
                "model": response.model,
                "attempt": ctx.attempt,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "draft_guard": "accepted" if answer_supported else "safe_fallback",
            },
        )
