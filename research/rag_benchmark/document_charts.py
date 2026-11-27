"""Gráficos SVG dos ensaios multimodais, usando ReportLab já fixado no lock."""

import json
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[2]

SPLITS = (("calibration", "Calibração"), ("validation", "Verificação"))
FIELDS = (
    ("amount", "valor"),
    ("date", "data"),
    ("counterparty", "favorecido"),
    ("total", "total"),
    ("due_date", "vencimento"),
    ("bank", "banco"),
)


def extraction_chart(run: dict, output: Path) -> None:
    if run["mode"] != "rapidocr":
        return
    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 170, 65, 380, 150
    chart.categoryAxis.categoryNames = ["Calibração", "Verificação"]
    series = [
        ("correct_fields", "recoverable_fields"),
        ("correct_transactions", "recoverable_transactions"),
    ]
    if all("numeric_transactions" in group for group in run["summary"].values()):
        series.append(("numeric_transactions", "recoverable_transactions"))
    chart.data = [
        tuple(
            100 * run["summary"][split][num] / run["summary"][split][den]
            for split in ("calibration", "validation")
        )
        for num, den in series
    ]
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 100, 25
    for i, color in enumerate(("#2a78d6", "#eb6834", "#1baf7a")[: len(series)]):
        chart.bars[i].fillColor = HexColor(color)
    chart.barLabelFormat = "%.1f%%"
    chart.barLabels.nudge = 14
    drawing = Drawing(650, 300)
    drawing.add(String(25, 275, "OCR real — acerto exato e componente financeiro", fontSize=14))
    drawing.add(
        String(25, 250, "Corpus de desenvolvimento inspecionado; não é teste cego.", fontSize=10)
    )
    drawing.add(chart)
    drawing.add(String(25, 35, "Azul: campos exatos • Laranja: linhas exatas", fontSize=10))
    drawing.add(
        String(
            25, 18, "Verde: datas, valores e parcelas das linhas (ignora descrição)", fontSize=10
        )
    )
    renderSVG.drawToFile(drawing, str(output / "extracao.svg"))


def _field_chart(run: dict, output: Path) -> None:
    summary = run["summary"]
    fields = [
        (key, label)
        for key, label in FIELDS
        if any(summary[split]["per_field"].get(key, {}).get("expected") for split, _ in SPLITS)
    ]
    if not fields:
        return
    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 170, 65, 380, 30 * len(fields) + 30
    chart.categoryAxis.categoryNames = [label for _, label in fields][::-1]
    chart.data = [
        tuple(
            100 * summary[split]["per_field"][key]["correct"] / summary[split]["per_field"][key]["expected"]
            if summary[split]["per_field"].get(key, {}).get("expected")
            else 0
            for key, _ in fields
        )[::-1]
        for split, _ in SPLITS
    ]
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 100, 25
    chart.bars[0].fillColor = HexColor("#2a78d6")
    chart.bars[1].fillColor = HexColor("#eb6834")
    chart.barLabelFormat = "%.1f%%"
    chart.barLabels.nudge = 14
    drawing = Drawing(650, 165 + 30 * len(fields))
    top = 165 + 30 * len(fields)
    drawing.add(
        String(25, top - 25, f"Motor {run['engine']} — acerto por campo recuperável", fontSize=14)
    )
    drawing.add(String(25, top - 45, "Azul: calibração • Laranja: verificação", fontSize=10))
    drawing.add(chart)
    for line, (split, split_label) in enumerate(SPLITS):
        counts = "  ".join(
            f"{label} {summary[split]['per_field'].get(key, {}).get('correct', 0)}/{summary[split]['per_field'].get(key, {}).get('expected', 0)}"
            for key, label in fields
        )
        drawing.add(String(25, 40 - 14 * line, f"{split_label}: {counts}", fontSize=8))
    renderSVG.drawToFile(drawing, str(output / "campos.svg"))


