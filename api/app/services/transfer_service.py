"""Transferências entre as próprias contas do usuário (PF↔PJ e entre bancos).

O mesmo dinheiro aparece como saída numa conta e entrada noutra. Sem tratar isso, as duas pontas
inflam despesas e receitas. O pareamento usa valor, data (até 1 dia de diferença) e direções
opostas em contas diferentes; o nome da contraparte vem truncado de formas diferentes em cada
banco e serve só de reforço. Nada é excluído dos totais sem o usuário confirmar, exceto
identidades que ele já confirmou antes.
"""

import hashlib
import re
from collections import defaultdict

from app.domain.models import (
    AccountKind,
    Transaction,
    TransactionCategory,
    TransactionNature,
    TransactionType,
)
from app.services.library_service import ConfirmedTransfer, Identity, Library
from app.services.statement_profiles import normalize_text

_MOVEMENT_NATURES = {TransactionNature.PIX_OUT, TransactionNature.PIX_IN, TransactionNature.OTHER}
_MIN_NAME = 8


def pair_id(debit_uid: str, credit_uid: str) -> str:
    return hashlib.sha1(f"{debit_uid}>{credit_uid}".encode()).hexdigest()[:12]


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", name) if len(t) > 1}


def name_matches(a: str | None, b: str | None) -> bool:
    """Nomes iguais, truncados (um começa com o outro) ou com as mesmas palavras."""
    if not a or not b:
        return False
    na, nb = normalize_text(a), normalize_text(b)
    if len(na) < _MIN_NAME or len(nb) < _MIN_NAME:
        return False
    if na == nb:
        return True
    shorter, longer = sorted((na, nb), key=len)
    if len(shorter) >= 10 and longer.startswith(shorter):
        return True
    ta, tb = _tokens(na), _tokens(nb)
    return len(ta) >= 2 and len(tb) >= 2 and (ta <= tb or tb <= ta)


def matches_identity(tx: Transaction, identities: list[Identity]) -> bool:
    if tx.nature not in {TransactionNature.PIX_OUT, TransactionNature.PIX_IN}:
        return False
    for identity in identities:
        doc_equal = bool(
            identity.doc and tx.counterparty_doc and identity.doc == tx.counterparty_doc
        )
        name_equal = name_matches(tx.merchant, identity.name_norm)
        is_company_doc = bool(identity.doc and "/" in identity.doc)
        if doc_equal and (is_company_doc or name_equal):
            return True
        if not identity.doc and name_equal:
            return True
    return False


def linked_account(library: Library, tx: Transaction):
    """Conta importada pelo usuário que é o destino (ou a origem) deste Pix, se houver.

    O OFX do Nubank mostra a conta da contraparte no texto do Pix. Quando ela é igual ao número
    de uma conta que o usuário também importou, a ligação é certa: é dinheiro entre contas dele.
    """
    if not tx.counterparty_account:
        return None
    for account in library.accounts.values():
        if (
            account.id != tx.account_id
            and account.kind != AccountKind.CARD
            and account.link_key == tx.counterparty_account
        ):
            return account
    return None


def _eligible(tx: Transaction) -> bool:
    return not tx.is_duplicate and tx.nature in _MOVEMENT_NATURES


