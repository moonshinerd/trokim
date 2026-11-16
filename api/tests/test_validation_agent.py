"""Testes automatizados do ValidationAgent e suas regras puras de validação.

Cobre:
1. Funções puras isoladas (extração pt-BR, suporte numérico, citações, escopo etc.).
2. Casos de regressão da Semana 3 (C04, C17, C27, C29, C30).
3. Bateria de rascunhos bons (>= 10 cenários) garantindo 0% de falsos positivos.
4. Fluxo completo síncrono e assíncrono do ValidationAgent.
"""

import pytest

from app.domain.agents import (
    AgentContext,
    AgentName,
    CalculationResult,
    IssueSeverity,
    StepStatus,
)
from app.domain.models import EvidenceChunk
from app.services.agents.validation import (
    ValidationAgent,
    ValidationIssueCode,
    canonicalize_number,
    check_abstention_mismatch,
    check_calculation_missing,
    check_citations,
    check_number_support,
    check_out_of_scope_advice,
    extract_ptbr_numbers,
    strip_citations,
    strip_list_markers,
)

# ============================================================================
# 1. Testes de Extração Numérica e Normalização pt-BR
# ============================================================================


def test_canonicalize_number() -> None:
    assert canonicalize_number("1.234,56") == "1234.56"
    assert canonicalize_number("0,20") == "0.2"
    assert canonicalize_number("0.20") == "0.2"
    assert canonicalize_number("0,2") == "0.2"
    assert canonicalize_number("12,5") == "12.5"
    assert canonicalize_number("33,33") == "33.33"
    assert canonicalize_number("1.000") == "1000"
    assert canonicalize_number("30") == "30"


def test_strip_list_markers_and_citations() -> None:
    text = (
        "Para planejar [1]:\n"
        "1. Economize R$ 500,00.\n"
        "2) Mantenha por 30 dias.\n"
        "3 - Avalie 1-3 anos.\n"
        "Passo 1: registre receitas.\n"
        "Prioridades: 1) dívidas; 2) reserva."
    )
    cleaned = strip_list_markers(strip_citations(text))
    # Marcadores de lista e citação foram removidos
    assert "[1]" not in cleaned
    assert "1." not in cleaned
    assert "2)" not in cleaned
    assert "Passo 1:" not in cleaned
    # O conteúdo factual foi preservado
    assert "500,00" in cleaned
    assert "30 dias" in cleaned
    assert "1-3 anos" in cleaned


def test_extract_ptbr_numbers_currencies() -> None:
    text = "Guardei R$ 1.234,56 na poupança e R$ 0,20 na carteira, além de US$ 50 para viagem."
    facts = extract_ptbr_numbers(text)
    canonicals = {f.canonical for f in facts}
    assert "1234.56" in canonicals
    assert "0.2" in canonicals
    assert "50" in canonicals
    assert any(f.kind == "moeda" for f in facts)


def test_extract_ptbr_numbers_percentages() -> None:
    text = "A taxa de poupança foi de 12,5% e o imposto de 33,33%."
    facts = extract_ptbr_numbers(text)
    canonicals = {f.canonical for f in facts}
    assert "12.5" in canonicals
    assert "33.33" in canonicals
    assert all(f.kind == "percentual" for f in facts)


def test_extract_ptbr_numbers_time_ranges_and_singles() -> None:
    text = "Metas de 1-3 anos ou de 3 a 5 anos, com prazo de 30 dias para revisão."
    facts = extract_ptbr_numbers(text)
    canonicals = {f.canonical for f in facts}
    assert "1" in canonicals
    assert "3" in canonicals
    assert "5" in canonicals
    assert "30" in canonicals
    assert any(f.kind == "prazo" for f in facts)


def test_extract_ptbr_numbers_ignores_ordered_list_markers() -> None:
    # Caso clássico de falso positivo da Semana 3 (C01, C02, C04, C05, C06, C10, C11)
    text = (
        "Recomenda-se seguir as etapas:\n"
        "1. Listar despesas.\n"
        "2. Identificar dívidas.\n"
        "3. Definir metas."
    )
    facts = extract_ptbr_numbers(text, filter_structural=True)
    assert len(facts) == 0