def _accuracy_chart(run: dict, output: Path) -> None:
    summary = run["summary"]
    measures = (
        ("Campos recuperáveis", "correct_fields", "recoverable_fields"),
        ("Documentos íntegros", "correct_documents", "documents"),
        ("Abstenção segura (ilegíveis)", "safe_abstentions", "illegible_documents"),
    )
    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 210, 65, 340, 120
    chart.categoryAxis.categoryNames = [name for name, _, _ in measures][::-1]
    chart.data = [
        tuple(
            100 * summary[split][num] / summary[split][den] if summary[split][den] else 0
            for _, num, den in measures
        )[::-1]
        for split, _ in SPLITS
    ]
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 100, 25
    chart.bars[0].fillColor = HexColor("#2a78d6")
    chart.bars[1].fillColor = HexColor("#eb6834")
    chart.barLabelFormat = "%.1f%%"
    chart.barLabels.nudge = 14
    drawing = Drawing(650, 290)
    drawing.add(
        String(25, 265, f"Motor {run['engine']} — acerto de documento e abstenção", fontSize=14)
    )
    drawing.add(
        String(
            25,
            240,
            "Azul: calibração • Laranja: verificação; meta de abstenção segura: 100%.",
            fontSize=10,
        )
    )
    drawing.add(chart)
    for line, (split, split_label) in enumerate(SPLITS):
        counts = "; ".join(
            f"{name} {summary[split][num]}/{summary[split][den]}"
            for name, num, den in measures
        )
        drawing.add(String(25, 45 - 14 * line, f"{split_label}: {counts}", fontSize=8))
    renderSVG.drawToFile(drawing, str(output / "acertos.svg"))


def _risk_chart(run: dict, output: Path) -> None:
    summary = run["summary"]
    measures = (
        ("Falso aceite (ilegível lido)", "false_accepts"),
        ("Campos inventados", "invented_fields"),
        ("Falhas técnicas", "technical_failures"),
    )
    top_value = max(
        (summary[split][key] for split, _ in SPLITS for _, key in measures), default=0
    )
    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 210, 65, 340, 120
    chart.categoryAxis.categoryNames = [name for name, _ in measures][::-1]
    chart.data = [
        tuple(summary[split][key] for _, key in measures)[::-1] for split, _ in SPLITS
    ]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(4, top_value)
    chart.valueAxis.valueStep = max(1, round(max(4, top_value) / 4))
    chart.bars[0].fillColor = HexColor("#2a78d6")
    chart.bars[1].fillColor = HexColor("#eb6834")
    chart.barLabelFormat = "%d"
    chart.barLabels.nudge = 7
    drawing = Drawing(650, 290)
    drawing.add(
        String(25, 265, f"Motor {run['engine']} — riscos e falhas (meta: zero)", fontSize=14)
    )
    drawing.add(
        String(
            25,
            240,
            "Azul: calibração • Laranja: verificação; falha técnica não conta como acerto.",
            fontSize=10,
        )
    )
    drawing.add(chart)
    denominators = "  ".join(
        f"{split_label}: {summary[split]['illegible_documents']} ilegíveis, "
        f"{summary[split]['documents']} documentos, "
        f"{summary[split]['recoverable_fields']} campos recuperáveis"
        for split, split_label in SPLITS
    )
    drawing.add(String(25, 30, denominators, fontSize=8))
    renderSVG.drawToFile(drawing, str(output / "riscos.svg"))


def _degradation_chart(run: dict, output: Path) -> None:
    summary = run["summary"]
    names = sorted(
        {
            name
            for split, _ in SPLITS
            for name in summary[split].get("by_degradation", {})
        }
    )
    if not names:
        return
    def rate(split, name):
        group = summary[split].get("by_degradation", {}).get(name, {})
        den = group.get("recoverable_fields", 0)
        return 100 * group.get("correct_fields", 0) / den if den else 0

    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 170, 65, 380, 22 * len(names) + 30
    chart.categoryAxis.categoryNames = names[::-1]
    chart.data = [
        tuple(rate(split, name) for name in names)[::-1] for split, _ in SPLITS
    ]
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 100, 25
    chart.bars[0].fillColor = HexColor("#2a78d6")
    chart.bars[1].fillColor = HexColor("#eb6834")
    chart.barLabelFormat = "%.1f%%"
    chart.barLabels.nudge = 14
    height = 165 + 22 * len(names) + 30
    drawing = Drawing(650, height)
    drawing.add(
        String(
            25,
            height - 25,
            f"Motor {run['engine']} — acerto de campos por degradação",
            fontSize=14,
        )
    )
    drawing.add(
        String(25, height - 45, "Azul: calibração • Laranja: verificação", fontSize=10)
    )
    drawing.add(chart)
    for line, (split, split_label) in enumerate(SPLITS):
        counts = "  ".join(
            f"{name} {summary[split].get('by_degradation', {}).get(name, {}).get('correct_fields', 0)}"
            f"/{summary[split].get('by_degradation', {}).get(name, {}).get('recoverable_fields', 0)}"
            for name in names
        )
        drawing.add(String(25, 55 - 14 * line, f"{split_label}: {counts}", fontSize=8))
    renderSVG.drawToFile(drawing, str(output / "degradacao.svg"))


