"""ValidationAgent: validação determinística de rascunhos de resposta.

Garante que nenhuma resposta saia sem uma checagem independente e determinística.
Reaproveita e aprimora as heurísticas do benchmark da Semana 3, sem chamadas a LLM
e sem acesso à rede.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    AgentStepStatus,
    CalculationResult,
    IssueSeverity,
    ValidationIssue,
    ValidationIssueCode,
)
from app.domain.models import EvidenceChunk

# Padrões para remoção de elementos estruturais que não constituem fatos numéricos
CITATION_PATTERN = re.compile(r"\[\d+(?:\s*[,-]\s*\d+)*\]")
LIST_MARKER_PATTERNS = [
    # Início de linha ou parágrafo com marcador: "1. ", "2) ", "1 - ", "* 1. "
    re.compile(r"(?m)^\s*(?:[\*\-]\s*)?\(?\d{1,2}(?:[\.\)]|\s*[-–—])\s+"),
    # Marcador inline com parênteses: "1) ", "(1) " (não precedido por dígito, vírgula ou ponto)
    re.compile(r"(?<![\d,\.])\(?\d{1,2}\)\s+(?=[A-Za-zÀ-ÿ])"),
    # Marcador após pontuação final e espaço: ". 1. ", "; 2) "
    re.compile(r"(?<=[.!?;]\s)\(?\d{1,2}[\.\)]\s+(?=[A-Za-zÀ-ÿ])"),
    # Numerais ordinais: "1º", "2ª"
    re.compile(r"\b\d+[ºª]\b"),
]

# Padrões para extração de fatos numéricos em pt-BR
CURRENCY_PATTERN = re.compile(
    r"(?<![\w])(?:R\$|US\$|USD)\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?|\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(
    r"(?<![\w])(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?|\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
TIME_RANGE_PATTERN = re.compile(
    r"(?<![\w])(\d+)\s*(?:-|–|—|a)\s*(\d+)\s*(dias?|meses|mês|anos?)\b",
    re.IGNORECASE,
)
TIME_SINGLE_PATTERN = re.compile(
    r"(?<![-–—aA\w]\s)\b(\d+)\s+(dias?|meses|mês|anos?)\b",
    re.IGNORECASE,
)
GENERAL_NUMBER_PATTERN = re.compile(
    r"(?<![\w\.\,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?|\d+(?:\.\d+)?)(?![\w\.\,])"
)

# Padrões para detecção de aconselhamento fora de escopo e termos proibidos
OUT_OF_SCOPE_PATTERNS = [
    # Garantias de rendimento e certezas
    (re.compile(r"\bgarantid[oa]s?\b", re.IGNORECASE), "termo proibido 'garantido'"),
    (re.compile(r"\bretorno\s+garantido\b", re.IGNORECASE), "promessa de retorno garantido"),
    (
        re.compile(r"\blucro\s+(?:garantido|certo)\b", re.IGNORECASE),
        "promessa de lucro garantido/certo",
    ),
    (re.compile(r"\brendimento\s+garantido\b", re.IGNORECASE), "promessa de rendimento garantido"),
    (re.compile(r"\bganho\s+certo\b", re.IGNORECASE), "promessa de ganho certo"),
    (
        re.compile(r"\bsem\s+risco\b|\brisco\s+zero\b", re.IGNORECASE),
        "afirmação de investimento sem risco",
    ),
    (
        re.compile(r"\brentabilidade\s+garantida\b", re.IGNORECASE),
        "promessa de rentabilidade garantida",
    ),
    # Recomendações diretas de compra/venda de ativos específicos
    (
        re.compile(r"\bcompre\s+(?:a\s+|as\s+)?ações?\b", re.IGNORECASE),
        "recomendação de compra de ação específica",
    ),
    (
        re.compile(r"\bvenda\s+(?:a\s+|as\s+)?ações?\b", re.IGNORECASE),
        "recomendação de venda de ação específica",
    ),
    (
        re.compile(r"\binvista\s+(?:na\s+|nas\s+)?ações?\b", re.IGNORECASE),
        "recomendação de investimento em ação específica",
    ),
    (
        re.compile(r"\brecomendo\s+(?:a\s+compra|comprar|investir\s+em)\b", re.IGNORECASE),
        "recomendação ativa de produto/ação",
    ),
    # Previsão determinística de cotações futuras de mercado (C27)
    (
        re.compile(r"\bo\s+preço\s+(?:exato\s+)?da\s+ação\s+(?:será|vai)\b", re.IGNORECASE),
        "previsão de preço de ação",
    ),
    (
        re.compile(r"\ba\s+ação\s+vai\s+(?:subir|cair|atingir|valer)\b", re.IGNORECASE),
        "previsão de cotação de mercado",
    ),
    (
        re.compile(r"\bcotação\s+(?:exata\s+)?será\b", re.IGNORECASE),
        "previsão determinística de cotação",
    ),
    (re.compile(r"\bprevisão\s+de\s+preço\b", re.IGNORECASE), "previsão de preço de mercado"),
]

NEGATION_PREFIX_PATTERN = re.compile(
    r"(?:\bnão\s+|\bsem\s+|\bnunca\s+|\bjamais\s+|\bimpossível\s+|\bnão\s+há\s+|\bnão\s+é\s+possível\s+|\bnão\s+oferece\s+|\bnão\s+possu[ei]\s+)[^.!?]{0,40}$",
    re.IGNORECASE,
)

# Indicadores de abstenção ou recusa segura
ABSTENTION_INDICATORS = [
    re.compile(
        r"\bnão\s+(?:posso|podemos|consigo|é\s+possível|tenho\s+como|há\s+como)\b", re.IGNORECASE
    ),
    re.compile(r"\bfora\s+d[eo]\s+escopo\b", re.IGNORECASE),
    re.compile(
        r"\bsem\s+evidência\b|\bnão\s+há\s+evidência\b|\bnão\s+possuo\s+evidência\b|\bnão\s+foram\s+encontradas\s+evidências\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnão\s+(?:forneço|fornecemos|realizo|realizamos)\s+(?:recomendaç|previs)", re.IGNORECASE
    ),
    re.compile(r"\babsten(?:ho|ção)\b", re.IGNORECASE),
    re.compile(r"\bnão\s+(?:é\s+permitido|autorizado)\s+prever\b", re.IGNORECASE),
    re.compile(r"\bnão\s+é\s+possível\s+(?:prever|estimar|calcular|recomendar)\b", re.IGNORECASE),
    re.compile(r"\bdados\s+insuficientes\b|\binformações\s+insuficientes\b", re.IGNORECASE),
    re.compile(r"\bsolicitar\s+o\s+cálculo\s+ao\s+sistema\b", re.IGNORECASE),
    re.compile(r"\bresultado\s+determinístico\s+não\s+foi\s+fornecido\b", re.IGNORECASE),
]

# Indicadores de perguntas numéricas que demandam cálculo
NUMERIC_QUERY_PATTERNS = [
    re.compile(r"\bcalcule\b", re.IGNORECASE),
    re.compile(r"\bcalcular\b", re.IGNORECASE),
    re.compile(r"\bcálculo\b", re.IGNORECASE),
    re.compile(r"\bcalculo\b", re.IGNORECASE),
    re.compile(r"\bqual\s+(?:é\s+)?o\s+(?:saldo|total|resultado|valor)\b", re.IGNORECASE),
    re.compile(r"\bquanto\s+(?:sobra|sobrou|resta|rendeu|custa)\b", re.IGNORECASE),
    re.compile(r"\bquantos\s+meses\b", re.IGNORECASE),
    re.compile(r"\btaxa\s+de\s+poupança\b", re.IGNORECASE),
    re.compile(r"\breceitas\s+de\b.*?\bdespesas\s+de\b", re.IGNORECASE),
    re.compile(r"\bdespesas\s+de\b.*?\breceitas\s+de\b", re.IGNORECASE),
    re.compile(r"\bmenos\s+despesa\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class NumberFact:
    """Fato numérico extraído com representação canônica e unidade/tipo."""

    canonical: str
    kind: str  # "moeda", "percentual", "prazo", "geral"
    raw_text: str


def _ascii(text: str) -> str:
    """Normaliza texto removendo acentos para minúsculas."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def canonicalize_number(raw: str) -> str:
    """Converte representações numéricas pt-BR e internacionais para forma decimal canônica.

    Exemplos:
    - "1.234,56" -> "1234.56"
    - "0,20" -> "0.2"
    - "12,5" -> "12.5"
    - "30" -> "30"
    """
    cleaned = raw.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        dec = Decimal(cleaned).normalize()
        s = format(dec, "f")
        return s.rstrip("0").rstrip(".") if "." in s else s
    except (InvalidOperation, ValueError):
        return cleaned


