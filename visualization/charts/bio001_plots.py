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
    if result.get("id") == "EXO-001":
        fig = make_exo_figure(result, dark=dark)
    else:
        fig = make_figure_n(result, dark=dark) if result["A"]["q"].shape[1] > 2 else make_figure(result, dark=dark)
    FigureCanvasAgg(fig)
    fig.savefig(str(path), dpi=130, facecolor=fig.get_facecolor())


def make_passive_figure(result: dict, dark: bool = True) -> Figure:
    bg, fg, grid = (theme.PANEL, theme.TEXT, theme.PANEL2) if dark else ("white", "black", "#dddddd")
    a = result["A"]
    fig = Figure(figsize=(10, 6), facecolor=bg, layout="constrained")
    ax1, ax2 = fig.subplots(2, 1, sharex=True)
    ax1.plot(a["t"], np.degrees(a["q"][:, 0]), color=theme.BLUE, label="q1 (°, abs.)")
    ax1.plot(a["t"], np.degrees(a["q"][:, 1]), color=theme.CYAN, label="q2 (°, rel.)")
    ax2.plot(a["t"], a["energy"] - a["energy"][0], color=theme.WARN)
    ax1.set_ylabel("Ângulo (°)", color=fg, fontsize=7)
    ax2.set_ylabel("E − E0 (J)", color=fg, fontsize=7)
    ax2.set_xlabel("t (s)", color=fg, fontsize=7)
    for ax in (ax1, ax2):
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg, labelsize=7)
        ax.grid(True, color=grid, lw=0.6)
        for s in ax.spines.values():
            s.set_color(grid)
    ax1.legend(facecolor=bg, labelcolor=fg, fontsize=7, edgecolor=grid)
    fig.suptitle("SIM-001 — dinâmica passiva (parâmetros DEMONSTRATIVOS)", color=theme.WARN, fontsize=8)
    return fig


def make_figure_n(result: dict, dark: bool = True) -> Figure:
    """Gráficos para cadeias de N segmentos (BIO-002): linhas = ângulo, velocidade, torque; colunas = juntas."""
    bg, fg, grid = (theme.PANEL, theme.TEXT, theme.PANEL2) if dark else ("white", "black", "#dddddd")
    N = result["A"]["q"].shape[1]
    fig = Figure(figsize=(11, 7), facecolor=bg, layout="constrained")
    axes = fig.subplots(3, N, sharex=True, squeeze=False)
    rows = [("Ângulo (°)", lambda r: np.degrees(r["q"])), ("Vel. angular (°/s)", lambda r: np.degrees(r["qd"])),
            ("Torque (N·m)", lambda r: r["tau"])]
    for i, (yl, get) in enumerate(rows):
        for j in range(N):
            ax = axes[i][j]
            ax.set_facecolor(bg)
            for key, color in (("A", theme.BLUE), ("B", theme.CYAN)):
                ax.plot(result[key]["t"], get(result[key])[:, j], color=color, lw=1.6, label=f"Modelo {key}")
            if j == 0:
                ax.set_ylabel(yl, color=fg, fontsize=6.5)
            ax.tick_params(colors=fg, labelsize=6.5)
            ax.grid(True, color=grid, lw=0.6)
            for sp in ax.spines.values():
                sp.set_color(grid)
            if i == 0:
                ax.set_title(f"Junta {j+1}: {result['A']['joint_names'][j]} / {result['B']['joint_names'][j]}", color=fg, fontsize=7)
            if i == 2:
                ax.set_xlabel("t (s)", color=fg, fontsize=6.5)
    axes[0][0].legend(facecolor=bg, labelcolor=fg, fontsize=6.5, edgecolor=grid)
    fig.suptitle("BIO-002 — parâmetros DEMONSTRATIVOS", color=theme.WARN, fontsize=8)
    return fig


def make_exo_figure(result: dict, dark: bool = True) -> Figure:
    """EXO-001: torque da junta assistida (sem exo, com exo sem assistência, humano com assistência, atuador) e limite do atuador."""
    bg, fg, grid = (theme.PANEL, theme.TEXT, theme.PANEL2) if dark else ("white", "black", "#dddddd")
    a = result["A"]
    j = a["summary"]["joint_index"]
    fig = Figure(figsize=(10, 6), facecolor=bg, layout="constrained")
    ax1, ax2 = fig.subplots(2, 1, sharex=True)
    ax1.plot(a["t"], a["tau_baseline"][:, j], color=theme.TEXT2, lw=1.4, label="Requerido sem exo")
    ax1.plot(a["t"], a["tau_loaded"][:, j], color=theme.CYAN, lw=1.4, ls="--", label="Requerido com exo (sem assist.)")
    ax1.plot(a["t"], a["tau_human"][:, j], color=theme.BLUE, lw=1.8, label="Humano com assistência")
    ax1.set_ylabel("Torque (N·m)", color=fg, fontsize=7)
    ax2.plot(a["t"], a["tau_exo"], color=theme.WARN, lw=1.6, label="Atuador")
    ax2.plot(a["t"], a["tau_limit"], color=grid, lw=1.0, ls=":", label="Limite τ-ω (+)")
    ax2.plot(a["t"], -a["tau_limit"], color=grid, lw=1.0, ls=":")
    ax2.set_ylabel("Atuador (N·m)", color=fg, fontsize=7)
    ax2.set_xlabel("t (s)", color=fg, fontsize=7)
    for ax in (ax1, ax2):
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg, labelsize=7)
        ax.grid(True, color=grid, lw=0.6)
        for sp in ax.spines.values():
            sp.set_color(grid)
        ax.legend(facecolor=bg, labelcolor=fg, fontsize=6.5, edgecolor=grid)
    fig.suptitle("EXO-001 — exoesqueleto, parâmetros DEMONSTRATIVOS", color=theme.WARN, fontsize=8)
    return fig
