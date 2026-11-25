import math
import re
import time
import unicodedata

from app.domain.agents import (
    AgentContext,
    AgentName,
    AgentStep,
    CalculationResult,
    StepStatus,
)
from app.domain.models import TransactionOrigin
from app.services.calculation_service import CalculationService


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_br_number(raw: str) -> float | None:
    """Converte representações numéricas em pt-BR (ex.: '6.000,50', '500', '12,5') para float."""
    clean = raw.strip().replace("R$", "").strip()
    if not clean:
        return None
    # Trata notação milhar brasileira com ponto e decimal com vírgula
    if "." in clean and "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    elif "." in clean:
        # Verifica se é milhar puro ex: 6.000
        parts = clean.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            clean = parts[0] + parts[1]
    try:
        val = float(clean)
        return val if not math.isnan(val) and not math.isinf(val) else None
    except ValueError:
        return None


def extract_goal_and_monthly(text: str) -> tuple[float | None, float | None]:
    """Extrai valor da meta (objetivo) e aporte mensal a partir do texto em linguagem natural."""
    normalized = _strip_accents(text.lower())

    goal: float | None = None
    monthly: float | None = None

    # Padrão específico para objetivo/meta
    goal_match = re.search(
        r"(?:juntar|acumular|meta(?:\s+de)?|guardar|ter|alcancar|poupar)\s*(?:r\$\s*)?([\d\.\,]+(?:\s*mil)?)",
        normalized,
    )
    if goal_match:
        raw_val = goal_match.group(1)
        if "mil" in raw_val:
            base_num = _parse_br_number(raw_val.replace("mil", ""))
            goal = (base_num * 1000.0) if base_num is not None else None
        else:
            goal = _parse_br_number(raw_val)

    # Padrão específico para aporte mensal
    monthly_match = re.search(
        r"(?:poupando|guardando|aporte(?:\s+de)?|economizando|por\s+mes|mensal(?:mente)?)\s*(?:de\s*)?(?:r\$\s*)?([\d\.\,]+)",
        normalized,
    )
    if monthly_match:
        monthly = _parse_br_number(monthly_match.group(1))

    # Fallback se ambos não foram capturados por palavras-chave: busca valores em R$ ou numéricos
    if goal is None or monthly is None:
        money_matches = re.findall(r"r\$\s*([\d\.\,]+)", normalized)
        parsed_money = [
            p for p in (_parse_br_number(m) for m in money_matches) if p is not None and p > 0
        ]
        if len(parsed_money) >= 2:
            larger = max(parsed_money)
            smaller = min(parsed_money)
            if goal is None:
                goal = larger
            if monthly is None:
                monthly = smaller

    return goal, monthly