def strip_citations(text: str) -> str:
    """Remove marcadores de citação entre colchetes [n] para evitar falsos positivos."""
    return CITATION_PATTERN.sub(" ", text)


def strip_list_markers(text: str) -> str:
    """Remove marcadores de listas ordenadas (1., 2), 1 -, etc.) do texto."""
    result = text
    for pattern in LIST_MARKER_PATTERNS:
        result = pattern.sub(" ", result)
    return result


def extract_ptbr_numbers(text: str, filter_structural: bool = True) -> set[NumberFact]:
    """Extrai fatos numéricos com suporte estrito a formatos pt-BR.

    Suporta:
    - Moedas: 'R$ 1.234,56', 'US$ 50', 'R$ 0,20'
    - Percentuais: '12,5%', '33,33%', '10%'
    - Prazos e faixas temporais: '30 dias', '1-3 anos', '3 a 5 anos'
    - Números gerais: inteiros e decimais isolados

    Se filter_structural=True, remove previamente marcadores de lista ('1.', '2.')
    e citações ('[1]') para eliminar os falsos positivos identificados na Semana 3.
    """
    if not text or not text.strip():
        return set()

    working_text = text
    if filter_structural:
        working_text = strip_list_markers(strip_citations(text))

    facts: set[NumberFact] = set()
    covered_spans: list[tuple[int, int]] = []

    def is_covered(start: int, end: int) -> bool:
        return any(s <= start and end <= e for s, e in covered_spans)

    # 1. Moedas
    for m in CURRENCY_PATTERN.finditer(working_text):
        covered_spans.append(m.span())
        facts.add(
            NumberFact(
                canonical=canonicalize_number(m.group(1)),
                kind="moeda",
                raw_text=m.group(0).strip(),
            )
        )

    # 2. Percentuais
    for m in PERCENT_PATTERN.finditer(working_text):
        if not is_covered(*m.span()):
            covered_spans.append(m.span())
            facts.add(
                NumberFact(
                    canonical=canonicalize_number(m.group(1)),
                    kind="percentual",
                    raw_text=m.group(0).strip(),
                )
            )

    # 3. Faixas temporais (ex: "1-3 anos", "3 a 5 anos")
    for m in TIME_RANGE_PATTERN.finditer(working_text):
        if not is_covered(*m.span()):
            covered_spans.append(m.span())
            unit = m.group(3)
            facts.add(
                NumberFact(
                    canonical=canonicalize_number(m.group(1)),
                    kind="prazo",
                    raw_text=f"{m.group(1)} {unit}",
                )
            )
            facts.add(
                NumberFact(
                    canonical=canonicalize_number(m.group(2)),
                    kind="prazo",
                    raw_text=f"{m.group(2)} {unit}",
                )
            )

    # 4. Prazos simples (ex: "30 dias", "12 meses")
    for m in TIME_SINGLE_PATTERN.finditer(working_text):
        if not is_covered(*m.span()):
            covered_spans.append(m.span())
            facts.add(
                NumberFact(
                    canonical=canonicalize_number(m.group(1)),
                    kind="prazo",
                    raw_text=m.group(0).strip(),
                )
            )

    # 5. Números gerais restantes
    for m in GENERAL_NUMBER_PATTERN.finditer(working_text):
        if not is_covered(*m.span()):
            covered_spans.append(m.span())
            facts.add(
                NumberFact(
                    canonical=canonicalize_number(m.group(1)),
                    kind="geral",
                    raw_text=m.group(0).strip(),
                )
            )

    return facts


