"""Regressões de limites de recorte e suporte numérico da RF30."""

import pytest
from test_financial_queries import CC, HOJE
from test_financial_queries import library as financial_library  # noqa: F401

from app.domain.agents import CalculationResult, FinancialFilters
from app.services.agents.validation import check_financial_numbers
from app.services.financial_chat_service import query_finances


@pytest.fixture
def query_library(request):
    return request.getfixturevalue("financial_library")


def test_ano_inteiro_nao_vira_resumo_de_todos_os_anos(query_library):
    result = query_finances(
        "Quanto gastei em 2025?", "summary", FinancialFilters(), query_library, HOJE
    )
    assert not result.calculations
    assert result.clarification is not None


def test_filtro_nao_pode_apagar_periodo_nao_suportado_do_texto(query_library):
    result = query_finances(
        "Quanto gastei na semana passada?",
        "summary",
        FinancialFilters(period="2026-10"),
        query_library,
        HOJE,
    )
    assert not result.calculations
    assert result.clarification is not None


def test_rotulo_do_resultado_identifica_conta_explicitamente_selecionada(query_library):
    result = query_finances(
        "Quanto gastei?", "summary", FinancialFilters(account_id=CC), query_library, HOJE
    )
    assert result.calculations
    assert all("Nubank" in c.label for c in result.calculations)
    assert all("todas as contas" not in c.label for c in result.calculations)


@pytest.mark.parametrize(
    "draft",
    [
        "Seu saldo é R$ - 100,00.",
        "Seu saldo é −100 BRL.",
        "Seu saldo é US$ 100.",
        "Seu saldo é R$ 2027-01.",
        "Seu saldo é R$ 1230.",
        "Seu saldo é 99.99.9 BRL.",
    ],
)
def test_metadados_moeda_e_sinal_nao_autorizam_numero_inventado(draft):
    calculations = [
        CalculationResult(
            key="balance", label="Saldo da loja 123", value=100, unit="BRL", source="Sistema"
        ),
        CalculationResult(key="zero", label="Sem movimento", value=0, unit="BRL", source="Sistema"),
        CalculationResult(key="end", label="Termina em", value="2027-01", source="Sistema"),
    ]
    assert check_financial_numbers(draft, calculations, []), draft


@pytest.mark.parametrize("draft", ["R$ 100 USD", "US$ 100 BRL", "R$ 100%"])
def test_prefixo_e_unidade_divergentes_sao_bloqueados(draft):
    assert check_financial_numbers(
        draft,
        [
            CalculationResult(
                key="value",
                label="Valor",
                value=100,
                unit="BRL",
                source="Sistema",
            )
        ],
        [],
    )


@pytest.mark.parametrize(
    "draft",
    [
        "R$ - 100,00.",
        "−100 BRL.",
        "-R$100,00.",
        "-100 brl.",
    ],
)
def test_variantes_de_valor_negativo_legitimo_sao_aceitas(draft):
    assert not check_financial_numbers(
        draft,
        [
            CalculationResult(
                key="balance",
                label="Saldo",
                value=-100,
                unit="BRL",
                source="Sistema",
            )
        ],
        [],
    )


def test_data_e_prazo_legitimos_nao_viram_moeda():
    calculations = [
        CalculationResult(
            key="end",
            label="Última parcela em",
            value="2027-01",
            source="Sistema",
        )
    ]
    assert not check_financial_numbers(
        "Última parcela em 2027-01. Vencimentos nos próximos 30 dias.",
        calculations,
        ["Vencimentos nos próximos 30 dias."],
    )


@pytest.mark.parametrize(
    "question",
    [
        "Quanto gastei em novembro de 2026 na Loja Desconhecida?",
        "Quanto gastei na minha loja desconhecida em novembro de 2026?",
        "Meus gastos no Restaurante Desconhecido em novembro de 2026?",
    ],
)
def test_complemento_desconhecido_nao_e_ignorado_apos_periodo(question, query_library):
    result = query_finances(question, "summary", FinancialFilters(), query_library, HOJE)
    assert not result.calculations
    assert result.clarification is not None


def test_estabelecimento_conhecido_nao_oculta_outro_desconhecido(query_library):
    result = query_finances(
        "Quanto gastei no Mercado Z e no Restaurante Desconhecido em novembro de 2026?",
        "summary",
        FinancialFilters(),
        query_library,
        HOJE,
    )
    assert result.clarification is not None
    assert not result.calculations


def test_nome_de_loja_igual_a_intencao_nao_altera_o_resumo(query_library):
    query_library.transactions.append(
        query_library.transactions[0].model_copy(
            update={
                "id": "colisao-sintetica",
                "merchant": "Saldo",
            }
        )
    )
    result = query_finances("Qual meu saldo?", "summary", FinancialFilters(), query_library, HOJE)
    assert {c.key for c in result.calculations} == {"total_income", "total_expenses", "net_balance"}
