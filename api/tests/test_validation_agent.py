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
    AgentStepStatus,
    CalculationResult,
    IssueSeverity,
    ValidationIssueCode,
)
from app.domain.models import EvidenceChunk
from app.services.agents.base import Agent
from app.services.agents.validation import (
    ValidationAgent,
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
        "Prioridades: 1) dívidas; 2) reserva."
    )
    cleaned = strip_list_markers(strip_citations(text))
    # Marcadores de lista e citação foram removidos
    assert "[1]" not in cleaned
    assert "1." not in cleaned
    assert "2)" not in cleaned
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


def test_check_number_support_with_calculations() -> None:
    draft = "Suas receitas foram de R$ 0,30 e o saldo de R$ 0,20 [1]."
    supported = ["Texto oficial sobre orçamento [1]."]
    calcs = [
        CalculationResult(key="receitas", label="Receitas", value=0.30, unit="R$"),
        CalculationResult(key="saldo", label="Saldo", value=0.20, unit="R$"),
    ]

    issues = check_number_support(draft, supported, calcs)
    assert len(issues) == 0


def test_check_citations_pure() -> None:
    evidences = [
        EvidenceChunk(
            id="1",
            source_name="BCB",
            document_title="Orçamento",
            section="Geral",
            content="Conteúdo 1",
        ),
        EvidenceChunk(
            id="2",
            source_name="CVM",
            document_title="Investimentos",
            section="Geral",
            content="Conteúdo 2",
        ),
    ]

    # Citações válidas [1] e [2]
    good_draft = "Segundo o BCB [1], controle gastos. Segundo a CVM [2], invista bem."
    assert len(check_citations(good_draft, evidences)) == 0

    # Falta de citação com evidências disponíveis
    no_citation_draft = "Controle seus gastos e invista bem."
    issues_no_cit = check_citations(no_citation_draft, evidences)
    assert len(issues_no_cit) == 1
    assert issues_no_cit[0].code == ValidationIssueCode.CITATION_INVALID
    assert "não incluiu nenhuma citação" in issues_no_cit[0].message

    # Citação fora do limite [3]
    out_of_bounds_draft = "Informação oficial [3]."
    issues_oob = check_citations(out_of_bounds_draft, evidences)
    assert len(issues_oob) == 1
    assert issues_oob[0].code == ValidationIssueCode.CITATION_INVALID
    assert "[3]" in issues_oob[0].message


def test_check_citations_empty_evidences() -> None:
    # Sem evidências no contexto: rascunho sem citação é válido
    assert len(check_citations("Resposta sem citação necessária.", [])) == 0

    # Sem evidências, mas rascunho inventa citação [1]
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
        query="Qual será o preço exato de uma ação brasileira daqui a um ano?",
        evidences=[],
        abstain_reason="fora_de_escopo",
        calculations=[],
        draft_answer="O preço da ação será R$ 45,00 daqui a um ano, com retorno garantido.",
    )

    step = agent.validate(ctx)
    assert step.status == AgentStepStatus.FAILED
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
        CalculationResult(key="receitas", label="Receitas", value=0.30, unit="R$"),
        CalculationResult(key="despesas", label="Despesas", value=0.10, unit="R$"),
        CalculationResult(key="saldo", label="Saldo", value=0.20, unit="R$"),
    ]
    ctx = AgentContext(
        query=(
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
    assert step.status == AgentStepStatus.FAILED
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
        query=(
            "No exemplo sintético sem resultado do sistema, calcule o saldo de receitas "
            "de R$ 0,10 e R$ 0,20 menos despesa de R$ 0,10."
        ),
        evidences=[],
        calculations=[],  # Sem cálculos fornecidos
        draft_answer="O saldo final calculado é de R$ 0,20.",
    )

    step = agent.validate(ctx)
    assert step.status == AgentStepStatus.FAILED
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
        document_title="Definição de Objetivos",
        section="Metas",
        content="Definir objetivos claros e prazos em que o dinheiro será necessário.",
    )
    ctx = AgentContext(
        query="Como definir metas financeiras e prazos?",
        evidences=[evidence],
        calculations=[],
        draft_answer=(
            "Para definir suas metas [1], planeje ter R$ 100.000,00 de reserva "
            "e acumular R$ 5.000,00 anuais em investimentos."
        ),
    )

    step = agent.validate(ctx)
    assert step.status == AgentStepStatus.FAILED
    unsupported_numbers = [
        i for i in ctx.issues if i.code == ValidationIssueCode.NUMBER_NOT_SUPPORTED
    ]
    assert len(unsupported_numbers) >= 2


