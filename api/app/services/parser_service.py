import io
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from ofxparse import OfxParser

from app.domain.models import (
    Transaction,
    TransactionCategory,
    TransactionType,
)
from app.services.bank_profiles import ExperimentalOfxProfile
from app.services.categorization_service import CategorizationService
from app.services.statement_profiles import (
    PROFILES,
    OfxMeta,
    decode_ofx,
    detect_statement,
    doc_is_company,
    parse_ofx_meta,
)


@dataclass
class OfxParseResult:
    transactions: list[Transaction]
    institution: str | None = None
    kind: str | None = None
    ledger_balance: float | None = None
    meta: OfxMeta | None = None
    # PDF: o total do arquivo fecha com a soma dos lançamentos? (``None`` = sem como saber)
    reconciled: bool | None = None


class ParserService:
    """Parser de arquivos financeiros padronizados (OFX e PDF).

    Responsável por converter extratos bancários em instâncias padronizadas
    da entidade de domínio Transaction, com deduplicação nativa.
    """

    @classmethod
    def parse_ofx(cls, file_content: bytes, filename: str = "extrato.ofx") -> list[Transaction]:
        return cls.parse_ofx_detailed(file_content, filename).transactions

    @classmethod
    def parse_ofx_detailed(
        cls, file_content: bytes, filename: str = "extrato.ofx"
    ) -> "OfxParseResult":
        text = decode_ofx(file_content)
        detection = detect_statement(text)
        meta = parse_ofx_meta(text)
        ofx = OfxParser.parse(io.BytesIO(text.encode("utf-8")))

        account_id = "default_account"
        if ofx.account and ofx.account.account_id:
            account_id = str(ofx.account.account_id)

        profile = (
            (PROFILES.get(detection.institution) or ExperimentalOfxProfile) if detection else None
        )
        statement = ofx.account.statement if ofx.account else None
        transactions: list[Transaction] = []
        if statement and statement.transactions:
            for item in statement.transactions:
                amount_val = float(item.amount)
                tx_type = TransactionType.CREDIT if amount_val > 0 else TransactionType.DEBIT
                abs_amount = round(abs(amount_val), 2)
                memo = (item.memo or item.payee or "Transação sem descrição").strip()
                tx_date = item.date.date() if isinstance(item.date, datetime) else item.date

                if profile and detection:
                    parsed = profile.parse(memo, tx_type, detection.kind, (item.payee or None))
                    description = parsed.description
                    category = CategorizationService.categorize(
                        parsed.merchant or parsed.description,
                        tx_type=tx_type,
                        nature=parsed.nature,
                        cnpj=parsed.counterparty_doc
                        if doc_is_company(parsed.counterparty_doc)
                        else None,
                    )
                    extra = {
                        "nature": parsed.nature,
                        "merchant": parsed.merchant,
                        "counterparty_kind": parsed.counterparty_kind,
                        "counterparty_doc": parsed.counterparty_doc,
                        "counterparty_account": parsed.counterparty_account,
                        "installment_number": parsed.installment_number,
                        "installment_total": parsed.installment_total,
                        "institution": detection.institution,
                    }
                else:
                    description = memo
                    category = cls._infer_category(memo, tx_type)
                    extra = {}

                transactions.append(
                    Transaction(
                        id=str(item.id) if item.id else None,
                        account_id=account_id,
                        description=description,
                        amount=abs_amount,
                        date=tx_date,
                        type=tx_type,
                        category=category,
                        source_file=filename,
                        **extra,
                    )
                )

        balance = None
        if statement is not None and getattr(statement, "balance", None) is not None:
            balance = round(float(statement.balance), 2)
        return OfxParseResult(
            transactions=cls.deduplicate(transactions),
            institution=detection.institution if detection else None,
            kind=detection.kind if detection else None,
            ledger_balance=balance,
            meta=meta,
        )

    _PDF_LINE = re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{4})?)\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<value>[-+]?\s*(?:R\$)?\s*[-+]?\s*\d+(?:\.\d{3})*,\d{2}|"
        r"[-+]?\s*(?:R\$)?\s*[-+]?\s*\d+\.\d{2})"
        r"(?P<tail>\s*[-CD])?\s*$",
        re.IGNORECASE,
    )
    _PDF_PARCELA = re.compile(r"\s+(\d{1,2})\s*/\s*(\d{1,2})\s*$")

    @staticmethod
    def _parse_money(raw: str) -> float:
        cleaned = raw.replace("R$", "").replace(" ", "").replace("+", "")
        negative = cleaned.startswith("-") or cleaned.endswith("-")
        cleaned = cleaned.strip("-")
        if "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        value = float(cleaned)
        return -value if negative else value

    @classmethod
    def parse_pdf_text(
        cls,
        text: str,
        filename: str = "fatura.pdf",
        today: date | None = None,
    ) -> list[Transaction]:
        """Extrai lançamentos de extratos/faturas em texto puro (extraídos via pypdf).

        Aceita acentos, milhar (``1.250,00``), sinal à frente ou atrás (``-R$ 10,00`` e
        ``10,00-``), sufixos ``C``/``D`` e parcelas (``03/10``). Numa fatura de cartão,
        valor sem sinal é compra (débito); num extrato, é entrada (crédito). Data sem ano
        usa o ano de referência mais recente que não fique no futuro.
        """
        transactions: list[Transaction] = []
        is_invoice = re.search(r"fatura", text, re.IGNORECASE) is not None
        reference = today or datetime.now().date()

        for raw_line in text.split("\n"):
            line = raw_line.strip()
            match = cls._PDF_LINE.search(line)
            if not match:
                continue

            raw_desc = match.group("desc").strip()
            try:
                amount_num = cls._parse_money(match.group("value"))
            except ValueError:
                continue
            tail = (match.group("tail") or "").strip().upper()
            if tail == "-":
                amount_num = -abs(amount_num)
            elif tail == "D":
                amount_num = -abs(amount_num)
            elif tail == "C":
                amount_num = abs(amount_num)
            elif amount_num > 0 and is_invoice:
                amount_num = -amount_num  # compra sem sinal numa fatura

            tx_type = TransactionType.CREDIT if amount_num > 0 else TransactionType.DEBIT
            abs_amount = round(abs(amount_num), 2)

            date_parts = match.group("date").split("/")
            try:
                day, month = int(date_parts[0]), int(date_parts[1])
                if len(date_parts) == 3:
                    year = int(date_parts[2])
                else:
                    year = reference.year if month <= reference.month else reference.year - 1
                tx_date = date(year, month, day)
            except ValueError:
                continue

            number = total = None
            parcela = cls._PDF_PARCELA.search(raw_desc)
            if parcela and int(parcela.group(2)) >= int(parcela.group(1)) >= 1:
                number, total = int(parcela.group(1)), int(parcela.group(2))
                raw_desc = raw_desc[: parcela.start()].strip()

            desc = re.sub(r"\s+", " ", raw_desc)
            transactions.append(
                Transaction(
                    account_id="pdf_account",
                    description=desc,
                    amount=abs_amount,
                    date=tx_date,
                    type=tx_type,
                    category=cls._infer_category(desc, tx_type),
                    source_file=filename,
                    installment_number=number,
                    installment_total=total,
                )
            )

        return cls.deduplicate(transactions)

    @staticmethod
    def _dedup_key(tx: Transaction) -> tuple:
        # O FITID do banco identifica o lançamento; sem ele, usa data, texto e valor.
        if tx.id and tx.institution:
            return ("fitid", tx.account_id, tx.id, tx.date, tx.amount, tx.type)
        return (tx.date, tx.description.lower(), tx.amount, tx.type)

    @classmethod
    def deduplicate(
        cls, transactions: list[Transaction], known: Iterable[Transaction] = ()
    ) -> list[Transaction]:
        """Identifica duplicatas com base em data, descrição e valor.

        Com ``known`` (lançamentos já importados), reenviar o mesmo extrato não
        conta duas vezes: o que já existe entre eles marca o novo como duplicata.
        """
        seen = {cls._dedup_key(tx) for tx in known if not tx.is_duplicate}
        for tx in transactions:
            key = cls._dedup_key(tx)
            if key in seen:
                tx.is_duplicate = True
            else:
                seen.add(key)
        return transactions

    @staticmethod
    def _infer_category(
        description: str, tx_type: TransactionType | None = None
    ) -> TransactionCategory:
        return CategorizationService.categorize(description, tx_type=tx_type)
