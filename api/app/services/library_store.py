"""Conversão entre a biblioteca em memória e o retrato, e persistência dela (ADR 0024)."""

import hashlib
import threading

from app.core.config import settings
from app.domain.snapshot import (
    LibrarySnapshot,
    StoredIdentity,
    StoredOwnMark,
    StoredTransaction,
    StoredTransfer,
)
from app.models.library_repository import LibraryRepository
from app.services.library_service import LIBRARY, ConfirmedTransfer, Identity, Library

_lock = threading.Lock()
_repository: LibraryRepository | None = None
_last_hash: str | None = None


def _stored(tx) -> StoredTransaction:
    data = tx.model_dump()
    data["counterparty_doc"] = tx.counterparty_doc
    data["counterparty_account"] = tx.counterparty_account
    return StoredTransaction.model_validate(data)


def snapshot_from(library: Library) -> LibrarySnapshot:
    return LibrarySnapshot(
        transactions=[_stored(tx) for tx in library.transactions],
        statements=dict(library.statements),
        accounts=dict(library.accounts),
        rejected_pairs=sorted(library.rejected_pairs),
        confirmed={
            key: StoredTransfer(
                debit_uid=t.debit_uid,
                credit_uid=t.credit_uid,
                identities=[StoredIdentity(name_norm=i.name_norm, doc=i.doc) for i in t.identities],
                kind=t.kind,
            )
            for key, t in library.confirmed.items()
        },
        own_marks={
            uid: StoredOwnMark(nature=nature, category=category)
            for uid, (nature, category) in library.own_marks.items()
        },
        own_reasons=dict(library.own_reasons),
        not_own=sorted(library.not_own),
        category_rules=dict(library.category_rules),
    )


def _transaction(stored: StoredTransaction):
    from app.domain.models import Transaction

    return Transaction.model_validate(stored.model_dump(exclude={"uid"}))


def apply_snapshot(library: Library, snapshot: LibrarySnapshot, *, merge: bool = False) -> dict:
    """Aplica o retrato na biblioteca. Sem ``merge``, substitui tudo; com ``merge``, só
    acrescenta o que ainda não existe (por identificador). Devolve as contagens do que entrou."""
    if not merge:
        library.reset()
    known = {tx.uid for tx in library.transactions}
    added = 0
    for stored in snapshot.transactions:
        tx = _transaction(stored)
        if tx.uid not in known:
            library.transactions.append(tx)
            known.add(tx.uid)
            added += 1
    accounts = statements = 0
    for key, account in snapshot.accounts.items():
        if key not in library.accounts:
            library.accounts[key] = account
            accounts += 1
    for key, statement in snapshot.statements.items():
        if key not in library.statements:
            library.statements[key] = statement
            statements += 1
    library.rejected_pairs.update(snapshot.rejected_pairs)
    library.not_own.update(snapshot.not_own)
    for key, rule in snapshot.category_rules.items():
        library.category_rules.setdefault(key, rule)
    for uid, mark in snapshot.own_marks.items():
        library.own_marks.setdefault(uid, (mark.nature, mark.category))
    for uid, reason in snapshot.own_reasons.items():
        library.own_reasons.setdefault(uid, reason)
    for key, transfer in snapshot.confirmed.items():
        library.confirmed.setdefault(
            key,
            ConfirmedTransfer(
                debit_uid=transfer.debit_uid,
                credit_uid=transfer.credit_uid,
                identities=[Identity(i.name_norm, i.doc) for i in transfer.identities],
                kind=transfer.kind,
            ),
        )
    return {"transactions": added, "accounts": accounts, "statements": statements}


def configure(repository: LibraryRepository | None) -> None:
    """Define o repositório (``None`` desliga a persistência). Usado por testes e na partida."""
    global _repository, _last_hash
    with _lock:
        _repository = repository
        _last_hash = None


def _default_repository() -> LibraryRepository | None:
    if not settings.LIBRARY_PERSISTENCE:
        return None
    from app.clients.sqlite_library_repository import SqliteLibraryRepository

    return SqliteLibraryRepository(settings.DATABASE_URL)


def _current() -> LibraryRepository | None:
    global _repository
    if _repository is None:
        _repository = _default_repository()
    return _repository


def restore(library: Library = LIBRARY) -> bool:
    """Carrega o último retrato gravado para a biblioteca. Devolve se havia algo."""
    global _last_hash
    with _lock:
        repository = _current()
        snapshot = repository.load() if repository else None
        if snapshot is None:
            return False
        apply_snapshot(library, snapshot)
        _last_hash = hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest()
        return True


def persist(library: Library = LIBRARY) -> bool:
    """Grava a biblioteca se mudou desde a última gravação. Devolve se gravou."""
    global _last_hash
    with _lock:
        repository = _current()
        if repository is None:
            return False
        snapshot = snapshot_from(library)
        digest = hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest()
        if digest == _last_hash:
            return False
        repository.save(snapshot)
        _last_hash = digest
        return True