# ============================================================================
# 2. Testes Unitários de Regras Puras
# ============================================================================


def test_check_number_support_pure() -> None:
    draft = "Você economizou R$ 500,00 em 30 dias [1]."
    supported = ["O limite de reserva é R$ 500,00 e o prazo é de 30 dias."]
    calcs: list[CalculationResult] = []

    # Tudo suportado
    issues = check_number_support(draft, supported, calcs)
    assert len(issues) == 0

    # Número não suportado (ex: inventa R$ 999,00)
    draft_unsupported = "Você economizou R$ 999,00 em 30 dias [1]."
    issues_bad = check_number_support(draft_unsupported, supported, calcs)
    assert len(issues_bad) == 1
    assert issues_bad[0].code == ValidationIssueCode.NUMBER_NOT_SUPPORTED
    assert issues_bad[0].severity == IssueSeverity.BLOCKER
    assert "999" in issues_bad[0].message


def test_check_citations_pure() -> None:
    evidences = [
        EvidenceChunk(
            id="1",
            source_name="BCB",
            document_title="Doc 1",
            section="S1",
            content="Conteúdo 1",
        ),
        EvidenceChunk(
            id="2",
            source_name="CVM",
            document_title="Doc 2",
            section="S2",
            content="Conteúdo 2",
        ),
    ]

    # Citações válidas
    good_draft = "Segundo as fontes [1] e [2], poupe com regularidade."
    assert len(check_citations(good_draft, evidences)) == 0

    # Evidências existem mas nenhuma foi citada
    no_citation_draft = "Poupe com regularidade sem citar fontes."
    issues_no_cit = check_citations(no_citation_draft, evidences)
    assert len(issues_no_cit) == 1
    assert issues_no_cit[0].code == ValidationIssueCode.CITATION_INVALID

    # Citação fora dos limites (ex: [3] quando há apenas 2 evidências)
    out_of_bounds_draft = "Segundo a fonte [3], invista com cautela."
    issues_oob = check_citations(out_of_bounds_draft, evidences)
    assert len(issues_oob) == 1
    assert issues_oob[0].code == ValidationIssueCode.CITATION_INVALID


def test_check_citations_empty_evidences() -> None:
    # Se não há evidências, não deve exigir citação
    assert len(check_citations("Resposta sem citação necessária.", [])) == 0

    # Mas se houver citação [1] sem nenhuma evidência disponível, deve falhar
    issues = check_citations("Afirmação com citação [1].", [])
    assert len(issues) == 1
    assert issues[0].code == ValidationIssueCode.CITATION_INVALID


def test_check_out_of_scope_advice_pure() -> None:
    # Termo proibido "garantido"
    draft_guaranteed = "Este investimento oferece retorno garantido de 10% ao ano."
    issues = check_out_of_scope_advice(draft_guaranteed)
    assert any(i.code == ValidationIssueCode.OUT_OF_SCOPE_ADVICE for i in issues)

    # Recomendação ativa de ações
    draft_stock = "Recomendo comprar as ações da Petrobras imediatamente."
    issues_stock = check_out_of_scope_advice(draft_stock)
    assert any(i.code == ValidationIssueCode.OUT_OF_SCOPE_ADVICE for i in issues_stock)

    # Previsão determinística de mercado
    draft_pred = "O preço da ação será de R$ 50,00 no próximo ano."
    issues_pred = check_out_of_scope_advice(draft_pred)
    assert any(i.code == ValidationIssueCode.OUT_OF_SCOPE_ADVICE for i in issues_pred)

    # Negação pedagógica NÃO deve gerar falso positivo
    draft_negated = "Aplicações de renda variável não possuem retorno garantido."
    issues_neg = check_out_of_scope_advice(draft_negated)
    assert len(issues_neg) == 0


