"""Controle de parcelamentos do cartão: o que já foi pago, o que falta e a projeção mensal."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from app.domain.models import Transaction, TransactionType
from app.services.statement_profiles import normalize_text


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


class InstallmentService:
    @staticmethod
    def build(transactions: Sequence[Transaction]) -> dict[str, object]:
        """Agrupa as parcelas de uma mesma compra, mesmo vistas em faturas diferentes."""
        groups: dict[tuple, list[Transaction]] = defaultdict(list)
        for tx in transactions:
            if (
                tx.is_duplicate
                or tx.type != TransactionType.DEBIT
                or not tx.installment_total
                or not tx.installment_number
                or tx.installment_number > tx.installment_total
            ):
                continue
            merchant = normalize_text(tx.merchant or tx.description)
            groups[(tx.account_id, merchant, tx.installment_total)].append(tx)

        plans: list[dict[str, object]] = []
        for (account_id, _merchant, total), items in groups.items():
            # Parcelas com valores bem diferentes são compras diferentes na mesma loja.
            clusters: list[list[Transaction]] = []
            for tx in sorted(items, key=lambda t: (t.amount, t.date)):
                for cluster in clusters:
                    ref = cluster[0].amount
                    if abs(tx.amount - ref) <= max(0.05, ref * 0.02):
                        cluster.append(tx)
                        break
                else:
                    clusters.append([tx])
            for cluster in clusters:
                # O mesmo número de parcela visto duas vezes (arquivo reenviado) conta uma só.
                by_number: dict[int, Transaction] = {}
                for tx in cluster:
                    by_number.setdefault(tx.installment_number or 0, tx)
                current = max(by_number)
                latest = by_number[current]
                amount = round(sum(t.amount for t in by_number.values()) / len(by_number), 2)
                remaining = total - current
                last_month = _add_months(latest.date, 0)
                plans.append(
                    {
                        "account_id": account_id,
                        "merchant": latest.merchant or latest.description,
                        "amount": amount,
                        "total": total,
                        "current": current,
                        "paid": len(by_number),
                        "remaining": remaining,
                        "remaining_amount": round(remaining * amount, 2),
                        "last_seen": latest.date.isoformat(),
                        "ends_on_month": _add_months(last_month, remaining).strftime("%Y-%m"),
                        "finished": remaining == 0,
                    }
                )

        plans.sort(key=lambda p: (p["finished"], -float(p["remaining_amount"])))  # type: ignore[arg-type]
        projection: dict[str, float] = defaultdict(float)
        for plan in plans:
            if plan["finished"]:
                continue
            last = date.fromisoformat(str(plan["last_seen"]))
            for k in range(1, int(plan["remaining"]) + 1):  # type: ignore[call-overload]
                projection[_add_months(last, k).strftime("%Y-%m")] += float(plan["amount"])  # type: ignore[arg-type]
        active = [p for p in plans if not p["finished"]]
        return {
            "plans": plans,
            "active_count": len(active),
            "finished_count": len(plans) - len(active),
            "total_remaining": round(sum(float(p["remaining_amount"]) for p in active), 2),  # type: ignore[arg-type]
            "monthly_projection": [
                {"month": month, "total": round(total, 2)}
                for month, total in sorted(projection.items())
            ],
        }