def test_regression_c17_valores_inventados_rotativo() -> None:
    """C17: LLM pura inventou taxa de 1,5% e valor de R$ 1.018,25.

    ValidationAgent deve disparar NUMBER_NOT_SUPPORTED.
    """
    agent = ValidationAgent()
    evidence = EvidenceChunk(
        id="1",
        source_name="BCB",
        document_title="Rotativo do Cartão",
        section="Prazos",
        content="O saldo devedor pode permanecer no rotativo por até 30 dias.",
    )
    ctx = AgentContext(
        query="Até quando posso financiar o mesmo saldo no rotativo do cartão?",
        evidences=[evidence],
        calculations=[],
        draft_answer=(
            "O saldo pode ser financiado até 30 dias [1]. "
            "A taxa de juros aplicada é de 1,5% e o saldo fica em R$ 1.018,25."
        ),
    )

    step = agent.validate(ctx)
    assert step.status == AgentStepStatus.FAILED
    unsupported_numbers = [
        i for i in ctx.issues if i.code == ValidationIssueCode.NUMBER_NOT_SUPPORTED
    ]
    assert len(unsupported_numbers) >= 2


# ============================================================================
# 4. Bateria de Rascunhos Bons (>= 10 cenários) e Taxa de Falsos Positivos
# ============================================================================


