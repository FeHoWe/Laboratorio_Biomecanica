"""Relatório PDF (matplotlib PdfPages): páginas de texto + gráficos."""
from __future__ import annotations

import textwrap
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from core.exceptions import NexusError
from research.experiments import bio001, bio002
from visualization.charts.bio001_plots import make_exo_figure, make_figure, make_figure_n

LINES_PER_PAGE = 52


def _text_pages(md: str) -> list[Figure]:
    lines: list[str] = []
    for raw in md.splitlines():
        raw = raw.replace("**", "").replace("`", "").lstrip("#> ").rstrip()
        lines += textwrap.wrap(raw, 95) or [""]
    pages = []
    for i in range(0, len(lines), LINES_PER_PAGE):
        fig = Figure(figsize=(8.27, 11.69))  # A4
        fig.text(0.07, 0.96, "\n".join(lines[i:i + LINES_PER_PAGE]), va="top", family="monospace", fontsize=8)
        fig.text(0.5, 0.02, f"NEXUS BIOMECHANICS — página {i // LINES_PER_PAGE + 1}", ha="center", fontsize=7)
        pages.append(fig)
    return pages


def _spec(result: dict):
    """(markdown, figura, título) conforme o experimento; levanta NexusError se não houver PDF para ele."""
    rid = result.get("id")
    if rid == bio001.EXPERIMENT_ID:
        return bio001.report_markdown(result), make_figure(result, dark=False), "BIO-001 — Comparative Joint Mechanics"
    if rid == bio002.EXPERIMENT_ID:
        return bio002.report_markdown(result), make_figure_n(result, dark=False), "BIO-002 — Comparative Joint Mechanics (3 segmentos)"
    if rid == "EXO-001":
        from exoskeleton.analysis import assist
        return assist.report_markdown(result), make_exo_figure(result, dark=False), "EXO-001 — Assistência articular por exoesqueleto"
    raise NexusError(f"Relatório PDF não disponível para {rid}")


def export_pdf(result: dict, path: Path | str) -> None:
    md, fig_res, title = _spec(result)
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with PdfPages(tmp) as pdf:
            for fig in _text_pages(md):
                pdf.savefig(fig)
            pdf.savefig(fig_res)
            info = pdf.infodict()
            info["Title"] = title
            info["Creator"] = "NEXUS BIOMECHANICS"
        tmp.replace(path)
    except OSError as exc:
        raise NexusError(f"Falha ao gerar PDF: {exc}") from exc
