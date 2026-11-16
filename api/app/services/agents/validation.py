import math
import re
import time
import unicodedata

from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    IssueSeverity,
    StepStatus,
    ValidationIssue,
)
from app.services.agents.orchestrator import needs_analysis


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_canonical_float(raw: str) -> float | None:
    clean = raw.strip().replace("R$", "").replace("%", "").strip()
    if not clean:
        return None
    if "." in clean and "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    elif "." in clean:
        parts = clean.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            clean = parts[0] + parts[1]
    try:
        val = float(clean)
        return val if not math.isnan(val) and not math.isinf(val) else None
    except ValueError:
        return None


def clean_text_for_numbers(text: str) -> str:
    """Remove elementos estruturais que contêm números mas não são dados factuais."""
    # 1. Marcadores de citação [1], [2]
    cleaned = re.sub(r"\[\d+\]", " ", text)
    # 2. Resoluções, leis e artigos (ex.: "Resolução 4.966", "Lei nº 14.181", "art. 5º")
    cleaned = re.sub(
        r"\b(?:lei|resolucao|resolução|artigo|art\.?|norma|decreto)\s*(?:nº|no|n\.)?\s*[\d\.\/\-]+",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # 3. Anos de 4 dígitos (ex.: 2024, 2025, 2026, 1999)
    cleaned = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", cleaned)
    # 4. Numeração de listas no início de linhas (ex.: "1. ", "2) ")
    cleaned = re.sub(r"(?m)^\s*\d+[\.\)]\s+", " ", cleaned)
    # 5. Numeração de listas após pontuação (ex.: "... 1. Primeiro ... 2. Segundo")
    cleaned = re.sub(r"(?<=[;:\.\n])\s*\d+[\.\)]\s+", " ", cleaned)
    # 6. Menções ordinais ou passos (ex.: "Passo 1:", "item 2")
    pattern_steps = r"\b(?:passo|etapa|item|opcao|opção)\s+\d+\b"
    cleaned = re.sub(pattern_steps, " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def extract_numbers_from_text(text: str) -> list[tuple[float, str]]:
    """Extrai grandezas numéricas candidatas (valores monetários, percentuais e prazos)."""
    cleaned = clean_text_for_numbers(text)
    pattern = re.compile(
        r"(?:R\$\s*)?(?:\b\d{1,3}(?:\.\d{3})+(?:,\d+)?|\b\d+(?:,\d+)?|\b\d+(?:\.\d+)?)\s*"
        r"(?:%|\b(?:reais|meses|dias|anos)\b)?",
        re.IGNORECASE,
    )
    results: list[tuple[float, str]] = []
    for match in pattern.finditer(cleaned):
        raw = match.group(0).strip()
        if not raw:
            continue
        val = _parse_canonical_float(raw)
        if val is not None:
            results.append((val, raw))
    return results


def check_number_support(
    draft_numbers: list[tuple[float, str]],
    supported_numbers: set[float],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: set[float] = set()

    for val, raw in draft_numbers:
        is_supported = any(abs(val - sup) < 0.05 for sup in supported_numbers)
        if not is_supported and val not in seen:
            seen.add(val)
            msg = (
                f"O número '{raw}' (valor: {val}) não possui suporte nos cálculos "
                "nem nas evidências oficiais."
            )
            issues.append(
                ValidationIssue(
                    code="NUMBER_NOT_SUPPORTED",
                    severity=IssueSeverity.BLOCKER,
                    message=msg,
                )
            )
    return issues


def check_citations(draft: str, evidences_count: int) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    citations = [int(m) for m in re.findall(r"\[(\d+)\]", draft)]

    if evidences_count > 0:
        if not citations and len(draft.strip()) > 50:
            issues.append(
                ValidationIssue(
                    code="CITATION_INVALID",
                    severity=IssueSeverity.BLOCKER,
                    message="A resposta utiliza evidências mas não contém citações [n].",
                )
            )
        for c in citations:
            if c < 1 or c > evidences_count:
                issues.append(
                    ValidationIssue(
                        code="CITATION_INVALID",
                        severity=IssueSeverity.BLOCKER,
                        message=f"Citação [{c}] inválida ({evidences_count} evidências).",
                    )
                )
    else:
        if citations:
            issues.append(
                ValidationIssue(
                    code="CITATION_INVALID",
                    severity=IssueSeverity.BLOCKER,
                    message="Resposta cita fontes [n], mas nenhuma evidência foi recuperada.",
                )
            )
    return issues


def check_out_of_scope_advice(draft: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    normalized = _strip_accents(draft.lower())

    patterns = (
        r"\b(compre|invista em|indico comprar|carteira recomendada)\b.*"
        r"\b(petrobras|vale|itau|bitcoin|cripto|criptomoeda)\b",
        r"\b(lucro|retorno|rendimento)\s+garantido\b",
        r"\b(vai subir|vai cair|previsao de preco|preco alvo)\b",
    )
    for pat in patterns:
        if re.search(pat, normalized):
            issues.append(
                ValidationIssue(
                    code="OUT_OF_SCOPE_ADVICE",
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        "A resposta contém conselho específico ou promessa de retorno, "
                        "violando o escopo educacional."
                    ),
                )
            )
            break
    return issues


def check_abstention_mismatch(draft: str, abstain_reason: str | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if abstain_reason and len(draft.strip()) > 15:
        issues.append(
            ValidationIssue(
                code="ABSTENTION_MISMATCH",
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"A resposta foi elaborada apesar de haver motivo de abstenção "
                    f"('{abstain_reason}')."
                ),
            )
        )
    return issues


def check_calculation_missing(
    question: str,
    draft: str,
    calculations_count: int,
    evidence_or_q_numbers: set[float],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if needs_analysis(question) and calculations_count == 0:
        numbers = extract_numbers_from_text(draft)
        has_unsupported_math = any(
            not any(abs(val - sup) < 0.05 for sup in evidence_or_q_numbers) for val, _ in numbers
        )
        if has_unsupported_math:
            issues.append(
                ValidationIssue(
                    code="CALCULATION_MISSING",
                    severity=IssueSeverity.BLOCKER,
                    message=(
                        "A consulta demanda cálculo, mas o rascunho traz números "
                        "sem cálculo auditável do sistema."
                    ),
                )
            )
    return issues


class ValidationAgent:
    """Agente determinístico de validação defensiva e conformidade regulatória (ADR 0016)."""

    def __init__(self) -> None:
        self.name = AgentName.VALIDATION

    async def run(self, ctx: AgentContext) -> AgentStep:
        t0 = time.perf_counter()
        draft = ctx.draft_answer or ""
        issues: list[ValidationIssue] = []

        # 1. Checagem de incompatibilidade de abstenção
        issues.extend(check_abstention_mismatch(draft, ctx.abstain_reason))

        # 2. Checagem de conselho fora de escopo (C27)
        issues.extend(check_out_of_scope_advice(draft))

        # 3. Checagem de validade de citações
        issues.extend(check_citations(draft, len(ctx.evidences)))

        # 4. Coleta de números suportados (calculations + evidences + question + constantes)
        supported_numbers: set[float] = {0.0, 1.0, 2.0, 3.0, 50.0, 30.0, 20.0, 6.0, 12.0}
        evidence_or_q_numbers: set[float] = set(supported_numbers)

        # Números das evidências
        for ev in ctx.evidences:
            full_ev_text = f"{ev.document_title} {ev.section} {ev.content}"
            for val, _ in extract_numbers_from_text(full_ev_text):
                supported_numbers.add(val)
                evidence_or_q_numbers.add(val)

        # Números presentes na pergunta do usuário
        for val, _ in extract_numbers_from_text(ctx.question):
            supported_numbers.add(val)
            evidence_or_q_numbers.add(val)

        # Números dos cálculos
        for calc in ctx.calculations:
            val = _parse_canonical_float(str(calc.value))
            if val is not None:
                supported_numbers.add(val)

        # 5. Checagem de cálculo ausente (C30)
        issues.extend(
            check_calculation_missing(
                ctx.question,
                draft,
                len(ctx.calculations),
                evidence_or_q_numbers,
            )
        )

        # 6. Verificação de suporte numérico (C29, C04, C17)
        draft_numbers = extract_numbers_from_text(draft)
        issues.extend(check_number_support(draft_numbers, supported_numbers))

        ctx.issues = issues

        duration = max(1, int(round((time.perf_counter() - t0) * 1000)))
        has_blocker = any(i.severity == IssueSeverity.BLOCKER for i in issues)

        if has_blocker:
            return AgentStep(
                agent=self.name,
                status=StepStatus.FAILED,
                summary=f"Validação reprovou o rascunho com {len(issues)} problemas detectados.",
                duration_ms=duration,
                detail={"issues": [i.model_dump() for i in issues]},
            )

        return AgentStep(
            agent=self.name,
            status=StepStatus.OK,
            summary=f"Validação aprovada sem bloqueios ({len(issues)} avisos informativos).",
            duration_ms=duration,
            detail={"issues_count": len(issues)},
        )