class TransferService:
    @staticmethod
    def suggestions(library: Library) -> list[dict[str, object]]:
        txs = [t for t in library.transactions if _eligible(t)]
        debits = [t for t in txs if t.type == TransactionType.DEBIT]
        credits = [t for t in txs if t.type == TransactionType.CREDIT]
        by_amount: dict[float, list[Transaction]] = defaultdict(list)
        for credit in credits:
            by_amount[round(credit.amount, 2)].append(credit)

        candidates: dict[str, list[Transaction]] = {}
        reverse: dict[str, list[Transaction]] = defaultdict(list)
        for debit in debits:
            options = [
                c
                for c in by_amount.get(round(debit.amount, 2), [])
                if c.account_id != debit.account_id
                and abs((debit.date - c.date).days) <= 1
                and pair_id(debit.uid, c.uid) not in library.rejected_pairs
                and pair_id(debit.uid, c.uid) not in library.confirmed
            ]
            if options:
                candidates[debit.uid] = options
                for option in options:
                    reverse[option.uid].append(debit)

        result: list[dict[str, object]] = []
        for debit in debits:
            for credit in candidates.get(debit.uid, []):
                unique = len(candidates[debit.uid]) == 1 and len(reverse[credit.uid]) == 1
                same_day = debit.date == credit.date
                result.append(
                    {
                        "id": pair_id(debit.uid, credit.uid),
                        "debit_uid": debit.uid,
                        "credit_uid": credit.uid,
                        "amount": round(debit.amount, 2),
                        "debit_date": debit.date.isoformat(),
                        "credit_date": credit.date.isoformat(),
                        "from_account": debit.account_id,
                        "to_account": credit.account_id,
                        "confidence": "alta" if unique else "media",
                        "reason": (
                            "Mesmo valor e mesma data, saída numa conta e entrada na outra."
                            if unique and same_day
                            else "Mesmo valor em contas diferentes com até 1 dia de diferença."
                            if unique
                            else "Há mais de uma combinação possível para este valor."
                        ),
                    }
                )
        result.sort(key=lambda s: (s["confidence"] != "alta", str(s["debit_date"])))
        return result

    @staticmethod
    def _by_uid(library: Library) -> dict[str, Transaction]:
        return {tx.uid: tx for tx in library.transactions}

    @staticmethod
    def recompute(library: Library) -> int:
        """Reaplica as marcações de transferência própria a partir das decisões do usuário.

        Devolve quantos lançamentos além dos pares confirmados foram marcados por identidade.
        """
        by_uid = TransferService._by_uid(library)
        for uid, (nature, category) in list(library.own_marks.items()):
            tx = by_uid.get(uid)
            if tx:
                tx.nature, tx.category = nature, category
        library.own_marks.clear()

        def mark(tx: Transaction) -> None:
            if tx.uid not in library.own_marks:
                library.own_marks[tx.uid] = (tx.nature, tx.category)
            tx.nature = TransactionNature.INTERNAL_TRANSFER
            tx.category = TransactionCategory.OTHER

        paired: set[str] = set()
        for transfer in library.confirmed.values():
            for uid in (transfer.debit_uid, transfer.credit_uid):
                tx = by_uid.get(uid)
                if tx:
                    mark(tx)
                    paired.add(uid)
        identities = library.identities()
        extra = 0
        for tx in library.transactions:
            if tx.uid in paired or tx.is_duplicate or tx.uid in library.not_own:
                continue
            is_pix = tx.nature in {TransactionNature.PIX_OUT, TransactionNature.PIX_IN}
            if (is_pix and linked_account(library, tx) is not None) or matches_identity(
                tx, identities
            ):
                mark(tx)
                extra += 1
        return extra

    @staticmethod
    def confirm(library: Library, debit_uid: str, credit_uid: str) -> dict[str, object]:
        by_uid = TransferService._by_uid(library)
        debit, credit = by_uid.get(debit_uid), by_uid.get(credit_uid)
        if debit is None or credit is None:
            raise LookupError("Lançamento não encontrado.")
        if debit.type != TransactionType.DEBIT or credit.type != TransactionType.CREDIT:
            raise ValueError("Informe a saída e a entrada da transferência.")
        if debit.account_id == credit.account_id:
            raise ValueError("A saída e a entrada precisam ser de contas diferentes.")
        pid = pair_id(debit_uid, credit_uid)
        identities: list[Identity] = []
        # O destino da saída é dono da conta que recebeu, e a origem da entrada é dono da
        # conta que enviou: ambos são "você".
        for tx in (debit, credit):
            if tx.merchant and len(normalize_text(tx.merchant)) >= _MIN_NAME:
                identities.append(Identity(normalize_text(tx.merchant), tx.counterparty_doc))
        library.confirmed[pid] = ConfirmedTransfer(debit_uid, credit_uid, identities)
        library.rejected_pairs.discard(pid)
        auto = TransferService.recompute(library)
        return {"id": pid, "auto_marked": auto, "learned": len(identities)}

    @staticmethod
    def reject(library: Library, debit_uid: str, credit_uid: str) -> str:
        pid = pair_id(debit_uid, credit_uid)
        library.rejected_pairs.add(pid)
        return pid

    @staticmethod
    def undo(library: Library, pid: str) -> int:
        if pid not in library.confirmed:
            raise LookupError("Transferência não encontrada.")
        del library.confirmed[pid]
        return TransferService.recompute(library)

    @staticmethod
    def unmark(library: Library, uid: str) -> int:
        """O usuário diz que um lançamento marcado automaticamente não é transferência própria."""
        if uid not in TransferService._by_uid(library):
            raise LookupError("Lançamento não encontrado.")
        library.not_own.add(uid)
        # Se fazia parte de um par confirmado, o par inteiro é desfeito.
        for pid, transfer in list(library.confirmed.items()):
            if uid in (transfer.debit_uid, transfer.credit_uid):
                del library.confirmed[pid]
        return TransferService.recompute(library)

    @staticmethod
    def automatic_list(library: Library) -> list[dict[str, object]]:
        """Pix marcados sozinhos porque a conta de destino é outra conta do usuário."""
        confirmed_uids = {
            uid for t in library.confirmed.values() for uid in (t.debit_uid, t.credit_uid)
        }
        items: list[dict[str, object]] = []
        for tx in library.transactions:
            if tx.uid in confirmed_uids or tx.uid not in library.own_marks or tx.is_duplicate:
                continue
            other = linked_account(library, tx)
            if other is None:
                continue
            outgoing = tx.type == TransactionType.DEBIT
            items.append(
                {
                    "id": tx.uid,
                    "kind": "automatica",
                    "amount": round(tx.amount, 2),
                    "date": tx.date.isoformat(),
                    "from_account": tx.account_id if outgoing else other.id,
                    "to_account": other.id if outgoing else tx.account_id,
                    "reason": "A conta de destino é uma conta sua que você importou.",
                }
            )
        return items

    @staticmethod
    def confirmed_list(library: Library) -> list[dict[str, object]]:
        by_uid = TransferService._by_uid(library)
        items: list[dict[str, object]] = []
        for pid, transfer in library.confirmed.items():
            debit, credit = by_uid.get(transfer.debit_uid), by_uid.get(transfer.credit_uid)
            if not debit or not credit:
                continue
            items.append(
                {
                    "id": pid,
                    "kind": "confirmada",
                    "amount": round(debit.amount, 2),
                    "debit_date": debit.date.isoformat(),
                    "credit_date": credit.date.isoformat(),
                    "from_account": debit.account_id,
                    "to_account": credit.account_id,
                }
            )
        return items