# ============================================================================
# Regras Puras de Validação
# ============================================================================


def check_number_support(
    draft_answer: str,
    supported_texts: list[str],
    calculations: list[CalculationResult],
) -> list[ValidationIssue]:
    """Valida se todos os números do rascunho possuem suporte nas evidências ou cálculos.

    Gera NUMBER_NOT_SUPPORTED (BLOCKER) para qualquer valor monetário, percentual,
    prazo ou número geral ausente das fontes autorizadas.
    """
    if not draft_answer or not draft_answer.strip():
        return []

    draft_facts = extract_ptbr_numbers(draft_answer, filter_structural=True)
    if not draft_facts:
        return []

    # Extrai números das fontes textuais (evidências, pergunta)
    source_facts: set[NumberFact] = set()
    for text in supported_texts:
        if text:
            # Nas fontes extraímos sem filtrar estruturas, garantindo cobertura total
            source_facts.update(extract_ptbr_numbers(text, filter_structural=False))

    # Mapeia números dos cálculos determinísticos
    calculation_canonicals: set[str] = set()
    for calc in calculations:
        val_str = str(calc.value)
        calculation_canonicals.add(canonicalize_number(val_str))
        # Extrai também números do rótulo ou unidade do cálculo se existirem
        source_facts.update(
            extract_ptbr_numbers(f"{calc.label} {calc.value} {calc.unit}", filter_structural=False)
        )

    issues: list[ValidationIssue] = []
    unsupported_facts: list[NumberFact] = []

    for fact in sorted(draft_facts, key=lambda f: (f.kind, f.canonical)):
        # 1. Presente nos cálculos determinísticos?
        if fact.canonical in calculation_canonicals:
            continue

        # 2. Presente em fatos das fontes?
        supported = False
        for src in source_facts:
            if src.canonical == fact.canonical:
                if fact.kind == "geral" or src.kind == "geral" or fact.kind == src.kind:
                    supported = True
                    break

        if supported:
            continue

        # 3. Substring exata presente em alguma fonte textual?
        if any(fact.raw_text in text for text in supported_texts if text):
            continue

        unsupported_facts.append(fact)

    for fact in unsupported_facts:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.NUMBER_NOT_SUPPORTED,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"Número sem suporte factual encontrado no rascunho: '{fact.raw_text}' "
                    f"(valor canônico: {fact.canonical}, tipo: {fact.kind})."
                ),
            )
        )

    return issues


