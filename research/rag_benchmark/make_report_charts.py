"""Gera os gráficos versionados do benchmark (Semana 2) e da comparação LLM x RAG (Semana 3).

Uso (matplotlib não é dependência do projeto; o `uv` o traz só para este comando):

    make report-charts

Cada execução da comparação mora em `results/comparison/<run_id>/` com um `run.json`
(data, commit, modelo, parâmetros e métricas). Os gráficos de cada execução vão para
`docs/assets/comparacao/<run_id>/`, os da Semana 2 para `docs/assets/comparacao/semana2/`
e a comparação entre execuções para `docs/assets/comparacao/entre-execucoes/`. Para
registrar uma nova execução, veja `docs/pesquisa/resultados.md`.

Cores: três primeiras posições da paleta categórica validada (azul, laranja, verde-água),
sempre com o valor escrito em cada barra, porque o verde-água tem contraste baixo sobre
o branco.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research/rag_benchmark/results"
OUT_DIR = ROOT / "docs/assets/comparacao"

SURFACE = "#ffffff"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

KEYS = ["llm_pura", "rag_ingenuo", "trokim_estruturado"]
LABELS = ["LLM pura", "RAG ingênuo", "Trokim estruturado"]
COLORS = [BLUE, ORANGE, AQUA]

# Metas da Entrega 2 (docs/rag/index.md).
WEEK2_TARGETS = {"recall_at_3": 0.90, "grounded_accuracy": 0.90, "abstention_accuracy": 1.00}
WEEK2_NAMES = {
    "recall_at_3": "Recall@3",
    "grounded_accuracy": "Resposta fundamentada",
    "abstention_accuracy": "Abstenção correta",
}


def pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",") + "%"


def style(ax, *, grid_axis: str = "y") -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, length=0, labelsize=8.5)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print(f"gerado: {path.relative_to(ROOT)}")


def legend_top(ax, **kwargs) -> None:
    ax.legend(
        frameon=False,
        fontsize=8,
        labelcolor=INK_2,
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        **kwargs,
    )


def load_runs() -> list[dict]:
    runs = []
    for path in sorted(RESULTS.glob("comparison/*/run.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_dir"] = path.parent
        runs.append(data)
    return runs


def run_styles(run):
    keys = list(run["approaches"])
    palette = dict(zip(KEYS + ["multiagente"], COLORS + ["#52514e"], strict=True))
    return keys, [run["approaches"][k]["label"] for k in keys], [palette[k] for k in keys]


def fig_metrics(run: dict, out: Path) -> None:
    KEYS, LABELS, COLORS = run_styles(run)
    approaches = run["approaches"]
    series = {
        "F1 de tokens": [approaches[k]["f1_tokens"] for k in KEYS],
        "Cobertura de\nconceitos": [approaches[k]["concept_coverage"] for k in KEYS],
        "Inconsistência\n(heurística; menor\né melhor)": [
            approaches[k]["inconsistency_rate"] for k in KEYS
        ],
        "F1 de abstenção": [approaches[k]["abstention_f1"] for k in KEYS],
    }
    names = list(series)
    fig, ax = plt.subplots(figsize=(6.8, 3.5), facecolor=SURFACE)
    style(ax)
    width = 0.8 / len(KEYS)
    for i, (label, color) in enumerate(zip(LABELS, COLORS, strict=True)):
        xs = [g + (i - (len(KEYS) - 1) / 2) * (width + 0.03) for g in range(len(names))]
        values = [100 * (series[name][i] or 0) for name in names]
        bars = ax.bar(xs, values, width, color=color, label=label, edgecolor=SURFACE)
        for bar, value, name in zip(bars, values, names, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 1.2,
                pct(value) if series[name][i] is not None else "—",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color=INK,
            )
    ax.set_xticks(range(len(names)), names)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20), [f"{v}%" for v in range(0, 101, 20)])
    legend_top(ax, ncol=3)
    save(fig, out / "fig1-metricas.png")


def fig_audit(run: dict, out: Path) -> None:
    """Alucinações confirmadas pela revisão, separadas do que a heurística sinalizou."""
    KEYS, LABELS, COLORS = run_styles(run)
    audit = [run["approaches"][k]["audit"] for k in KEYS]
    cases = run["cases"]
    fig, ax = plt.subplots(figsize=(6.8, 3.4), facecolor=SURFACE)
    style(ax)
    tops = []
    for i, (info, color) in enumerate(zip(audit, COLORS, strict=True)):
        confirmed_flagged = info["flagged"] - info["false_positives"]
        missed = info["confirmed"] - confirmed_flagged  # confirmadas que a heurística não viu
        false_pos = info["false_positives"]
        segments = [
            (confirmed_flagged, {"alpha": 1.0, "hatch": ""}, "white"),
            (missed, {"alpha": 0.7, "hatch": "xxx"}, "white"),
            (false_pos, {"alpha": 0.3, "hatch": "///"}, INK),
        ]
        bottom = 0
        for count, kwargs, text_color in segments:
            if count <= 0:
                continue
            ax.bar(
                i,
                count,
                0.5,
                bottom=bottom,
                color=color,
                edgecolor=SURFACE,
                linewidth=1.5,
                **kwargs,
            )
            ax.text(
                i,
                bottom + count / 2,
                str(count),
                ha="center",
                va="center",
                fontsize=9,
                color=INK if kwargs["hatch"] == "xxx" else text_color,
                fontweight="bold",
                bbox=(
                    {"facecolor": SURFACE, "edgecolor": "none", "pad": 1.2}
                    if kwargs["hatch"] == "xxx"
                    else None
                ),
            )
            bottom += count
        tops.append(bottom)
        ax.text(
            i,
            bottom + 0.5,
            f"Taxa auditada: {pct(info['confirmed'] / cases * 100)}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            color=INK,
            fontweight="bold",
        )
    ax.set_xticks(range(len(KEYS)), LABELS)
    ax.set_ylim(0, max(tops) + 4)
    ax.set_yticks(range(0, max(tops) + 1, 5))
    ax.set_ylabel(f"Casos (de {cases})", color=INK_2, fontsize=8.5)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=INK_2, label="Confirmada e sinalizada pela heurística"),
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=INK_2,
            alpha=0.7,
            hatch="xxx",
            edgecolor=SURFACE,
            label="Confirmada, mas a heurística não sinalizou",
        ),
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=GRID,
            hatch="///",
            edgecolor=INK_2,
            label="Falso positivo da heurística",
        ),
    ]
    ax.legend(
        handles=handles,
        ncol=1,
        frameon=False,
        fontsize=8,
        labelcolor=INK_2,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
    )
    save(fig, out / "fig2-alucinacao-auditada.png")


def fig_latency(run: dict, out: Path) -> None:
    KEYS, LABELS, COLORS = run_styles(run)
    values = [run["approaches"][k]["latency_ms"] for k in KEYS]
    fig, ax = plt.subplots(figsize=(6.8, 1.9), facecolor=SURFACE)
    style(ax, grid_axis="x")
    ypos = list(range(len(LABELS)))[::-1]
    for y, value, color in zip(ypos, values, COLORS, strict=True):
        ax.barh(y, value, 0.5, color=color, edgecolor=SURFACE)
        ax.text(
            value + 40,
            y,
            f"{value:,} ms".replace(",", "."),
            va="center",
            fontsize=8.5,
            color=INK,
        )
    ax.set_yticks(ypos, LABELS)
    ax.set_xlim(0, max(values) * 1.25)
    ax.set_xlabel(
        f"Latência média por resposta (ms); {run['model']}, execução local",
        color=INK_2,
        fontsize=8.5,
    )
    save(fig, out / "fig3-latencia.png")


def fig_across_runs(runs: list[dict], out: Path) -> None:
    """Mesmas métricas em execuções diferentes, para mostrar a variação entre elas."""
    panels = [
        ("concept_coverage", "Cobertura de conceitos"),
        ("inconsistency_rate", "Inconsistência (heurística)"),
        ("f1_tokens", "F1 de tokens"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.2), facecolor=SURFACE, sharey=True)
    width = 0.34
    hatches = ["", "///", "xxx", "..."]
    for ax, (metric, title) in zip(axes, panels, strict=True):
        style(ax)
        for j, run in enumerate(runs):
            xs = [g + (j - (len(runs) - 1) / 2) * (width + 0.03) for g in range(3)]
            for x, key, color in zip(xs, KEYS, COLORS, strict=True):
                raw = run["approaches"][key][metric]
                if raw is None:
                    continue
                value = 100 * raw
                ax.bar(
                    x,
                    value,
                    width,
                    color=color,
                    alpha=1.0 if j == 0 else 0.5,
                    edgecolor=SURFACE,
                    hatch=hatches[j % len(hatches)],
                )
                ax.text(x, value + 1.5, f"{value:.0f}", ha="center", fontsize=7.5, color=INK)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xticks(range(3), ["LLM\npura", "RAG\ningênuo", "Trokim"], fontsize=8)
        ax.set_ylim(0, 100)
    axes[0].set_yticks(range(0, 101, 20), [f"{v}%" for v in range(0, 101, 20)])
    handles = [
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor=INK_2,
            alpha=1.0 if j == 0 else 0.5,
            hatch=hatches[j % len(hatches)],
            edgecolor=SURFACE,
            label=run["run_id"],
        )
        for j, run in enumerate(runs)
    ]
    fig.legend(
        handles=handles,
        ncol=len(runs),
        frameon=False,
        fontsize=8,
        labelcolor=INK_2,
        loc="lower left",
        bbox_to_anchor=(0.06, 0.96),
    )
    save(fig, out / "fig-variacao-entre-execucoes.png")


def fig_week2_targets(out: Path) -> None:
    baseline = json.loads((RESULTS / "baseline.json").read_text(encoding="utf-8"))["metrics"]
    current = json.loads((RESULTS / "current.json").read_text(encoding="utf-8"))["metrics"]
    names = list(WEEK2_NAMES)[::-1]
    fig, ax = plt.subplots(figsize=(6.8, 3.0), facecolor=SURFACE)
    style(ax, grid_axis="x")
    for y, metric in enumerate(names):
        now, before = 100 * current[metric], 100 * baseline[metric]
        target = 100 * WEEK2_TARGETS[metric]
        ax.barh(y + 0.17, now, 0.3, color=BLUE, edgecolor=SURFACE, label="Atual")
        ax.barh(
            y - 0.17,
            before,
            0.3,
            color=BLUE,
            alpha=0.35,
            hatch="///",
            edgecolor=SURFACE,
            label="Baseline (sem política de escopo)",
        )
        ax.text(
            1.2,
            y + 0.17,
            pct(now, 2),
            ha="left",
            va="center",
            fontsize=8,
            color="white",
            fontweight="bold",
        )
        ax.text(1.2, y - 0.17, pct(before, 2), ha="left", va="center", fontsize=8, color=INK)
        ax.plot([target, target], [y - 0.38, y + 0.38], color=INK, linewidth=1.6)
        ax.text(
            target + 0.5, y + 0.42, f"meta {pct(target, 0)}", fontsize=7.5, color=INK_2, va="center"
        )
    ax.set_yticks(range(len(names)), [WEEK2_NAMES[m] for m in names])
    ax.set_xlim(0, 108)
    ax.set_xticks(range(0, 101, 20), [f"{v}%" for v in range(0, 101, 20)])
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles, strict=True))
    ax.legend(
        unique.values(),
        unique.keys(),
        ncol=2,
        frameon=False,
        fontsize=8,
        labelcolor=INK_2,
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
    )
    save(fig, out / "fig-metas.png")


def fig_alpha(out: Path) -> None:
    data = json.loads((RESULTS / "alpha_calibration.json").read_text(encoding="utf-8"))
    alphas = data["alpha"]
    recall = [100 * v for v in data["recall_at_3"]]
    grounded = [100 * v for v in data["grounded_accuracy"]]
    fig, ax = plt.subplots(figsize=(6.8, 3.0), facecolor=SURFACE)
    style(ax)
    for values, others, color, label in (
        (recall, grounded, BLUE, "Recall@3"),
        (grounded, recall, ORANGE, "Resposta fundamentada"),
    ):
        ax.plot(
            alphas,
            values,
            color=color,
            linewidth=2,
            marker="o",
            markersize=7,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=label,
        )
        for x, v, other in zip(alphas, values, others, strict=True):
            ax.text(
                x,
                v + 0.9 if v >= other else v - 1.9,
                pct(v, 2),
                ha="center",
                fontsize=7.5,
                color=INK,
                bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 0.6},
            )
    chosen = data["chosen_alpha"]
    ax.axvline(chosen, color=INK_2, linewidth=0.9, linestyle=(0, (4, 3)))
    ax.text(
        chosen + 0.01,
        83.6,
        f"α = {chosen:g}".replace(".", ",") + " (escolhido)",
        fontsize=8,
        color=INK_2,
        va="bottom",
    )
    ax.set_xticks(alphas, ["0\n(só TF-IDF)", "0,3", "0,5", "0,7", "1\n(só embeddings)"])
    ax.set_ylim(83, 102)
    ax.set_yticks(range(84, 101, 4), [f"{v}%" for v in range(84, 101, 4)])
    ax.set_xlabel(
        "Peso da similaridade densa (α); eixo vertical começa em 83%", color=INK_2, fontsize=8.5
    )
    legend_top(ax, ncol=2)
    save(fig, out / "fig-calibracao-alpha.png")


def fig_multiagent(run: dict, out: Path) -> None:
    """Novos painéis: sinalizações por caso, números e etapas executadas."""
    report = json.loads((run["_dir"] / "comparison_report.json").read_text(encoding="utf-8"))
    keys, labels, colors = run_styles(run)
    fig, ax = plt.subplots(figsize=(9, 2.5), facecolor=SURFACE)
    details = [report["methods"][key]["case_details"] for key in keys]
    values = [[int(bool(d["factual_inconsistencies"])) for d in group] for group in details]
    ax.imshow(values, cmap="Greys", vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xticks(range(len(details[0])), [d["id"] for d in details[0]], rotation=90)
    ax.tick_params(labelsize=8)
    ax.set_title(
        "Sinalização heurística por caso (escuro = sinalizado; sem confirmação humana)", fontsize=9
    )
    save(fig, out / "fig4-falhas-por-caso.png")

    multi = report["multiagent"]
    groups = [
        (name, data)
        for name, data in multi["categories"].items()
        if data["numeric_accuracy"] is not None
    ]
    fig, ax = plt.subplots(figsize=(6.8, 2.7), facecolor=SURFACE)
    style(ax)
    for i, (_, data) in enumerate(groups):
        value = data["numeric_accuracy"] * 100
        ax.bar(i, value, color="#52514e")
        ax.text(i, value + 1, pct(value), ha="center", fontsize=9)
    ax.set_xticks(range(len(groups)), [name for name, _ in groups])
    ax.set_ylim(0, 110)
    ax.set_ylabel("Números reproduzidos com unidade (%)")
    ax.set_title("Abstenções contam como números não reproduzidos", fontsize=9)
    save(fig, out / "fig5-acerto-numerico.png")

    latencies = multi["latency_per_agent"]
    fig, ax = plt.subplots(figsize=(6.8, 2.7), facecolor=SURFACE)
    style(ax)
    for i, (_, data) in enumerate(latencies.items()):
        value = data["mean_ms"]
        ax.bar(i, value, color="#52514e")
        ax.text(
            i,
            value,
            f"{value:.0f} ms\nn={data['executed_cases']}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.set_xticks(range(len(latencies)), list(latencies))
    ax.set_ylim(0, max((d["mean_ms"] for d in latencies.values()), default=1) * 1.4 or 1)
    ax.set_ylabel("Tempo médio (ms)")
    ax.set_title("Somente casos executados; revisões somadas por agente", fontsize=9)
    save(fig, out / "fig6-latencia-agentes.png")


def main() -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    runs = load_runs()
    for run in runs:
        out = OUT_DIR / run["run_id"]
        fig_metrics(run, out)
        fig_latency(run, out)
        if run.get("audit"):
            fig_audit(run, out)
        if "multiagent" in run:
            fig_multiagent(run, out)
    if len(runs) > 1:
        fig_across_runs(runs, OUT_DIR / "entre-execucoes")
    fig_week2_targets(OUT_DIR / "semana2")
    fig_alpha(OUT_DIR / "semana2")


if __name__ == "__main__":
    main()