GOOD_DRAFT_CASES = [
    {
        "nome": "R01_lista_numerada_passo_a_passo",
        "query": "Como organizar minhas finanças pessoais?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Planejamento",
                section="Etapas",
                content="O planejamento financeiro envolve listar despesas e mapear objetivos.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Para organizar suas finanças pessoais [1], recomenda-se seguir os passos:\n"
            "1. Liste todas as fontes de renda e gastos fixos.\n"
            "2. Identifique oportunidades de corte de despesas supérfluas.\n"
            "3. Estabeleça metas financeiras claras para o futuro."
        ),
    },
    {
        "nome": "R02_faixas_temporais_usuais",
        "query": "Quais são os prazos usuais para objetivos de investimento?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Objetivos Financeiros",
                section="Prazos",
                content=(
                    "Objetivos de curto prazo costumam variar de 1 a 3 anos e "
                    "médio prazo de 3 a 5 anos."
                ),
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Segundo as diretrizes oficiais [1], metas de curto prazo costumam ter prazos de "
            "1-3 anos, enquanto objetivos de médio prazo variam entre 3-5 anos."
        ),
    },
    {
        "nome": "R03_resumo_calculado_com_moeda_e_percentual",
        "query": "Qual é o resumo das minhas finanças com base no extrato importado?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Orçamento Familiar",
                section="Balanço",
                content="O balanço mensal compara receitas totais e despesas totais.",
            )
        ],
        "calculations": [
            CalculationResult(key="total_income", label="Receitas", value=3500.0, unit="R$"),
            CalculationResult(key="total_expenses", label="Despesas", value=2100.0, unit="R$"),
            CalculationResult(key="net_balance", label="Saldo Líquido", value=1400.0, unit="R$"),
            CalculationResult(key="savings_rate", label="Taxa de Poupança", value=40.0, unit="%"),
        ],
        "abstain_reason": None,
        "draft_answer": (
            "Conforme os dados do seu extrato [1], suas receitas totalizaram R$ 3.500,00 e as "
            "despesas somaram R$ 2.100,00, gerando um saldo positivo de R$ 1.400,00. "
            "Sua taxa de poupança no período foi de 40,0%."
        ),
    },
    {
        "nome": "R04_prazo_do_rotativo_em_dias",
        "query": "Até quando o saldo pode ficar no rotativo?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Regras do Rotativo",
                section="Prazos",
                content="O saldo devedor pode permanecer no crédito rotativo por até 30 dias.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "De acordo com a regulamentação do Banco Central [1], o saldo devedor não pode "
            "permanecer no rotativo por mais de 30 dias, devendo ser quitado ou parcelado."
        ),
    },
    {
        "nome": "R05_marcadores_com_parenteses",
        "query": "Quais as orientações para renegociação de dívidas?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CFPB",
                document_title="Dívidas",
                section="Renegociação",
                content="Priorizar dívidas essenciais e entrar em contato com os credores.",
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "Ao renegociar débitos [1], mantenha duas diretrizes em foco:\n"
            "1) quite primeiro os compromissos vinculados a serviços essenciais;\n"
            "2) proponha parcelas compatíveis com o seu orçamento real."
        ),
    },
    {
        "nome": "R06_orientacao_qualitativa_sem_numeros",
        "query": "Onde devo guardar minha reserva de emergência?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="CVM",
                document_title="Reserva de Emergência",
                section="Liquidez",
                content=(
                    "A reserva de emergência deve ser mantida em produtos de "
                    "alta liquidez e baixo risco."
                ),
            )
        ],
        "calculations": [],
        "abstain_reason": None,
        "draft_answer": (
            "A reserva de emergência deve ser alocada prioritariamente em aplicações com alta "
            "liquidez e baixo risco de mercado [1], viabilizando resgates imediatos em imprevistos."
        ),
    },
    {
        "nome": "R07_abstencao_pedagogica_correta",
        "query": "Qual ação vai render mais no próximo mês?",
        "evidences": [],
        "calculations": [],
        "abstain_reason": "fora_de_escopo",
        "draft_answer": (
            "Não posso fornecer recomendações sobre ações específicas nem realizar previsões "
            "de mercado, pois tais orientações estão fora do escopo educativo do assistente."
        ),
    },
    {
        "nome": "R08_c29_comportamento_correto",
        "query": (
            "No exemplo sintético, explique as receitas, despesas e o saldo "
            "calculados pelo sistema."
        ),
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Orçamento Familiar",
                section="Cálculo",
                content="Receitas e despesas mensais formam a base do saldo financeiro.",
            )
        ],
        "calculations": [
            CalculationResult(key="receitas", label="Receitas", value=0.30, unit="R$"),
            CalculationResult(key="despesas", label="Despesas", value=0.10, unit="R$"),
            CalculationResult(key="saldo", label="Saldo", value=0.20, unit="R$"),
        ],
        "abstain_reason": None,
        "draft_answer": (
            "No cálculo determinístico apurado pelo sistema [1], as receitas somam R$ 0,30 e "
            "as despesas são de R$ 0,10, resultando em um saldo disponível de R$ 0,20."
        ),
    },
    {
        "nome": "R09_multiplas_fontes_com_citacoes",
        "query": "Como avaliar o custo de um empréstimo antes de contratar?",
        "evidences": [
            EvidenceChunk(
                id="1",
                source_name="BCB",
                document_title="Custo Efetivo Total",
                section="CET",
                content=(
                    "O Custo Efetivo Total (CET) inclui taxa de juros, tributos, tarifas e seguros."
                ),
            ),
            EvidenceChunk(
                id="2",
                source_name="CVM",
                document_title="Crédito Consciente",
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
            query=case["query"],
            evidences=case["evidences"],
            calculations=case["calculations"],
            abstain_reason=case["abstain_reason"],
            draft_answer=case["draft_answer"],
        )

        step = agent.validate(ctx)
        if step.status != AgentStepStatus.OK or len(ctx.issues) > 0:
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
    assert isinstance(agent, Agent)
    assert agent.name == AgentName.VALIDATION

    evidence = EvidenceChunk(
        id="1",
        source_name="BCB",
        document_title="Educação",
        section="Geral",
        content="Conteúdo educativo do Banco Central.",
    )
    ctx = AgentContext(
        query="Como poupar com segurança?",
        evidences=[evidence],
        calculations=[],
        draft_answer="Economize todo mês com disciplina [1].",
    )

    step = await agent.run(ctx)
    assert step.agent == AgentName.VALIDATION
    assert step.status == AgentStepStatus.OK
    assert step.duration_ms >= 0.0
    assert step.details["blockers_count"] == 0
    assert len(ctx.issues) == 0