def check_citations(
    draft_answer: str,
    evidences: list[EvidenceChunk],
) -> list[ValidationIssue]:
    """Valida a integridade das citações [n] no rascunho de resposta.

    Gera CITATION_INVALID (BLOCKER) se:
    1. Marcador [n] referenciar evidência inexistente (ex: [3] quando há 2 evidências, ou [0]).
    2. Evidências estiverem disponíveis mas o rascunho não contiver nenhuma citação.
    """
    if not draft_answer or not draft_answer.strip():
        return []

    citations = [int(m) for m in re.findall(r"\[(\d+)\]", draft_answer)]
    issues: list[ValidationIssue] = []
    max_evidences = len(evidences)

    # Se há evidências disponíveis, exige pelo menos uma citação
    if max_evidences > 0 and not citations:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.CITATION_INVALID,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"O rascunho possui {max_evidences} evidência(s) disponível(is), "
                    "mas não incluiu nenhuma citação de fonte [n] no texto."
                ),
            )
        )

    # Verifica se alguma citação extrapola as evidências disponíveis
    invalid_indices = {idx for idx in citations if idx < 1 or idx > max_evidences}
    for invalid_idx in sorted(invalid_indices):
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.CITATION_INVALID,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"A citação [{invalid_idx}] no rascunho é inválida pois não há "
                    f"evidência correspondente (total disponível: {max_evidences})."
                ),
            )
        )

    return issues


def check_out_of_scope_advice(draft_answer: str) -> list[ValidationIssue]:
    """Valida se o rascunho contém aconselhamento fora de escopo ou promessas de retorno.

    Gera OUT_OF_SCOPE_ADVICE (BLOCKER) para recomendações de produtos/ações específicas,
    promessas de rendimento ou termos proibidos como 'garantido'.
    Ignora menções que estejam sob negação pedagógica (ex: 'não há retorno garantido').
    """
    if not draft_answer or not draft_answer.strip():
        return []

    issues: list[ValidationIssue] = []
    seen_reasons: set[str] = set()

    for pattern, reason in OUT_OF_SCOPE_PATTERNS:
        for match in pattern.finditer(draft_answer):
            # Verifica se há negação imediatamente anterior na mesma oração
            prefix = draft_answer[max(0, match.start() - 50) : match.start()]
            if NEGATION_PREFIX_PATTERN.search(prefix):
                # Ocorrência negada pedagogicamente (ex: "não possui retorno garantido")
                continue

            if reason not in seen_reasons:
                seen_reasons.add(reason)
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.OUT_OF_SCOPE_ADVICE,
                        severity=IssueSeverity.BLOCKER,
                        message=(
                            f"O rascunho contém orientação financeira fora de escopo "
                            f"ou termo proibido: '{match.group(0)}' ({reason})."
                        ),
                    )
                )

    return issues


def check_abstention_mismatch(
    draft_answer: str,
    abstain_reason: str | None,
) -> list[ValidationIssue]:
    """Valida se o rascunho respeitou o motivo de abstenção registrado no contexto.

    Gera ABSTENTION_MISMATCH (BLOCKER) quando abstain_reason está preenchido, mas o rascunho
    fornece uma resposta substantiva em vez de declarar a recusa pedagógica.
    """
    if not abstain_reason or not abstain_reason.strip():
        return []

    if not draft_answer or not draft_answer.strip():
        # Rascunho vazio com abstenção não viola a regra
        return []

    # Verifica se o rascunho expressa abstenção ativa
    is_abstaining_text = any(pattern.search(draft_answer) for pattern in ABSTENTION_INDICATORS)

    if not is_abstaining_text:
        return [
            ValidationIssue(
                code=ValidationIssueCode.ABSTENTION_MISMATCH,
                severity=IssueSeverity.BLOCKER,
                message=(
                    f"O contexto indicou motivo de abstenção ('{abstain_reason}'), "
                    "mas o rascunho forneceu uma resposta substantiva em vez de se abster."
                ),
            )
        ]

    return []


