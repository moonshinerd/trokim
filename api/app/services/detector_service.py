"""Detector de arquivo no lugar errado: conta pessoal × Empresas e conta × cartão.

O OFX do Nubank não diz se a conta é pessoal ou Empresas, então o detector junta sinais, do mais
forte para o mais fraco:

1. **Cadastro:** a conta (banco + número) já foi importada com um dono.
2. **Documentos de outros arquivos:** os Pix de outras contas citam o número desta conta junto do
   documento do titular (CNPJ = empresa, CPF = pessoa).
3. **Pagamento da fatura:** o pagamento de um cartão sai de uma conta específica, e a conta e o
   cartão são do mesmo dono.
4. **Nome do arquivo:** o Nubank usa padrões diferentes para conta pessoal e Empresas.

Também avisa se o tipo do arquivo (conta ou cartão) difere do que o usuário escolheu e se os
lançamentos já foram importados em outra conta.
"""

import re
from dataclasses import dataclass
from datetime import date

from app.domain.models import AccountKind, AccountOwner, Transaction, TransactionNature
from app.services.library_service import Library
from app.services.parser_service import OfxParseResult
from app.services.statement_service import account_key, infer_status

_PF_NOME = re.compile(r"^NU_\d+_\d{2}[A-Z]{3}\d{4}_\d{2}[A-Z]{3}\d{4}\.ofx$", re.IGNORECASE)
_PJ_NOME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.ofx$",
    re.IGNORECASE,
)
_STRENGTH = {"alta": 3, "media": 2, "baixa": 1}


@dataclass(frozen=True)
class Signal:
    owner: AccountOwner
    source: str
    label: str
    strength: str  # alta | media | baixa


def _digits(raw: str | None) -> str:
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def _owner_text(owner: AccountOwner) -> str:
    return "Nubank Empresas" if owner == AccountOwner.BUSINESS else "conta pessoal"


def _holder_signal(library: Library, link_key: str | None) -> Signal | None:
    """Documento do titular desta conta, como aparece nos Pix de outros arquivos."""
    if not link_key:
        return None
    kinds: set[AccountOwner] = set()
    for tx in library.transactions:
        if tx.counterparty_account != link_key or not tx.counterparty_doc:
            continue
        kinds.add(AccountOwner.BUSINESS if "/" in tx.counterparty_doc else AccountOwner.PERSONAL)
    if len(kinds) != 1:
        return None
    owner = next(iter(kinds))
    return Signal(
        owner,
        "documentos",
        "Outros arquivos seus citam esta conta com "
        + ("CNPJ" if owner == AccountOwner.BUSINESS else "CPF"),
        "alta",
    )


def _filename_signal(filename: str, kind: AccountKind | None) -> Signal | None:
    if kind != AccountKind.CHECKING:
        return None  # as faturas dos dois tipos têm o mesmo padrão de nome
    if _PJ_NOME.match(filename):
        return Signal(
            AccountOwner.BUSINESS, "nome_do_arquivo", "Nome no padrão do Nubank Empresas", "media"
        )
    if _PF_NOME.match(filename):
        return Signal(
            AccountOwner.PERSONAL, "nome_do_arquivo", "Nome no padrão da conta pessoal", "media"
        )
    return None


def _payment_signal(
    library: Library, txs: list[Transaction], kind: AccountKind | None
) -> Signal | None:
    """Liga cartão e conta pelo pagamento da fatura (mesmo valor, até 4 dias de diferença)."""
    if kind is None:
        return None
    want_kind = AccountKind.CHECKING if kind == AccountKind.CARD else AccountKind.CARD
    mine = [t for t in txs if t.nature == TransactionNature.CARD_PAYMENT and not t.is_duplicate]
    if not mine:
        return None
    owners: list[AccountOwner] = []
    for tx in mine:
        for other in library.transactions:
            account = library.accounts.get(other.account_id)
            if (
                account is None
                or account.kind != want_kind
                or account.owner is None
                or other.nature != TransactionNature.CARD_PAYMENT
                or other.is_duplicate
                or round(other.amount, 2) != round(tx.amount, 2)
                or abs((other.date - tx.date).days) > 4
            ):
                continue
            owners.append(account.owner)
    if not owners or len(set(owners)) != 1:
        return None
    owner = owners[0]
    where = "da conta" if kind == AccountKind.CARD else "do cartão"
    return Signal(
        owner,
        "pagamento_da_fatura",
        f"O pagamento da fatura bate com um lançamento {where} {_owner_text(owner)}",
        "alta" if len(owners) >= 2 else "media",
    )