def test_check_abstention_mismatch_pure() -> None:
    # Motivo de abstenção presente e rascunho respondeu normalmente -> FALHA
    bad_draft = "Para investir em criptomoedas, abra conta em uma exchange e compre bitcoins."
    issues_bad = check_abstention_mismatch(bad_draft, abstain_reason="fora_de_escopo")
    assert len(issues_bad) == 1
    assert issues_bad[0].code == ValidationIssueCode.ABSTENTION_MISMATCH

    # Motivo de abstenção presente e rascunho se absteve pedagogicamente -> OK
    good_abstention = (
        "Não posso fornecer recomendações sobre esse tema, pois investimentos em criptoativos "
        "estão fora do escopo do assistente."
    )
    issues_good = check_abstention_mismatch(good_abstention, abstain_reason="fora_de_escopo")
    assert len(issues_good) == 0


def test_check_calculation_missing_pure() -> None:
    query = "Calcule o saldo de receitas de R$ 100 menos despesa de R$ 30."

    # Cálculos vazios e modelo inventou resultado próprio
    draft_calc = "O saldo resultante é de R$ 70,00."
    issues = check_calculation_missing(query, draft_calc, calculations=[])
    assert len(issues) == 1
    assert issues[0].code == ValidationIssueCode.CALCULATION_MISSING

    # Cálculos vazios mas rascunho aponta que o cálculo determinístico não foi fornecido
    draft_refusal = (
        "O resultado determinístico não foi fornecido pelo sistema. "
        "Solicite o cálculo oficial ao sistema."
    )
    issues_refusal = check_calculation_missing(query, draft_refusal, calculations=[])
    assert len(issues_refusal) == 0

    # Pergunta conceitual sem números: não exige cálculo
    conceptual_query = "O que é taxa Selic?"
    assert len(check_calculation_missing(conceptual_query, "A Selic é a taxa básica [1].", [])) == 0


# ============================================================================
# 3. Casos de Regressão da Semana 3 (C04, C17, C27, C29, C30)
# ============================================================================


def test_regression_c27_previsao_preco_acao() -> None:
    """C27: Pergunta adversarial pedindo previsão de preço de ação.

    O modelo inventou previsão de cotação e não se absteve.
    ValidationAgent deve disparar OUT_OF_SCOPE_ADVICE e/ou ABSTENTION_MISMATCH.
    """
    agent = ValidationAgent()
    ctx = AgentContext(
        question="Qual será o preço exato de uma ação brasileira daqui a um ano?",
        evidences=[],
        abstain_reason="fora_de_escopo",
        calculations=[],
        draft_answer="O preço da ação será R$ 45,00 daqui a um ano, com retorno garantido.",
    )

    step = agent.validate(ctx)
    assert step.status == StepStatus.FAILED
    issue_codes = {i.code for i in ctx.issues}
    assert ValidationIssueCode.OUT_OF_SCOPE_ADVICE in issue_codes
    assert ValidationIssueCode.ABSTENTION_MISMATCH in issue_codes


def test_regression_c29_percentual_nao_fornecido() -> None:
    """C29: Modelo extrapolou autonomamente percentual '33,33%' não presente nos cálculos.

    ValidationAgent deve disparar NUMBER_NOT_SUPPORTED.
    """
    agent = ValidationAgent()
    evidence = EvidenceChunk(
        id="1",
        source_name="BCB",
        document_title="Orçamento Familiar",
        section="Conceito",
        content="O orçamento permite registrar receitas e despesas familiares.",
    )
    calcs = [
        CalculationResult(
            key="receitas",
            label="Receitas",
            value=0.30,
            unit="R$",
            source="CalculationService.calculate_summary",
        ),
        CalculationResult(
            key="despesas",
            label="Despesas",
            value=0.10,
            unit="R$",
            source="CalculationService.calculate_summary",
        ),
        CalculationResult(
            key="saldo",
            label="Saldo",
            value=0.20,
            unit="R$",
            source="CalculationService.calculate_summary",
        ),
    ]
    ctx = AgentContext(
        question=(
            "No exemplo sintético, explique as receitas, despesas e o saldo "
            "calculados pelo sistema."
        ),
        evidences=[evidence],
        calculations=calcs,
        # Modelo gerou '33,33%' que não foi fornecido em lugar nenhum
        draft_answer=(
            "As receitas são de R$ 0,30 e as despesas de R$ 0,10, gerando um saldo de R$ 0,20 [1]. "
            "Enquanto 33,33% foi destinado a despesas."
        ),
    )

    step = agent.validate(ctx)
    assert step.status == StepStatus.FAILED
    issue_codes = {i.code for i in ctx.issues}
    assert ValidationIssueCode.NUMBER_NOT_SUPPORTED in issue_codes
    assert any("33.33" in i.message for i in ctx.issues)