def _latency_chart(run: dict, output: Path) -> None:
    summary = run["summary"]
    pairs = [
        (f"{label} — média", summary[split]["latency_ms"]["mean"])
        for split, label in SPLITS
        if summary[split]["latency_ms"]["mean"] is not None
    ] + [
        (f"{label} — p95", summary[split]["latency_ms"]["p95"])
        for split, label in SPLITS
        if summary[split]["latency_ms"]["p95"] is not None
    ]
    if not pairs:
        return
    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 170, 65, 380, 40 * len(pairs) + 20
    chart.categoryAxis.categoryNames = [name for name, _ in pairs][::-1]
    chart.data = [(tuple(value for _, value in pairs)[::-1])]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(value for _, value in pairs) * 1.1
    chart.bars[0].fillColor = HexColor("#2a78d6")
    chart.barLabelFormat = "%d"
    chart.barLabels.nudge = 7
    drawing = Drawing(650, 165 + 40 * len(pairs))
    top = 165 + 40 * len(pairs)
    model = run.get("model") or "sem visão"
    drawing.add(
        String(25, top - 25, f"Motor {run['engine']} ({model}) — latência por documento", fontSize=14)
    )
    drawing.add(String(25, top - 45, "Milissegundos; média e p95 por conjunto.", fontSize=10))
    drawing.add(chart)
    usage = next(
        (summary[split]["usage"] for split, _ in SPLITS if summary[split]["usage"]["calls"]),
        None,
    )
    note = (
        f"Visão: {usage['calls']} chamadas, {usage['prompt_tokens']} tokens de entrada, "
        f"{usage['completion_tokens']} de saída; custo {usage['cost_status']}."
        if usage
        else "Sem chamadas de visão nesta execução."
    )
    drawing.add(String(25, 30, note, fontSize=8))
    renderSVG.drawToFile(drawing, str(output / "latencia.svg"))


def engine_charts(run: dict, output: Path) -> list[str]:
    generated = []
    for chart in (_field_chart, _accuracy_chart, _risk_chart, _degradation_chart, _latency_chart):
        chart(run, output)
        generated.append(chart.__name__)
    return generated


def gate_chart(run: dict, output: Path) -> None:
    summary = run["summary"]
    chart = HorizontalBarChart()
    chart.x, chart.y, chart.width, chart.height = 170, 65, 380, 150
    chart.data = [
        tuple(summary[s]["gate"][key] for s in ("calibration", "validation"))
        for key in (
            "readable_accepted",
            "readable_rejected",
            "illegible_accepted",
            "illegible_rejected",
        )
    ]
    chart.categoryAxis.categoryNames = ["Calibração (20)", "Verificação (20)"]
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 20, 5
    chart.bars[0].fillColor = HexColor("#2a78d6")
    chart.bars[1].fillColor = HexColor("#eb6834")
    chart.bars[2].fillColor = HexColor("#b02030")
    chart.bars[3].fillColor = HexColor("#1baf7a")
    chart.barLabels.nudge = 7
    chart.barLabelFormat = "%d"
    drawing = Drawing(650, 300)
    drawing.add(String(25, 275, "Porteiro de qualidade — corpus sintético (#90)", fontSize=14))
    drawing.add(
        String(25, 250, "Famílias separadas; contagens, sem medir acurácia de OCR.", fontSize=10)
    )
    drawing.add(chart)
    drawing.add(
        String(
            25,
            35,
            "Azul: legível/parcial aceito • Laranja: legível/parcial rejeitado",
            fontSize=10,
        )
    )
    drawing.add(String(25, 18, "Vermelho: ilegível aceito • Verde: ilegível rejeitado", fontSize=10))
    renderSVG.drawToFile(drawing, str(output / "qualidade.svg"))


def main():
    for path in sorted((ROOT / "research/rag_benchmark/results/documents").glob("*/run.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        output = ROOT / "docs/assets/documentos" / path.parent.name
        output.mkdir(parents=True, exist_ok=True)
        if run.get("engine"):
            engine_charts(run, output)
        else:
            gate_chart(run, output)
            extraction_chart(run, output)
        print(f"gerado: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
