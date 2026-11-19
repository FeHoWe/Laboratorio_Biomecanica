"""Gráficos do BIO-001 (matplotlib, sem pyplot -> seguro para uso em threads/GUI)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from interface import theme


def make_figure(result: dict, dark: bool = True) -> Figure:
    bg, fg, grid = (theme.PANEL, theme.TEXT, theme.PANEL2) if dark else ("white", "black", "#dddddd")
    fig = Figure(figsize=(10, 7), facecolor=bg, layout="constrained")
    rows = [("Ângulo (°)", lambda r: np.degrees(r["q"])),
            ("Vel. angular (°/s)", lambda r: np.degrees(r["qd"])),
            ("Torque (N·m)", lambda r: r["tau"])]
    axes = fig.subplots(3, 2, sharex=True)
    for i, (ylabel, getter) in enumerate(rows):
        for j in range(2):
            ax = axes[i][j]
            ax.set_facecolor(bg)
            for key, color in (("A", theme.BLUE), ("B", theme.CYAN)):
                r = result[key]
                ax.plot(r["t"], getter(r)[:, j], color=color, lw=1.8, label=f"Modelo {key}")
            ax.set_ylabel(ylabel, color=fg, fontsize=6.5)
            ax.tick_params(colors=fg, labelsize=6.5)
            ax.grid(True, color=grid, lw=0.6)
            for s in ax.spines.values():
                s.set_color(grid)
            if i == 0:
                ax.set_title("Junta 1 (proximal)" if j == 0 else "Junta 2 (joelho / jarrete)",
                             color=fg, fontsize=7)
            if i == 2:
                ax.set_xlabel("t (s)", color=fg, fontsize=6.5)
    axes[0][0].legend(facecolor=bg, labelcolor=fg, fontsize=6.5, edgecolor=grid)
    fig.suptitle("BIO-001 — parâmetros DEMONSTRATIVOS", color=theme.WARN, fontsize=8)
    return fig


def save_png(result: dict, path: Path | str, dark: bool = False) -> None:
    fig = make_figure(result, dark=dark)
    FigureCanvasAgg(fig)
    fig.savefig(str(path), dpi=130, facecolor=fig.get_facecolor())