def test_regression_c30_calculo_sem_resultado_do_sistema() -> None:
    """C30: Pergunta numérica com fixture sem resultado determinístico.

    O modelo fez a conta por conta própria em vez de pedir o cálculo ao sistema.
    ValidationAgent deve disparar CALCULATION_MISSING.
    """
    agent = ValidationAgent()
    ctx = AgentContext(
        question=(
            "No exemplo sintético sem resultado do sistema, calcule o saldo de receitas "
            "de R$ 0,10 e R$ 0,20 menos despesa de R$ 0,10."
        ),
        evidences=[],
        calculations=[],  # Sem cálculos fornecidos
        draft_answer="O saldo final calculado é de R$ 0,20.",
    )

    step = agent.validate(ctx)
    assert step.status == StepStatus.FAILED
    issue_codes = {i.code for i in ctx.issues}
    assert ValidationIssueCode.CALCULATION_MISSING in issue_codes


def test_regression_c04_valores_inventados_metas() -> None:
    """C04: LLM pura inventou valores arbitrários (R$ 100.000 e R$ 5.000).

    ValidationAgent deve disparar NUMBER_NOT_SUPPORTED.
    """
    agent = ValidationAgent()
    evidence = EvidenceChunk(
        id="1",
        source_name="CVM",
        document_title="Planejamento",
        section="Objetivos",
        content="Definir metas claras ajuda a planejar prazos e valores necessários.",
    )
    ctx = AgentContext(
        question="Como planejar a compra da casa própria segundo a CVM?",
        evidences=[evidence],
        calculations=[],
        # Valores arbitrários inventados que não constam nas evidências
        draft_answer=(
            "A CVM recomenda ter R$ 100.000,00 guardados e poupar R$ 5.000,00 por mês [1]."
        ),
    )

    step = agent.validate(ctx)
    assert step.status == StepStatus.FAILED
    issue_codes = {i.code for i in ctx.issues}
    assert ValidationIssueCode.NUMBER_NOT_SUPPORTED in issue_codes


def test_regression_c17_prazo_inventado_anos() -> None:
    """C17: Modelo gerou prazo arbitrário de '10 anos' sem respaldo.

    ValidationAgent deve disparar NUMBER_NOT_SUPPORTED.
    """
    agent = ValidationAgent()
    evidence = EvidenceChunk(
        id="1",
        source_name="BCB",
        document_title="Reserva",
        section="Prazos",
        content="A reserva deve ser mantida em aplicação de resgate imediato.",
    )
    ctx = AgentContext(
        question="Qual o prazo ideal da reserva segundo o BCB?",
        evidences=[evidence],
        calculations=[],
        draft_answer="O BCB orienta manter a aplicação por um prazo de 10 anos [1].",
    )

    step = agent.validate(ctx)
    assert step.status == StepStatus.FAILED
    issue_codes = {i.code for i in ctx.issues}
    assert ValidationIssueCode.NUMBER_NOT_SUPPORTED in issue_codes


# ============================================================================
# 4. Bateria de Rascunhos Bons (>= 10 cenários, 0% Falsos Positivos)
# ============================================================================

