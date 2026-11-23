"""Backup criptografado da biblioteca do usuário (arquivo ``.trokim``, ADR 0024).

Formato: ``MAGIC`` (11 bytes) + sal (16) + nonce (12) + texto cifrado. O conteúdo é o retrato da
biblioteca em JSON, comprimido com gzip e cifrado com AES-256-GCM. A chave vem da senha do
usuário por scrypt; a senha nunca é gravada. O ``MAGIC`` entra como dado autenticado.
"""

import gzip
import os
import zlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.domain.snapshot import SNAPSHOT_VERSION, LibrarySnapshot

MAGIC = b"TROKIM-BKP\x01"
SALT_SIZE = 16
NONCE_SIZE = 12
MAX_COMPRESSED_BYTES = 50 * 1024 * 1024
MAX_PLAIN_BYTES = 200 * 1024 * 1024


class BackupError(ValueError):
    """Backup inválido: senha errada, arquivo corrompido ou de uma versão mais nova."""


def _key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def export_backup(snapshot: LibrarySnapshot, passphrase: str) -> bytes:
    payload = gzip.compress(snapshot.model_dump_json().encode("utf-8"))
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    cipher = AESGCM(_key(passphrase, salt)).encrypt(nonce, payload, MAGIC)
    return MAGIC + salt + nonce + cipher


def import_backup(data: bytes, passphrase: str) -> LibrarySnapshot:
    header = len(MAGIC) + SALT_SIZE + NONCE_SIZE
    if len(data) > MAX_COMPRESSED_BYTES:
        raise BackupError("O arquivo de backup é grande demais.")
    if len(data) <= header or not data.startswith(MAGIC):
        raise BackupError("Este arquivo não é um backup do Trokim.")
    salt = data[len(MAGIC) : len(MAGIC) + SALT_SIZE]
    nonce = data[len(MAGIC) + SALT_SIZE : header]
    try:
        payload = AESGCM(_key(passphrase, salt)).decrypt(nonce, data[header:], MAGIC)
    except InvalidTag as exc:
        raise BackupError("Senha incorreta ou arquivo corrompido.") from exc
    try:
        decompressor = zlib.decompressobj(wbits=31)
        plain = decompressor.decompress(payload, MAX_PLAIN_BYTES)
        if decompressor.unconsumed_tail:
            raise BackupError("O conteúdo do backup é grande demais.")
        snapshot = LibrarySnapshot.model_validate_json(plain)
    except (zlib.error, ValueError) as exc:
        if isinstance(exc, BackupError):
            raise
        raise BackupError("O conteúdo do backup está corrompido.") from exc
    if snapshot.version > SNAPSHOT_VERSION:
        raise BackupError("Este backup é de uma versão mais nova do Trokim.")
    return snapshot
