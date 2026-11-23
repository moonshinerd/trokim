"""Gera os 40 documentos multimodais fictícios da #90, sem rede nem dados externos.

Uso: python research/synthetic_data/generate_document_images.py [--seed 90] [--output DIR]
As versões de Pillow/ReportLab estão fixadas em api/uv.lock; a fonte acompanha o código.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[2]
FONT = Path(__file__).parent / "fonts/Vera.ttf"
SEED = 90
CALIBRATION_FAMILIES = {1, 2, 3, 6, 7, 8, 9, 14, 15, 16}
BANKS = ("Nubank", "Nu Empresas", "Banco do Brasil", "Banco Horizonte Fictício")
COLORS = ("#6500a4", "#442080", "#124a8d", "#006b60")
KINDS = ("pix_receipt", "boleto", "card_invoice")
TITLES = ("Comprovante Pix", "Boleto", "Fatura de cartão")
LABELS = {
    "bank": "Banco",
    "date": "Data",
    "amount": "Valor",
    "counterparty": "Favorecido",
    "due_date": "Vencimento",
    "total": "Total",
}
NAMES = (
    "Pessoa Exemplo Alfa",
    "Pessoa Fictícia Beta",
    "Loja Sintética Gama",
    "Oficina Exemplo Delta",
)
PERSONAL = {
    "name": "Pessoa Exemplo Fictícia",
    "cpf": "000.000.000-00",
    "account": "0000000-0",
    "branch": "0000",
}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def original(family: int, rng: random.Random) -> dict:
    kind = KINDS[(family - 1) % 3]
    day = date(2026, 10, 1) + timedelta(days=family)
    amount = Decimal(rng.randrange(1250, 250000)) / 100
    bank = BANKS[(family - 1) % len(BANKS)]
    fields = {"bank": bank}
    rows = []
    if kind == "card_invoice":
        for n, description in enumerate(
            ("Mercado Exemplo", "Papelaria Fictícia", "Cinema Sintético")
        ):
            value = amount + Decimal(n * 125) / 100
            rows.append(
                {
                    "date": (day + timedelta(days=n)).isoformat(),
                    "description": description,
                    "amount": f"{value:.2f}",
                    "installment": None,
                }
            )
        fields.update(
            due_date=(day + timedelta(days=15)).isoformat(),
            total=f"{sum(Decimal(row['amount']) for row in rows):.2f}",
        )
    else:
        fields.update(amount=f"{amount:.2f}", counterparty=NAMES[(family - 1) % len(NAMES)])
        key = "date" if kind == "pix_receipt" else "due_date"
        fields[key] = day.isoformat()
    return {"kind": kind, "bank": bank, "fields": fields, "transactions": rows}


def formatted(key: str, value: str) -> str:
    if key in {"date", "due_date"}:
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    if key in {"amount", "total"}:
        return "R$ " + f"{Decimal(value):,.2f}".replace(",", "_").replace(".", ",").replace(
            "_", "."
        )
    return value


def render(source: dict, family: int) -> tuple[Image.Image, str, int]:
    """O campo essencial final pode ser retirado por corte/reflexo, mantendo os demais."""
    image = Image.new("RGB", (1000, 1250), "#fafafa")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 27)
    small = ImageFont.truetype(str(FONT), 19)
    title = ImageFont.truetype(str(FONT), 36)
    color = COLORS[(family - 1) % len(COLORS)]
    draw.text((65, 50), TITLES[KINDS.index(source["kind"])], font=title, fill="#151515")
    draw.rounded_rectangle((55, 115, 945, 175), radius=10, fill=color)
    draw.text((75, 129), "ÁREA DE DEMONSTRAÇÃO • SEM VALIDADE BANCÁRIA", font=small, fill="white")
    fields = source["fields"]
    last_key = {"pix_receipt": "counterparty", "boleto": "due_date", "card_invoice": "total"}[
        source["kind"]
    ]
    keys = [key for key in fields if key != last_key]
    y = 225
    for key in keys:
        draw.text(
            (65, y), f"{LABELS[key]}: {formatted(key, fields[key])}", font=font, fill="#151515"
        )
        y += 65
    for row in source["transactions"]:
        # Layout tabular visual; o texto explicita os três componentes, sem cálculo por OCR.
        text = (
            f"Lançamento: {formatted('date', row['date'])} | {row['description']} | "
            f"{formatted('amount', row['amount']).removeprefix('R$ ')}"
        )
        draw.text((65, y), text, font=ImageFont.truetype(str(FONT), 22), fill="#151515")
        y += 65
    draw.text(
        (65, y),
        f"{LABELS[last_key]}: {formatted(last_key, fields[last_key])}",
        font=font,
        fill="#151515",
    )
    draw.line((65, y + 65, 935, y + 65), fill="#cccccc", width=2)
    draw.text((65, 950), f"Titular: {PERSONAL['name']}", font=small, fill="#555555")
    draw.text((65, 985), f"CPF: {PERSONAL['cpf']}", font=small, fill="#555555")
    draw.text(
        (65, 1020),
        f"Agência: {PERSONAL['branch']}   Conta: {PERSONAL['account']}",
        font=small,
        fill="#555555",
    )
    draw.text(
        (65, 1135),
        "DADOS INVENTADOS • NÃO PAGAR • NÃO COMPROVA TRANSFERÊNCIA",
        font=small,
        fill=color,
    )
    return image, last_key, y


def variant(family: int) -> tuple[str, str, dict]:
    if family <= 5:
        name, parameters = (
            ("blur", {"radius": 0.45}),
            ("low_light", {"brightness": 0.65}),
            ("rotation", {"degrees": 1.0}),
            ("perspective", {"shear": 0.025}),
            ("jpeg", {"quality": 35}),
        )[family - 1]
        return "legible", name, parameters
    if family <= 13:
        return (
            "partial",
            "crop" if family % 2 == 0 else "reflection",
            {"essential_field_hidden": True},
        )
    return (
        "illegible",
        "blur",
        {"radius": 12.0 + family % 3, "brightness": 0.35 if family % 2 else 1.0},
    )


def degrade(image: Image.Image, name: str, parameters: dict, last_y: int) -> Image.Image:
    if name == "blur":
        image = image.filter(ImageFilter.GaussianBlur(parameters["radius"]))
        return ImageEnhance.Brightness(image).enhance(parameters.get("brightness", 1.0))
    if name == "low_light":
        return ImageEnhance.Brightness(image).enhance(parameters["brightness"])
    if name == "rotation":
        return image.rotate(parameters["degrees"], Image.Resampling.BICUBIC, fillcolor="white")
    if name == "perspective":
        return image.transform(
            image.size,
            Image.Transform.PERSPECTIVE,
            (1, parameters["shear"], -25, 0, 1, 0, 0.00001, 0),
            Image.Resampling.BICUBIC,
            fillcolor="white",
        )
    if name == "crop":
        return image.crop((0, 0, image.width, last_y - 5))
    if name == "reflection":
        image = image.copy()
        ImageDraw.Draw(image).polygon(
            [(0, last_y - 10), (1000, last_y - 5), (1000, last_y + 65), (0, last_y + 70)],
            fill="white",
        )
    return image


def encode(image: Image.Image, extension: str, jpeg_quality: int = 90) -> bytes:
    out = io.BytesIO()
    if extension == "pdf":
        # Invariant elimina data/ID voláteis. Só XObject de imagem; nenhuma camada de texto.
        pdf = Canvas(
            out, pagesize=(image.width / 2, image.height / 2), invariant=1, pageCompression=1
        )
        pdf.drawImage(ImageReader(image), 0, 0, width=image.width / 2, height=image.height / 2)
        pdf.showPage()
        pdf.save()
    elif extension == "jpg":
        image.save(out, format="JPEG", quality=jpeg_quality, subsampling=0, optimize=False)
    else:
        image.save(out, format="PNG", optimize=False, compress_level=9)
    return out.getvalue()


def build(seed: int = SEED) -> tuple[dict, dict[str, bytes]]:
    rng = random.Random(seed)
    cases, files = [], {}
    for family in range(1, 21):
        source = original(family, rng)
        base, hidden_key, last_y = render(source, family)
        for n in range(2):
            quality, degradation, parameters = variant(family) if n else ("legible", "none", {})
            image = degrade(base, degradation, parameters, last_y)
            index = (family - 1) * 2 + n + 1
            extension = (
                "pdf"
                if index % 5 == 0
                else "jpg"
                if degradation == "jpeg" or index % 3 == 0
                else "png"
            )
            relative = f"research/synthetic_data/document_images/D{index:02d}.{extension}"
            files[relative] = encode(image, extension, parameters.get("quality", 90))
            visible = {
                key: value
                for key, value in source["fields"].items()
                if quality != "illegible" and not (quality == "partial" and key == hidden_key)
            }
            cases.append(
                {
                    "id": f"D{index:02d}",
                    "family_id": f"F{family:02d}",
                    "path": relative,
                    "split": "calibration" if family in CALIBRATION_FAMILIES else "validation",
                    "kind": source["kind"],
                    "bank": source["bank"],
                    "media_type": {
                        "pdf": "application/pdf",
                        "jpg": "image/jpeg",
                        "png": "image/png",
                    }[extension],
                    "degradation": {
                        "type": degradation,
                        "level": "severe"
                        if quality == "illegible"
                        else "moderate"
                        if quality == "partial"
                        else "mild"
                        if n
                        else "none",
                        "parameters": parameters,
                    },
                    "expected_quality": quality,
                    "expected_fields": source["fields"],
                    "recoverable_fields": visible,
                    "expected_transactions": source["transactions"],
                    "recoverable_transactions": source["transactions"]
                    if quality != "illegible"
                    else [],
                    "demo": index in {1, 3, 28, 30},
                    "early_sample": index in {1, 3, 12, 28, 30},
                }
            )
        base.close()
    dataset = {
        "schema_version": 1,
        "seed": seed,
        "synthetic_only": True,
        "personal_data": PERSONAL,
        "cases": cases,
    }
    files["research/rag_benchmark/data/documents_gabarito.json"] = json_bytes(dataset)
    return dataset, files


def manifest(files: dict[str, bytes], root: Path = ROOT) -> dict:
    inputs = [
        Path(__file__).relative_to(ROOT).as_posix(),
        "research/synthetic_data/fonts/Vera.ttf",
        "research/synthetic_data/fonts/LICENSE.txt",
        "research/rag_benchmark/data/documents_gabarito.schema.json",
        "api/uv.lock",
    ]
    hashes = {path: sha256(content) for path, content in files.items()}
    hashes.update({path: sha256((root / path).read_bytes()) for path in inputs})
    return {
        "schema_version": 1,
        "hash_algorithm": "sha256-bytes",
        "files": dict(sorted(hashes.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--output", type=Path, default=ROOT, help="Raiz de destino; preserva a árvore relativa."
    )
    args = parser.parse_args()
    _, files = build(args.seed)
    files["research/rag_benchmark/documents_manifest.json"] = json_bytes(manifest(files))
    for relative, content in files.items():
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    print(f"40 documentos sintéticos gerados em {args.output}")


if __name__ == "__main__":
    main()