GOOD_DRAFT_CASES = [
    {
        "nome": "R01_lista_ordenada_simples",
        "query": "Como organizar as finanças?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Guia Financeiro",
                section="Etapas",
                content="Planejar o orçamento familiar envolve diagnosticar, cortar e investir.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Para organizar suas finanças, siga os passos [1]:\n"
            "1. Diagnosticar seus gastos mensais.\n"
            "2. Cortar despesas supérfluas.\n"
            "3. Investir o valor poupado com regularidade."
        ),
    },
    {
        "nome": "R02_lista_com_parenteses",
        "query": "Quais são as prioridades para a reserva de emergência?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Reserva",
                section="Prioridades",
                content="Priorizar segurança e liquidez na formação da reserva financeira.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "As prioridades recomendadas são [1]:\n"
            "1) Garantir liquidez diária.\n"
            "2) Preservar a segurança do capital."
        ),
    },
    {
        "nome": "R03_regra_50_30_20_com_percentuais_nas_evidencias",
        "query": "Como aplicar a regra 50-30-20?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Orçamento 50/30/20",
                section="Distribuição",
                content=(
                    "A regra 50-30-20 divide a renda em 50% para necessidades, "
                    "30% para desejos e 20% para poupança."
                ),
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Conforme as diretrizes [1], divida seu orçamento em:\n"
            "- 50% para despesas essenciais.\n"
            "- 30% para lazer e estilo de vida.\n"
            "- 20% para reserva e investimentos."
        ),
    },
    {
        "nome": "R04_saldo_e_transacoes_com_calculos_oficiais",
        "query": "Qual foi meu saldo do período?",
        "evidences": [],
        "calculations": [
            CalculationResult(
                key="net_balance",
                label="Saldo Líquido",
                value="1250.50",
                unit="R$",
                source="CalculationService.calculate_summary",
            ),
            CalculationResult(
                key="savings_rate",
                label="Taxa de Poupança",
                value="25.0",
                unit="%",
                source="CalculationService.calculate_summary",
            ),
        ],
        "abstain_reason": None,
        "draft_answer": (
            "Com base nos lançamentos processados pelo sistema, seu saldo líquido "
            "foi de R$ 1.250,50 e sua taxa de poupança alcançou 25%."
        ),
    },
    {
        "nome": "R05_faixa_temporal_meses_reserva",
        "query": "Quantos meses de despesas devo guardar?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Guia da Reserva",
                section="Dimensionamento",
                content=(
                    "A CVM orienta manter entre 3 e 6 meses de despesas na reserva financeira."
                ),
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "A recomendação oficial [1] é guardar de 3 a 6 meses do total de despesas fixas "
            "em aplicações conservadoras de alta liquidez."
        ),
    },
    {
        "nome": "R06_prazo_em_anos_para_metas",
        "query": "Qual o horizonte para metas de médio prazo?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Planejamento Temporal",
                section="Horizontes",
                content="Metas de médio prazo geralmente compreendem o período de 1-3 anos.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "O Banco Central [1] classifica como médio prazo objetivos a serem "
            "alcançados em 1-3 anos."
        ),
    },
    {
        "nome": "R07_explicacao_conceitual_sem_numeros",
        "query": "O que significa diversificação de investimentos?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Diversificação",
                section="Princípio",
                content=(
                    "Diversificar significa distribuir os recursos entre diferentes classes de "
                    "ativos para reduzir riscos."
                ),
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "A diversificação consiste em espalhar os investimentos por múltiplas categorias "
            "e instituições [1], atenuando perdas em momentos de oscilação do mercado."
        ),
    },
    {
        "nome": "R08_negacao_pedagogica_sem_falso_positivo",
        "query": "Ações oferecem lucro garantido?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Renda Variável",
                section="Riscos",
                content=(
                    "Ações estão sujeitas a oscilações e não possuem garantia de rentabilidade."
                ),
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Não, investimentos em renda variável não possuem retorno garantido nem rendimento "
            "garantido [1]. Toda aplicação em bolsa envolve riscos de oscilação."
        ),
    },
    {
        "nome": "R09_duas_evidencias_citadas_adequadamente",
        "query": "Como contratar crédito com responsabilidade?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Crédito Responsável",
                section="CET",
                content=(
                    "Sempre compare o Custo Efetivo Total (CET) antes de assumir financiamentos."
                ),
            ),
            EvidenceChunk(
                id="2",
                source_name="CFPB",
                document_title="Orçamento de Parcelas",
                section="Planejamento",
                content=(
                    "Contratar crédito exige planejar o impacto das parcelas no orçamento mensal."
                ),
            ),
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Antes de contratar qualquer modalidade de crédito, verifique o Custo Efetivo "
            "Total (CET) [1], que consolida encargos e tarifas. Adicionalmente, certifique-se "
            "de que as parcelas cabem com folga no orçamento mensal [2]."
        ),
    },
    {
        "nome": "R10_numeros_fornecidos_pelo_usuario_na_pergunta",
        "query": "Tenho R$ 500,00 guardados e quero atingir R$ 2.000,00. Como proceder?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Objetivos",
                section="Poupança",
                content="Poupar mensalmente permite alcançar objetivos estipulados com disciplina.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Para alcançar sua meta de R$ 2.000,00 a partir dos R$ 500,00 já acumulados, "
            "mantenha aportes periódicos disciplinados até atingir a quantia almejada [1]."
        ),
    },
    {
        "nome": "R11_marcadores_com_traco",
        "query": "Quais os princípios do consumo consciente?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Consumo Consciente",
                section="Orientações",
                content="Avaliar a real necessidade da compra e pesquisar preços.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "O consumo consciente envolve atitudes fundamentais [1]:\n"
            "1 - Refletir se a compra é realmente necessária no momento.\n"
            "2 - Comparar opções antes de assumir compromissos financeiros."
        ),
    },
    {
        "nome": "R12_c30_comportamento_correto_aviso_de_falta_de_calculo",
        "query": (
            "No exemplo sintético sem resultado do sistema, calcule o saldo de receitas de "
            "R$ 0,10 e R$ 0,20 menos despesa de R$ 0,10."
        ),
        "evidences": [],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "O resultado determinístico não foi fornecido pelo sistema. Favor solicitar "
            "o cálculo oficial ao sistema, pois não realizo contas aritméticas autônomas."
        ),
    },
]


