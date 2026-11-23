"""Registro de bancos suportados e seus níveis de suporte (ADR 0022).

Cada banco é um ``BankInfo``: identificador, nome, nível (``validado`` ou ``experimental``),
formatos aceitos e como reconhecê-lo **pelo conteúdo do arquivo, nunca pelo nome**. Banco novo é
um registro novo e um perfil; os demais não mudam (princípio da ADR 0017).

``validado`` só vale para banco conciliado ponta a ponta com arquivo **real** de uma conta real.
Sem isso, o banco sai como ``experimental``, no app e na documentação.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.statement_profiles import normalize_text

SupportLevel = Literal["validado", "experimental"]


@dataclass(frozen=True)
class BankInfo:
    bank_id: str
    display_name: str
    support_level: SupportLevel
    formats: tuple[str, ...]
    # Códigos de compensação (BANKID/FID do OFX), sem zeros à esquerda.
    ofx_codes: tuple[str, ...] = ()
    # Trechos (já sem acento, em minúsculas) do <ORG> do OFX.
    ofx_names: tuple[str, ...] = ()
    # Trechos (sem acento, em minúsculas) que identificam o PDF do banco.
    pdf_keywords: tuple[str, ...] = ()
    note: str | None = None


_REGISTRY: dict[str, BankInfo] = {}


def register_bank(info: BankInfo) -> BankInfo:
    """Registra um banco. Registrar de novo o mesmo ``bank_id`` é erro, não sobrescrita."""
    if info.bank_id in _REGISTRY:
        raise ValueError(f"Banco já registrado: {info.bank_id}")
    _REGISTRY[info.bank_id] = info
    return info


def unregister_bank(bank_id: str) -> None:
    """Remove um banco (útil em testes que registram um banco falso)."""
    _REGISTRY.pop(bank_id, None)


def get_bank(bank_id: str | None) -> BankInfo | None:
    return _REGISTRY.get(bank_id or "")


def list_banks() -> list[BankInfo]:
    return list(_REGISTRY.values())


def bank_label(bank_id: str | None) -> str:
    info = get_bank(bank_id)
    return info.display_name if info else (bank_id or "Banco").title()


def _code(raw: str) -> str:
    return raw.strip().lstrip("0")


def detect_ofx_bank(org: str, codes: set[str]) -> str | None:
    """Banco pelo ``<ORG>`` e pelos códigos do OFX. Os mais específicos vêm primeiro."""
    org_text = normalize_text(org)
    clean = {_code(c) for c in codes if c.strip()}
    for info in _REGISTRY.values():
        if any(name in org_text for name in info.ofx_names):
            return info.bank_id
        if clean & {_code(c) for c in info.ofx_codes}:
            return info.bank_id
    return None


def detect_pdf_bank(text: str) -> str | None:
    """Banco pelo texto do PDF (primeira ocorrência de uma palavra-chave do cadastro)."""
    norm = normalize_text(text)
    for info in _REGISTRY.values():
        if any(keyword in norm for keyword in info.pdf_keywords):
            return info.bank_id
    return None


def _seed() -> None:
    register_bank(
        BankInfo(
            "nubank",
            "Nubank",
            "validado",
            ("ofx",),
            ofx_codes=("260",),
            ofx_names=("nu pagamentos", "nubank"),
        )
    )
    register_bank(
        BankInfo(
            "bb",
            "Banco do Brasil",
            "validado",
            ("ofx", "pdf"),
            ofx_codes=("1",),
            ofx_names=("banco do brasil",),
            pdf_keywords=("ourocard",),
        )
    )
    # PicPay e Mercado Pago só exportam PDF (e o Mercado Pago, planilha). Os perfis foram escritos
    # a partir de formatos públicos e ainda não foram conciliados com arquivo real: experimentais
    # até alguém rodar ``make validar-banco`` com o próprio arquivo e os números fecharem.
    register_bank(
        BankInfo(
            "picpay",
            "PicPay",
            "experimental",
            ("pdf",),
            ofx_codes=("380",),
            ofx_names=("picpay",),
            pdf_keywords=("picpay",),
            note="Fatura e extrato lidos por layout público; falta arquivo real.",
        )
    )
    register_bank(
        BankInfo(
            "mercadopago",
            "Mercado Pago",
            "experimental",
            ("pdf",),
            ofx_codes=("323",),
            ofx_names=("mercado pago", "mercadopago"),
            pdf_keywords=("mercado pago", "mercadopago"),
            note="Extrato em PDF lido pelo layout publicado; falta conciliar com arquivo real.",
        )
    )
    register_bank(
        BankInfo(
            "inter",
            "Banco Inter",
            "experimental",
            ("ofx", "pdf"),
            ofx_codes=("77",),
            ofx_names=("banco inter", "inter&co", "inter e co"),
            pdf_keywords=("banco inter", "despesas da fatura", "a sua fatura chegou"),
            note="Sem conta real para validar; baseado no formato público.",
        )
    )
    register_bank(
        BankInfo(
            "c6",
            "C6 Bank",
            "experimental",
            ("ofx", "csv"),
            ofx_codes=("336",),
            ofx_names=("c6 bank", "banco c6"),
            pdf_keywords=("c6 bank", "banco c6"),
            note="Fatura em CSV e conta em OFX (web banking); sem arquivo real.",
        )
    )
    register_bank(
        BankInfo(
            "itau",
            "Itaú",
            "experimental",
            ("ofx", "pdf"),
            ofx_codes=("341",),
            ofx_names=("itau", "banco itau"),
            pdf_keywords=("itau unibanco", "lancamentos: compras e saques"),
            note="Sem conta real para validar; o OFX sai só pelo internet banking.",
        )
    )


_seed()