def detect(
    library: Library,
    parsed: OfxParseResult,
    filename: str,
    chosen_owner: AccountOwner | None = None,
    expect_kind: AccountKind | None = None,
) -> dict[str, object]:
    meta = parsed.meta
    kind = AccountKind(meta.kind) if meta and meta.kind else None
    acct_key = account_key(parsed.institution, meta.acct_id if meta else None)
    account = library.accounts.get(acct_key)
    txs = parsed.transactions
    link_key = None
    if meta and meta.acct_id:
        bank = _digits(meta.bank_id)
        link_key = f"{bank.zfill(4)}:{_digits(meta.acct_id)}" if bank else None

    signals: list[Signal] = []
    if account is not None and account.owner is not None:
        signals.append(
            Signal(
                account.owner,
                "cadastro",
                f"Esta conta já foi cadastrada como {_owner_text(account.owner)}",
                "alta",
            )
        )
    for signal in (
        _holder_signal(library, link_key) if kind == AccountKind.CHECKING else None,
        _payment_signal(library, txs, kind),
        _filename_signal(filename, kind),
    ):
        if signal is not None:
            signals.append(signal)

    owners = {s.owner for s in signals}
    best = max(signals, key=lambda s: _STRENGTH[s.strength]) if signals else None
    detected = best.owner if best else None
    confidence = best.strength if best else None
    warnings: list[dict[str, str]] = []

    if len(owners) > 1:
        confidence = "baixa"
        warnings.append(
            {
                "code": "sinais_divergentes",
                "severity": "atencao",
                "message": (
                    "Os sinais do arquivo apontam para donos diferentes. Confira antes de importar."
                ),
            }
        )
    if chosen_owner is not None and detected is not None and chosen_owner != detected:
        severity = "conflito" if confidence == "alta" else "atencao"
        reason = best.label if best else ""
        warnings.append(
            {
                "code": "dono_diferente_do_detectado",
                "severity": severity,
                "message": (
                    f"Você escolheu {_owner_text(chosen_owner)}, mas este arquivo parece ser de "
                    f"{_owner_text(detected)}. {reason}."
                ),
            }
        )
    if expect_kind is not None and kind is not None and expect_kind != kind:
        escolhido = "fatura do cartão" if expect_kind == AccountKind.CARD else "extrato da conta"
        real = "uma fatura do cartão" if kind == AccountKind.CARD else "um extrato de conta"
        warnings.append(
            {
                "code": "tipo_diferente",
                "severity": "conflito",
                "message": f"Você escolheu {escolhido}, mas o arquivo é {real}.",
            }
        )
    own_ids = {t.id for t in txs if t.id and not t.is_duplicate}
    if own_ids:
        elsewhere: dict[str, int] = {}
        for tx in library.transactions:
            if tx.id in own_ids and tx.account_id != acct_key:
                elsewhere[tx.account_id] = elsewhere.get(tx.account_id, 0) + 1
        for other_id, count in elsewhere.items():
            if count >= 2 and count / len(own_ids) >= 0.5:
                other = library.accounts.get(other_id)
                name = other.label or other_id if other else other_id
                warnings.append(
                    {
                        "code": "ja_importado_em_outra_conta",
                        "severity": "atencao",
                        "message": (
                            "Quase todos os lançamentos deste arquivo "
                            f"já foram importados em {name}."
                        ),
                    }
                )
    if parsed.institution is None:
        warnings.append(
            {
                "code": "banco_sem_perfil",
                "severity": "info",
                "message": (
                    "Este banco ainda não tem perfil no Trokim: "
                    "os lançamentos são lidos de forma genérica."
                ),
            }
        )
    if not txs:
        warnings.append(
            {
                "code": "arquivo_vazio",
                "severity": "info",
                "message": "O arquivo não tem lançamentos.",
            }
        )

    dates = [t.date for t in txs]
    period_start = (meta.period_start if meta else None) or (min(dates) if dates else None)
    period_end = (meta.period_end if meta else None) or (max(dates) if dates else None)
    status, closes_on, covered = infer_status(
        kind,
        period_start,
        period_end,
        meta.generated_at if meta else None,
        max(dates) if dates else None,
    )
    final_owner = chosen_owner or (account.owner if account else None) or detected
    return {
        "filename": filename,
        "institution": parsed.institution,
        "kind": kind.value if kind else None,
        "account_id": acct_key,
        "account_known": account is not None,
        "known_owner": account.owner.value if account and account.owner else None,
        "chosen_owner": chosen_owner.value if chosen_owner else None,
        "detected_owner": detected.value if detected else None,
        "confidence": confidence,
        "signals": [
            {"owner": s.owner.value, "source": s.source, "label": s.label, "strength": s.strength}
            for s in signals
        ],
        "warnings": warnings,
        "has_conflict": any(w["severity"] == "conflito" for w in warnings),
        "needs_owner": final_owner is None,
        "transaction_count": len(txs),
        "period": {
            "start": period_start.isoformat() if isinstance(period_start, date) else None,
            "end": period_end.isoformat() if isinstance(period_end, date) else None,
            "generated_at": meta.generated_at.isoformat() if meta and meta.generated_at else None,
            "status": status.value,
            "closes_on": closes_on.isoformat() if closes_on else None,
            "covered_until": covered.isoformat() if covered else None,
        },
    }