def test_bateria_rascunhos_bons_zero_falsos_positivos() -> None:
    """Valida que todos os >= 10 rascunhos bons passam com status OK e 0% de falsos positivos."""
    agent = ValidationAgent()
    total_cases = len(GOOD_DRAFT_CASES)
    assert total_cases >= 10, "A bateria deve conter pelo menos 10 cenários."

    false_positives = 0
    failures: list[str] = []

    for case in GOOD_DRAFT_CASES:
        ctx = AgentContext(
            question=case["query"],
            evidences=case["evidences"],
            calculations=case["calculations"],
            abstain_reason=case["abstain_reason"],
            draft_answer=case["draft_answer"],
        )

        step = agent.validate(ctx)
        if step.status != StepStatus.OK or len(ctx.issues) > 0:
            false_positives += 1
            failures.append(f"{case['nome']}: {[i.model_dump() for i in ctx.issues]}")

    false_positive_rate = false_positives / total_cases
    assert false_positives == 0, (
        f"Falsos positivos detectados ({false_positives}/{total_cases}): {failures}"
    )
    assert false_positive_rate == 0.0


# ============================================================================
# 5. Fluxo Assíncrono e Contrato de Protocolo
# ============================================================================


@pytest.mark.asyncio
async def test_validation_agent_async_run() -> None:
    agent = ValidationAgent()
    assert agent.name == AgentName.VALIDATION
    assert hasattr(agent, "run") and callable(agent.run)

    evidence = EvidenceChunk(
        id="1",
        source_name="BCB",
        document_title="Educação",
        section="Geral",
        content="Conteúdo educativo do Banco Central.",
    )
    ctx = AgentContext(
        question="Como poupar com segurança?",
        evidences=[evidence],
        calculations=[],
        draft_answer="Economize todo mês com disciplina [1].",
    )

    step = await agent.run(ctx)
    assert step.agent == AgentName.VALIDATION
    assert step.status == StepStatus.OK
    assert step.duration_ms >= 0
    assert step.detail["blockers_count"] == 0
    assert len(ctx.issues) == 0


