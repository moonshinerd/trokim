"""Gráficos SVG dos ensaios multimodais, usando ReportLab já fixado no lock."""

import json
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[2]


def main():
    for path in sorted((ROOT / "research/rag_benchmark/results/documents").glob("*/run.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
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
            String(
                25, 250, "Famílias separadas; contagens, sem medir acurácia de OCR.", fontSize=10
            )
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
        drawing.add(
            String(25, 18, "Vermelho: ilegível aceito • Verde: ilegível rejeitado", fontSize=10)
        )
        output = ROOT / "docs/assets/documentos" / path.parent.name / "qualidade.svg"
        output.parent.mkdir(parents=True, exist_ok=True)
        renderSVG.drawToFile(drawing, str(output))
        print(f"gerado: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
