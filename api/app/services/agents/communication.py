"""Communication Agent: redação em linguagem natural pedagógica ancorada em fontes e cálculos."""

import re
import time
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.core.config import settings
from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    IssueSeverity,
    StepStatus,
    ValidationIssue,
)
from app.domain.models import EvidenceChunk
from app.models.llm_provider import LLMProvider, LLMResponse

MODEL_UNAVAILABLE_MESSAGE = "Modelo de linguagem indisponível; não foi possível redigir a resposta."
DRAFT_NOT_GROUNDED_CODE = "DRAFT_NOT_GROUNDED"
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")

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
            source_url = ev.source_url or "URL não fornecida"
            quoted_content = re.sub(
                r"([.!?])(?=\s|$)",
                rf"\1 [{idx}]",
                ev.content.strip(),
            )
            lines.append(
                f"[{idx}] Órgão/Fonte: {ev.source_name} | Documento: {ev.document_title} | "
                f"Seção: {ev.section} | Link oficial: {source_url}\n"
                f"Conteúdo: {quoted_content}"
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
    def _evidence_sentences(ctx: AgentContext) -> list[tuple[int, str]]:
        sentences = []
        for index, evidence in enumerate(ctx.evidences, 1):
            for sentence in re.split(r"(?<=[.!?])\s+", evidence.content.strip()):
                if sentence:
                    sentences.append((index, sentence.strip()))
        return sentences

    @staticmethod
    def _calculation_lines(ctx: AgentContext) -> list[str]:
        lines = []
        for calculation in ctx.calculations:
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
        if not remaining or ctx.assumptions:
            return False

        citations = [int(value) for value in _CITATION_PATTERN.findall(remaining)]
        if any(value < 1 or value > len(ctx.evidences) for value in citations):
            return False

        matched_citations = []
        matched_evidence = False
        for index, sentence in cls._evidence_sentences(ctx):
            quoted = f"{sentence} [{index}]"
            if quoted in remaining:
                remaining = remaining.replace(quoted, " ", 1)
                matched_citations.append(index)
                matched_evidence = True
        if sorted(citations) != sorted(matched_citations):
            return False

        for calculation in cls._calculation_lines(ctx):
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
        parts = [f"{sentence} [{index}]" for index, sentence in cls._evidence_sentences(ctx)]
        parts.extend(cls._calculation_lines(ctx))
        parts.extend(f"Falta o dado: {assumption.rstrip('.!?')}?" for assumption in ctx.assumptions)
        if not parts:
            return "Não recebi evidências, cálculos ou premissas suficientes para responder."
        return "\n".join(parts)

    @staticmethod
    def _numeric_values(text: str) -> set[Decimal]:
        without_citations = _CITATION_PATTERN.sub(" ", text)
        pattern = r"(?:R\$\s*)?\d+(?:[.,]\d+)*(?:\s*(?:%|reais|BRL|meses|dias|anos))?"
        values: set[Decimal] = set()
        for raw in re.findall(pattern, without_citations, flags=re.IGNORECASE):
            number = re.sub(r"\s*(?:%|reais|BRL|meses|dias|anos)$", "", raw, flags=re.IGNORECASE)
            number = number.replace("R$", "").replace(" ", "")
            if "," in number:
                number = number.replace(".", "").replace(",", ".")
            try:
                values.add(Decimal(number))
            except InvalidOperation:
                continue
        return values

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
        supported = {
            Decimal("0"),
            Decimal("1"),
            Decimal("2"),
            Decimal("3"),
            Decimal("6"),
            Decimal("12"),
            Decimal("20"),
            Decimal("30"),
            Decimal("50"),
        }
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
        ctx.issues = [issue for issue in ctx.issues if issue.code != DRAFT_NOT_GROUNDED_CODE]
        if not answer_supported and self._has_unsupported_numbers(generated_answer, ctx):
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