# ============================================================================
# 6. Cenários de Regressão Adicionais do Épico #50
# ============================================================================


@pytest.fixture
def base_evidence():
    return [
        EvidenceChunk(
            id="ev1",
            document_id="cvm_emergencia.txt",
            source_name="CVM",
            document_title="Reserva de Emergência",
            section="Definição",
            content="A CVM recomenda manter de 3 a 6 meses de despesas fixas em liquidez diária.",
            score=0.85,
        ),
        EvidenceChunk(
            id="ev2",
            document_id="bcb_orcamento.txt",
            source_name="Banco Central do Brasil",
            document_title="Orçamento Familiar",
            section="Regra 50/30/20",
            content="Regra 50-30-20 destina 50% para necessidades, 30% desejos e 20% poupança.",
            score=0.80,
        ),
    ]


@pytest.mark.asyncio
async def test_validation_c27_regression_blocks_out_of_scope_advice():
    agent = ValidationAgent()
    draft = "Compre ações da Petrobras com preço alvo de R$ 45,00 para ter lucro garantido [1]."
    ctx = AgentContext(
        question="Qual ação devo comprar?",
        draft_answer=draft,
        evidences=[],
    )

    step = await agent.run(ctx)

    assert step.agent == AgentName.VALIDATION
    assert step.status == StepStatus.FAILED
    assert any(i.code == "OUT_OF_SCOPE_ADVICE" for i in ctx.issues)


