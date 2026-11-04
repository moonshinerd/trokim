import io
import re
from datetime import datetime

from ofxparse import OfxParser

from app.domain.models import (
    Transaction,
    TransactionCategory,
    TransactionType,
)


class ParserService:
    """Parser de arquivos financeiros padronizados (OFX e PDF).

    Responsável por converter extratos bancários em instâncias padronizadas
    da entidade de domínio Transaction, com deduplicação nativa.
    """

    @classmethod
    def parse_ofx(cls, file_content: bytes, filename: str = "extrato.ofx") -> list[Transaction]:
        transactions: list[Transaction] = []
        stream = io.BytesIO(file_content)
        ofx = OfxParser.parse(stream)

        account_id = "default_account"
        if ofx.account and ofx.account.account_id:
            account_id = str(ofx.account.account_id)

        statement = ofx.account.statement if ofx.account else None
        if statement and statement.transactions:
            for item in statement.transactions:
                amount_val = float(item.amount)
                tx_type = TransactionType.CREDIT if amount_val > 0 else TransactionType.DEBIT
                abs_amount = round(abs(amount_val), 2)
                memo = (item.memo or item.payee or "Transação sem descrição").strip()

                category = cls._infer_category(memo)

                tx_date = item.date.date() if isinstance(item.date, datetime) else item.date

                transactions.append(
                    Transaction(
                        id=str(item.id) if item.id else None,
                        account_id=account_id,
                        description=memo,
                        amount=abs_amount,
                        date=tx_date,
                        type=tx_type,
                        category=category,
                        source_file=filename,
                    )
                )

        return cls.deduplicate(transactions)

    @classmethod
    def parse_pdf_text(cls, text: str, filename: str = "fatura.pdf") -> list[Transaction]:
        """Extrai lançamentos de extratos/faturas em texto puro (extraídos via pypdf).

        Padrão procurado: DD/MM ou DD/MM/AAAA seguido por descrição e valor
        (exemplo: R$ 123,45 ou -123.45).
        """
        transactions: list[Transaction] = []
        pattern = re.compile(
            r"(\d{2}/\d{2}(?:/\d{4})?)\s+([A-Za-z0-9\s\.\*\-\_]+?)\s+(-?R?\$?\s*\d+[\.,]\d{2})"
        )

        current_year = datetime.now().year

        for line in text.split("\n"):
            line = line.strip()
            match = pattern.search(line)
            if not match:
                continue

            raw_date, raw_desc, raw_val = match.groups()
            cleaned_val = (
                raw_val.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
            )
            try:
                amount_num = float(cleaned_val)
            except ValueError:
                continue

            tx_type = TransactionType.CREDIT if amount_num > 0 else TransactionType.DEBIT
            abs_amount = round(abs(amount_num), 2)

            date_parts = raw_date.split("/")
            if len(date_parts) == 2:
                day, month = int(date_parts[0]), int(date_parts[1])
                tx_date = datetime(current_year, month, day).date()
            else:
                day, month, year = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                tx_date = datetime(year, month, day).date()

            desc = raw_desc.strip()
            transactions.append(
                Transaction(
                    account_id="pdf_account",
                    description=desc,
                    amount=abs_amount,
                    date=tx_date,
                    type=tx_type,
                    category=cls._infer_category(desc),
                    source_file=filename,
                )
            )

        return cls.deduplicate(transactions)

    @classmethod
    def deduplicate(cls, transactions: list[Transaction]) -> list[Transaction]:
        """Identifica duplicatas com base em data, descrição e valor."""
        seen = set()
        for tx in transactions:
            key = (tx.date, tx.description.lower(), tx.amount, tx.type)
            if key in seen:
                tx.is_duplicate = True
            else:
                seen.add(key)
        return transactions

    @staticmethod
    def _infer_category(description: str) -> TransactionCategory:
        d = description.lower()
        if any(w in d for w in ["mercado", "supermercado", "padaria", "ifood", "restaurante"]):
            return TransactionCategory.FOOD
        if any(w in d for w in ["uber", "combustivel", "posto", "onibus", "metro"]):
            return TransactionCategory.TRANSPORT
        if any(w in d for w in ["aluguel", "condominio", "energia", "luz", "agua", "gas"]):
            return TransactionCategory.HOUSING
        if any(w in d for w in ["farmacia", "medico", "hospital", "clinica"]):
            return TransactionCategory.HEALTH
        if any(w in d for w in ["curso", "faculdade", "escola", "livraria"]):
            return TransactionCategory.EDUCATION
        if any(w in d for w in ["cinema", "netflix", "spotify", "viagem", "steam"]):
            return TransactionCategory.LEISURE
        if any(w in d for w in ["salario", "ted recebida", "pix recebido", "proventos"]):
            return TransactionCategory.INCOME
        return TransactionCategory.OTHER