def check_calculation_missing(
    query: str,
    draft_answer: str,
    calculations: list[CalculationResult],
) -> list[ValidationIssue]:
    """Valida se uma pergunta numérica recebeu cálculo determinístico oficial.

    Gera CALCULATION_MISSING (BLOCKER) se a pergunta exige cálculo, calculations está vazio
    e o rascunho tenta apresentar resultado aritmético autônomo.
    """
    if not query or not draft_answer or calculations:
        return []

    # Verifica se a pergunta demanda cálculo numérico
    is_numeric_query = any(pattern.search(query) for pattern in NUMERIC_QUERY_PATTERNS)
    if not is_numeric_query:
        return []

    # Se a pergunta exige cálculo e calculations está vazio, verifica se o rascunho
    # apresentou resultado quantitativo autônomo em vez de avisar a falta do cálculo.
    is_abstaining_or_pointing_missing = any(
        pattern.search(draft_answer) for pattern in ABSTENTION_INDICATORS
    )
    if is_abstaining_or_pointing_missing:
        return []

    # Se o rascunho apresenta números (moeda, percentual ou saldo calculado),
    # trata-se de cálculo autônomo não autorizado pela arquitetura determinística.
    draft_facts = extract_ptbr_numbers(draft_answer, filter_structural=True)
    numeric_claims = [f for f in draft_facts if f.kind in {"moeda", "percentual", "geral"}]

    if numeric_claims:
        return [
            ValidationIssue(
                code=ValidationIssueCode.CALCULATION_MISSING,
                severity=IssueSeverity.BLOCKER,
                message=(
                    "A pergunta requer cálculo numérico, mas o contexto não possui resultados "
                    "determinísticos e o rascunho apresentou resultado autônomo "
                    f"({numeric_claims[0].raw_text})."
                ),
            )
        ]

    return []


# ============================================================================
# Agente de Validação
# ============================================================================


class ValidationAgent:
    """Agente responsável por auditar deterministamente os rascunhos antes da saída final."""

    name: AgentName = AgentName.VALIDATION

    def validate(self, ctx: AgentContext) -> AgentStep:
        """Executa a bateria de regras puras e atualiza o contexto compartilhado."""
        start_time = time.perf_counter()
        draft = ctx.draft_answer or ""
        issues: list[ValidationIssue] = []

        # 1. Orientação fora de escopo ou promessa de retorno
        issues.extend(check_out_of_scope_advice(draft))

        # 2. Resposta incompatível com motivo de abstenção
        issues.extend(check_abstention_mismatch(draft, ctx.abstain_reason))

        # 3. Integridade e pertinência de citações
        issues.extend(check_citations(draft, ctx.evidences))

        # 4. Cálculo numérico ausente em pergunta quantitativa
        issues.extend(check_calculation_missing(ctx.query, draft, ctx.calculations))

        # 5. Números sem suporte nas evidências ou cálculos
        supported_texts = [ctx.query] + [e.content for e in ctx.evidences]
        issues.extend(check_number_support(draft, supported_texts, ctx.calculations))

        # Atualiza a lista de issues do contexto
        ctx.issues.extend(issues)

        # Determina o status do passo
        has_blocker = any(i.severity == IssueSeverity.BLOCKER for i in ctx.issues)
        status = AgentStepStatus.FAILED if has_blocker else AgentStepStatus.OK
        duration_ms = (time.perf_counter() - start_time) * 1000

        summary = (
            f"Validação reprovada: {len(ctx.issues)} problema(s) impeditivo(s) encontrado(s)."
            if has_blocker
            else "Validação aprovada: resposta em conformidade com as regras de integridade."
        )

        return AgentStep(
            agent=self.name,
            status=status,
            summary=summary,
            duration_ms=round(duration_ms, 2),
            details={
                "issues_count": len(ctx.issues),
                "blockers_count": sum(1 for i in ctx.issues if i.severity == IssueSeverity.BLOCKER),
                "warnings_count": sum(1 for i in ctx.issues if i.severity == IssueSeverity.WARNING),
                "issues": [i.model_dump() for i in ctx.issues],
            },
        )

    async def run(self, ctx: AgentContext) -> AgentStep:
        """Executa o agente em conformidade com o protocolo Agent."""
        return self.validate(ctx)