class AnalysisAgent:
    """Agente puramente determinístico para cálculos financeiros auditáveis (ADR 0004)."""

    def __init__(self) -> None:
        self.name = AgentName.ANALYSIS

    async def run(self, ctx: AgentContext) -> AgentStep:
        t0 = time.perf_counter()
        normalized_q = _strip_accents(ctx.question.lower())

        intents: list[str] = []
        has_summary_intent = any(
            kw in normalized_q
            for kw in (
                "saldo",
                "receita",
                "despesa",
                "gastei",
                "gasto",
                "resumo",
                "balanco",
                "total",
                "poupanca",
                "poupança",
            )
        )
        has_category_intent = any(
            kw in normalized_q
            for kw in (
                "categoria",
                "alimentacao",
                "moradia",
                "transporte",
                "saude",
                "lazer",
                "educacao",
                "servicos",
            )
        )
        has_goal_intent = any(
            kw in normalized_q
            for kw in (
                "meta",
                "juntar",
                "meses",
                "tempo",
                "objetivo",
                "poupando",
                "quanto tempo",
            )
        )

        has_transactions = len(ctx.transactions) > 0

        # 1. Processamento de Resumo e Categorias sobre transações
        if has_summary_intent or has_category_intent:
            if not has_transactions:
                ctx.assumptions.append(
                    "Nenhum lançamento foi importado para calcular o resumo financeiro."
                )
            else:
                summary = CalculationService.calculate_summary(ctx.transactions)
                ctx.assumptions.append(
                    "Cálculos baseados em lançamentos importados, sem duplicatas."
                )
                from_documents = sum(
                    1
                    for t in ctx.transactions
                    if t.origin == TransactionOrigin.DOCUMENT and not t.is_duplicate
                )
                if from_documents:
                    ctx.assumptions.append(
                        f"{from_documents} lançamento(s) vieram de documentos que você enviou "
                        "por foto ou PDF e confirmou depois de revisar."
                    )

                if has_summary_intent:
                    intents.append("resumo")
                    ctx.calculations.extend(
                        [
                            CalculationResult(
                                key="total_income",
                                label="Receita total",
                                value=summary.total_income,
                                unit="BRL",
                                source="CalculationService.calculate_summary",
                            ),
                            CalculationResult(
                                key="total_expenses",
                                label="Despesa total",
                                value=summary.total_expenses,
                                unit="BRL",
                                source="CalculationService.calculate_summary",
                            ),
                            CalculationResult(
                                key="net_balance",
                                label="Saldo líquido",
                                value=summary.net_balance,
                                unit="BRL",
                                source="CalculationService.calculate_summary",
                            ),
                            CalculationResult(
                                key="savings_rate",
                                label="Taxa de poupança",
                                value=summary.savings_rate,
                                unit="%",
                                source="CalculationService.calculate_summary",
                            ),
                            CalculationResult(
                                key="transaction_count",
                                label="Lançamentos analisados",
                                value=summary.transaction_count,
                                unit="lançamentos",
                                source="CalculationService.calculate_summary",
                            ),
                        ]
                    )

                if has_category_intent:
                    intents.append("categorias")
                    shares = CalculationService.category_shares(summary)
                    for cat, amount in sorted(summary.expenses_by_category.items()):
                        ctx.calculations.append(
                            CalculationResult(
                                key=f"expense_{cat}",
                                label=f"Despesa em {cat.title()}",
                                value=amount,
                                unit="BRL",
                                source="CalculationService.calculate_summary",
                            )
                        )
                        ctx.calculations.append(
                            CalculationResult(
                                key=f"share_{cat}",
                                label=f"Participação de {cat.title()}",
                                value=shares.get(cat, 0.0),
                                unit="%",
                                source="CalculationService.category_shares",
                            )
                        )

        # 2. Processamento de Meta Financeira
        if has_goal_intent:
            goal, monthly = extract_goal_and_monthly(ctx.question)
            if goal is not None and monthly is not None and monthly > 0:
                intents.append("meta")
                months = CalculationService.months_to_goal(goal, monthly)
                ctx.calculations.extend(
                    [
                        CalculationResult(
                            key="target_amount",
                            label="Valor da meta",
                            value=round(goal, 2),
                            unit="BRL",
                            source="CalculationService.months_to_goal",
                        ),
                        CalculationResult(
                            key="monthly_savings",
                            label="Aporte mensal",
                            value=round(monthly, 2),
                            unit="BRL",
                            source="CalculationService.months_to_goal",
                        ),
                        CalculationResult(
                            key="months_to_goal",
                            label="Meses necessários",
                            value=months,
                            unit="meses",
                            source="CalculationService.months_to_goal",
                        ),
                    ]
                )
                ctx.assumptions.append(
                    f"Meta de R$ {goal:,.2f} com aportes mensais de R$ {monthly:,.2f}."
                )
            elif monthly is not None and monthly <= 0:
                ctx.assumptions.append("O aporte mensal informado deve ser estritamente positivo.")
            else:
                ctx.assumptions.append(
                    "Para estimar a meta, informe o valor total e o aporte mensal."
                )

        duration = max(1, int(round((time.perf_counter() - t0) * 1000)))

        # Se nenhum cálculo pôde ser realizado
        if not ctx.calculations:
            return AgentStep(
                agent=self.name,
                status=StepStatus.SKIPPED,
                summary="Sem dados suficientes ou lançamentos importados para calcular valores.",
                duration_ms=duration,
                detail={"reason": "sem_calculos", "intents": intents},
            )

        return AgentStep(
            agent=self.name,
            status=StepStatus.OK,
            summary=f"Cálculos determinísticos concluídos ({len(ctx.calculations)} itens).",
            duration_ms=duration,
            detail={"calculations_count": len(ctx.calculations), "intents": intents},
        )
