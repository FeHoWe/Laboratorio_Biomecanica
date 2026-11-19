"""Relatório PDF (matplotlib PdfPages): páginas de texto + gráficos."""
from __future__ import annotations

import textwrap
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from core.exceptions import NexusError
from research.experiments import bio001
from visualization.charts.bio001_plots import make_figure

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


def export_pdf(result: dict, path: Path | str) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with PdfPages(tmp) as pdf:
            for fig in _text_pages(bio001.report_markdown(result)):
                pdf.savefig(fig)
            pdf.savefig(make_figure(result, dark=False))
            info = pdf.infodict()
            info["Title"] = "BIO-001 — Comparative Joint Mechanics"
            info["Creator"] = "NEXUS BIOMECHANICS"
        tmp.replace(path)
    except OSError as exc:
        raise NexusError(f"Falha ao gerar PDF: {exc}") from exc