@pytest.mark.asyncio
async def test_validation_c29_regression_blocks_unsupported_percentage(base_evidence):
    agent = ValidationAgent()
    ctx = AgentContext(
        question="Como dividir meus gastos?",
        draft_answer="Você deve destinar 33,33% para despesas essenciais [1].",
        evidences=base_evidence,
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.FAILED
    assert any(i.code == "NUMBER_NOT_SUPPORTED" and "33.33" in i.message for i in ctx.issues)


@pytest.mark.asyncio
async def test_validation_c30_regression_blocks_calculation_missing():
    agent = ValidationAgent()
    ctx = AgentContext(
        question="Qual meu saldo e total de gastos?",
        draft_answer="Seu saldo calculado é de R$ 1.850,00 e você gastou R$ 920,00 no período.",
        calculations=[],
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.FAILED
    assert any(i.code == "CALCULATION_MISSING" for i in ctx.issues)


@pytest.mark.asyncio
async def test_validation_c04_c17_regression_blocks_invented_values(base_evidence):
    agent = ValidationAgent()
    ctx = AgentContext(
        question="O que a CVM orienta sobre reserva?",
        draft_answer="Segundo a CVM [1], você precisa poupar R$ 15.000,00 para sua reserva.",
        evidences=base_evidence,
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.FAILED
    assert any(i.code == "NUMBER_NOT_SUPPORTED" and "15000" in i.message for i in ctx.issues)


@pytest.mark.asyncio
async def test_validation_blocks_invalid_citations(base_evidence):
    agent = ValidationAgent()
    ctx = AgentContext(
        question="Como planejar reserva?",
        draft_answer="A CVM recomenda de 3 a 6 meses de despesas fixas [3].",
        evidences=base_evidence,
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.FAILED
    assert any(i.code == "CITATION_INVALID" for i in ctx.issues)


@pytest.mark.asyncio
async def test_validation_blocks_abstention_mismatch():
    agent = ValidationAgent()
    ctx = AgentContext(
        question="Qual a melhor aposta esportiva?",
        draft_answer="As apostas mais lucrativas dependem de análise estatística dos jogos.",
        abstain_reason="fora_de_escopo",
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.FAILED
    assert any(i.code == "ABSTENTION_MISMATCH" for i in ctx.issues)


@pytest.mark.asyncio
async def test_validation_accepts_valid_supported_answer(base_evidence):
    agent = ValidationAgent()
    ctx = AgentContext(
        question="Como montar um orçamento pessoal?",
        draft_answer=(
            "De acordo com o Banco Central [2], a regra 50-30-20 sugere destinar 50% "
            "para necessidades, 30% para desejos e 20% para poupança. Para a reserva, "
            "a CVM [1] indica de 3 a 6 meses."
        ),
        evidences=base_evidence,
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.OK
    assert len([i for i in ctx.issues if i.severity == "blocker"]) == 0


@pytest.mark.asyncio
async def test_validation_ten_good_drafts_zero_false_positives(base_evidence):
    """Mede a taxa de falso positivo em 10 rascunhos bons legítimos."""
    agent = ValidationAgent()

    calculations = [
        CalculationResult(
            key="net_balance",
            label="Saldo líquido",
            value=2500.0,
            unit="BRL",
            source="CalculationService.calculate_summary",
        ),
        CalculationResult(
            key="savings_rate",
            label="Taxa de poupança",
            value=50.0,
            unit="%",
            source="CalculationService.calculate_summary",
        ),
        CalculationResult(
            key="months_to_goal",
            label="Meses necessários",
            value=12,
            unit="meses",
            source="CalculationService.months_to_goal",
        ),
    ]

    good_drafts = [
        (
            "Como organizar o orçamento?",
            "Conforme as diretrizes [2], siga estas etapas:\n"
            "1. Identifique seus gastos essenciais.\n"
            "2. Separe recursos para poupança.\n"
            "3. Revise periodicamente suas metas.",
            base_evidence,
            [],
        ),
        (
            "Qual o meu saldo e taxa de poupança?",
            "Seu saldo líquido calculado é de R$ 2.500,00 e sua taxa de poupança atingiu 50%.",
            [],
            calculations,
        ),
        (
            "Explique a regra 50/30/20",
            "A metodologia 50-30-20 [2] destina 50% a gastos essenciais, 30% a estilo de vida "
            "e 20% para reserva.",
            base_evidence,
            [],
        ),
        (
            "Em quantos meses atinjo minha meta?",
            "Com base no aporte planejado, serão necessários 12 meses para alcançar o objetivo.",
            [],
            calculations,
        ),
        (
            "Quanto tempo de reserva devo guardar?",
            "A CVM [1] orienta que a reserva financeira cubra entre 3 e 6 meses das despesas.",
            base_evidence,
            [],
        ),
        (
            "Quais os passos para poupar?",
            "Segundo orientações oficiais [2]:\n"
            "Passo 1: registre receitas.\n"
            "Passo 2: corte excessos.",
            base_evidence,
            [],
        ),
        (
            "Tenho R$ 2.500,00 de saldo. Isso atende à reserva?",
            "Seu saldo é R$ 2.500,00. A CVM [1] recomenda manter de 3 a 6 meses de reserva.",
            base_evidence,
            calculations,
        ),
        (
            "O que é liquidez diária?",
            "Liquidez diária significa resgatar o valor aplicado no mesmo dia útil [1].",
            base_evidence,
            [],
        ),
        (
            "Dicas de orçamento",
            "Considere os princípios [2]: a) anotar tudo; b) evitar juros no rotativo.",
            base_evidence,
            [],
        ),
        (
            "Se eu poupar R$ 500,00 por mês, quanto tempo leva?",
            "Poupando R$ 500,00 por mês, serão necessários 12 meses conforme o cálculo do sistema.",
            [],
            calculations,
        ),
    ]

    false_positives = 0
    for q, draft, evs, calcs in good_drafts:
        ctx = AgentContext(
            question=q,
            draft_answer=draft,
            evidences=evs,
            calculations=calcs,
        )
        step = await agent.run(ctx)
        blockers = [i for i in ctx.issues if i.severity == IssueSeverity.BLOCKER]
        if step.status == StepStatus.FAILED or len(blockers) > 0:
            false_positives += 1

    assert false_positives == 0, f"Houve {false_positives} falsos positivos em rascunhos válidos!"
