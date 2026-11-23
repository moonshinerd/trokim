"""Leitura e validação dos insumos multimodais, sem expor gabarito aos motores."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
GABARITO = ROOT / "research/rag_benchmark/data/documents_gabarito.json"
SCHEMA = GABARITO.with_suffix(".schema.json")
MANIFEST = ROOT / "research/rag_benchmark/documents_manifest.json"


def load_dataset() -> dict:
    data = json.loads(GABARITO.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(data)
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for relative, digest in expected["files"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Insumo multimodal alterado: {relative}")
    for family in {case["family_id"] for case in data["cases"]}:
        splits = {c["split"] for c in data["cases"] if c["family_id"] == family}
        if len(splits) != 1:
            raise ValueError(f"Família presente nos dois conjuntos: {family}")
    return data
