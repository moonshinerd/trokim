import pytest

from app.domain.agents import (
    AgentContext,
    AgentName,
    CalculationResult,
    EvidenceChunk,
    StepStatus,
)
from app.services.agents.validation import ValidationAgent


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
        blockers = [i for i in ctx.issues if i.severity == "blocker"]
        if step.status == StepStatus.FAILED or len(blockers) > 0:
            false_positives += 1

    assert false_positives == 0, f"Houve {false_positives} falsos positivos em rascunhos válidos!"


@pytest.mark.asyncio
async def test_validation_accepts_named_markdown_links(base_evidence):
    agent = ValidationAgent()
    draft = (
        "Conforme diretrizes oficiais do [Banco Central do Brasil](https://www.bcb.gov.br/doc1), "
        "é recomendável destinar recursos para a reserva financeira."
    )
    ctx = AgentContext(
        question="Como organizar minha reserva?",
        draft_answer=draft,
        evidences=base_evidence,
    )

    step = await agent.run(ctx)

    assert step.status == StepStatus.OK
    assert not any(i.severity == "blocker" for i in ctx.issues)
