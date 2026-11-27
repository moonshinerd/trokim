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
from app.services.statement_profiles import doc_is_company, normalize_text

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


def payee_matches(a: str | None, b: str | None) -> bool:
    """Mesmo favorecido em dois lançamentos: ``name_matches`` ou um nome contido no outro."""
    if not a or not b:
        return False
    na, nb = normalize_text(a), normalize_text(b)
    return (
        na == nb or name_matches(a, b) or (len(na) >= 4 and na in nb) or (len(nb) >= 4 and nb in na)
    )


def matches_identity(tx: Transaction, identities: list[Identity]) -> bool:
    if tx.nature not in {TransactionNature.PIX_OUT, TransactionNature.PIX_IN}:
        return False
    for identity in identities:
        doc_equal = bool(
            identity.doc and tx.counterparty_doc and identity.doc == tx.counterparty_doc
        )
        name_equal = name_matches(tx.merchant, identity.name_norm)
        is_company_doc = doc_is_company(identity.doc)
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


_PAYMENT_WINDOW_DAYS = 3


def _is_card_account(library: Library, tx: Transaction) -> bool:
    account = library.accounts.get(tx.account_id)
    return account is not None and account.kind == AccountKind.CARD


class TransferService:
    @staticmethod
    def suggestions(library: Library) -> list[dict[str, object]]:
        """Pares saída × entrada em contas diferentes.

        Dois tipos: ``transferencia`` (entre contas do usuário, até 1 dia de diferença) e
        ``pagamento_fatura`` (a saída de uma conta paga o cartão de outro banco: a entrada é o
        "pagamento recebido" da fatura, até 3 dias de diferença).
        """
        txs = [t for t in library.transactions if _eligible(t)]
        debits = [
            t for t in txs if t.type == TransactionType.DEBIT and not _is_card_account(library, t)
        ]
        transfer_credits = [t for t in txs if t.type == TransactionType.CREDIT]
        payment_credits = [
            t
            for t in library.transactions
            if not t.is_duplicate
            and t.type == TransactionType.CREDIT
            and t.nature == TransactionNature.CARD_PAYMENT
            and _is_card_account(library, t)
        ]
        by_amount: dict[tuple[str, float], list[Transaction]] = defaultdict(list)
        for credit in transfer_credits:
            by_amount[("transferencia", round(credit.amount, 2))].append(credit)
        for credit in payment_credits:
            by_amount[("pagamento_fatura", round(credit.amount, 2))].append(credit)
        windows = {"transferencia": 1, "pagamento_fatura": _PAYMENT_WINDOW_DAYS}

        candidates: dict[str, list[tuple[str, Transaction]]] = {}
        reverse: dict[str, list[Transaction]] = defaultdict(list)
        for debit in debits:
            options: list[tuple[str, Transaction]] = []
            for kind, window in windows.items():
                for c in by_amount.get((kind, round(debit.amount, 2)), []):
                    pid = pair_id(debit.uid, c.uid)
                    if (
                        c.account_id != debit.account_id
                        and abs((debit.date - c.date).days) <= window
                        and pid not in library.rejected_pairs
                        and pid not in library.confirmed
                    ):
                        options.append((kind, c))
            if options:
                candidates[debit.uid] = options
                for _, option in options:
                    reverse[option.uid].append(debit)

        result: list[dict[str, object]] = []
        for debit in debits:
            for kind, credit in candidates.get(debit.uid, []):
                unique = len(candidates[debit.uid]) == 1 and len(reverse[credit.uid]) == 1
                same_day = debit.date == credit.date
                if kind == "pagamento_fatura":
                    reason = (
                        "O valor bate com o pagamento da fatura do cartão, saindo desta conta."
                        if unique
                        else "Há mais de uma combinação possível para este valor."
                    )
                elif unique and same_day:
                    reason = "Mesmo valor e mesma data, saída numa conta e entrada na outra."
                elif unique:
                    reason = "Mesmo valor em contas diferentes com até 1 dia de diferença."
                else:
                    reason = "Há mais de uma combinação possível para este valor."
                result.append(
                    {
                        "id": pair_id(debit.uid, credit.uid),
                        "kind": kind,
                        "debit_uid": debit.uid,
                        "credit_uid": credit.uid,
                        "amount": round(debit.amount, 2),
                        "debit_date": debit.date.isoformat(),
                        "credit_date": credit.date.isoformat(),
                        "from_account": debit.account_id,
                        "to_account": credit.account_id,
                        "confidence": "alta" if unique else "media",
                        "reason": reason,
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
        library.own_reasons.clear()

        def mark(
            tx: Transaction, nature: TransactionNature = TransactionNature.INTERNAL_TRANSFER
        ) -> None:
            if tx.uid not in library.own_marks:
                library.own_marks[tx.uid] = (tx.nature, tx.category)
            tx.nature = nature
            tx.category = TransactionCategory.OTHER

        paired: set[str] = set()
        for transfer in library.confirmed.values():
            if transfer.kind == "pagamento_fatura":
                # A entrada já é o "pagamento recebido" do cartão; só a saída muda.
                debit = by_uid.get(transfer.debit_uid)
                if debit:
                    mark(debit, TransactionNature.CARD_PAYMENT)
                    paired.add(transfer.debit_uid)
                paired.add(transfer.credit_uid)
                continue
            for uid in (transfer.debit_uid, transfer.credit_uid):
                tx = by_uid.get(uid)
                if tx:
                    mark(tx)
                    paired.add(uid)
        identities = library.identities()
        extra = 0
        linked: list[tuple[Transaction, str]] = []
        for tx in library.transactions:
            if tx.uid in paired or tx.is_duplicate or tx.uid in library.not_own:
                continue
            is_pix = tx.nature in {TransactionNature.PIX_OUT, TransactionNature.PIX_IN}
            other = linked_account(library, tx) if is_pix else None
            if other is not None:
                mark(tx)
                library.own_reasons[tx.uid] = ("conta_destino", other.id)
                linked.append((tx, other.id))
                extra += 1
            elif matches_identity(tx, identities):
                mark(tx)
                extra += 1
        # Um banco que não mostra a conta da contraparte (como o BB) só é ligado pela outra
        # ponta: a saída/entrada de mesmo valor, até 1 dia de diferença, na conta citada.
        for tx, other_id in linked:
            wanted = (
                TransactionType.CREDIT
                if tx.type == TransactionType.DEBIT
                else TransactionType.DEBIT
            )
            options = [
                c
                for c in library.transactions
                if c.account_id == other_id
                and c.type == wanted
                and not c.is_duplicate
                and c.uid not in library.not_own
                and c.uid not in library.own_marks
                and c.uid not in paired
                and c.nature in _MOVEMENT_NATURES
                and round(c.amount, 2) == round(tx.amount, 2)
                and abs((c.date - tx.date).days) <= 1
            ]
            if len(options) == 1:
                mark(options[0])
                library.own_reasons[options[0].uid] = ("contraparte", tx.account_id)
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
        is_payment = credit.nature == TransactionNature.CARD_PAYMENT and _is_card_account(
            library, credit
        )
        identities: list[Identity] = []
        if not is_payment:
            # O destino da saída é dono da conta que recebeu, e a origem da entrada é dono da
            # conta que enviou: ambos são "você".
            for tx in (debit, credit):
                if tx.merchant and len(normalize_text(tx.merchant)) >= _MIN_NAME:
                    identities.append(Identity(normalize_text(tx.merchant), tx.counterparty_doc))
        library.confirmed[pid] = ConfirmedTransfer(
            debit_uid,
            credit_uid,
            identities,
            kind="pagamento_fatura" if is_payment else "transferencia",
        )
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
        # A outra ponta da mesma transferência automática também deixa de contar como própria.
        for tx, partner, _code, _other in TransferService._automatic_pairs(library):
            if partner is not None and uid in (tx.uid, partner.uid):
                library.not_own.update({tx.uid, partner.uid})
        # Se fazia parte de um par confirmado, o par inteiro é desfeito.
        for pid, transfer in list(library.confirmed.items()):
            if uid in (transfer.debit_uid, transfer.credit_uid):
                del library.confirmed[pid]
        return TransferService.recompute(library)

    @staticmethod
    def _automatic_pairs(
        library: Library,
    ) -> list[tuple[Transaction, Transaction | None, str, str]]:
        """Agrupa as pontas de uma mesma transferência marcada sozinha.

        Quando as duas contas mostram a conta da contraparte (Nubank com Nubank), cada ponta é
        ligada por conta própria; sem agrupar, a mesma transferência apareceria duas vezes.
        Devolve ``(ponta, outra ponta ou None, motivo, conta ligada)``, com a saída primeiro.
        """
        marked = [
            tx
            for tx in library.transactions
            if tx.uid in library.own_reasons and not tx.is_duplicate
        ]
        # Saídas antes das entradas: o item fica com o id da saída quando houver as duas.
        marked.sort(key=lambda tx: tx.type != TransactionType.DEBIT)
        used: set[str] = set()
        pairs: list[tuple[Transaction, Transaction | None, str, str]] = []
        for tx in marked:
            if tx.uid in used:
                continue
            used.add(tx.uid)
            code, other_id = library.own_reasons[tx.uid]
            partner = next(
                (
                    c
                    for c in marked
                    if c.uid not in used
                    and c.account_id == other_id
                    and c.type != tx.type
                    and library.own_reasons[c.uid][1] == tx.account_id
                    and round(c.amount, 2) == round(tx.amount, 2)
                    and abs((c.date - tx.date).days) <= 1
                ),
                None,
            )
            if partner is not None:
                used.add(partner.uid)
            pairs.append((tx, partner, code, other_id))
        return pairs

    @staticmethod
    def automatic_list(library: Library) -> list[dict[str, object]]:
        """Transferências entre contas próprias marcadas sozinhas (uma por par de pontas)."""
        items: list[dict[str, object]] = []
        for tx, partner, code, other_id in TransferService._automatic_pairs(library):
            outgoing = tx.type == TransactionType.DEBIT
            items.append(
                {
                    "id": tx.uid,
                    "kind": "automatica",
                    "amount": round(tx.amount, 2),
                    "date": tx.date.isoformat(),
                    "from_account": tx.account_id if outgoing else other_id,
                    "to_account": other_id if outgoing else tx.account_id,
                    "both_sides": partner is not None,
                    "reason": (
                        "A conta de destino é uma conta sua que você importou."
                        if code == "conta_destino" or partner is not None
                        else "É a outra ponta de uma transferência ligada pela conta de destino."
                    ),
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
                    "transfer_kind": transfer.kind,
                    "amount": round(debit.amount, 2),
                    "debit_date": debit.date.isoformat(),
                    "credit_date": credit.date.isoformat(),
                    "from_account": debit.account_id,
                    "to_account": credit.account_id,
                }
            )
        return items
