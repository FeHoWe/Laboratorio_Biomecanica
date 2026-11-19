"""Controlador de reprodução (independente de Qt/VTK): mapeia tempo de parede → quadro da simulação.

Nenhum estado físico é inventado: só se escolhe o índice de uma Trajectory já calculada (t_sim, q, ...). O tempo simulado avança
`speed × Δt_parede`. Ao fim: para (loop=False) ou reinicia (loop=True).
"""
from __future__ import annotations

import numpy as np

from core.exceptions import NexusError

SPEEDS = (0.1, 0.25, 0.5, 1.0, 2.0, 4.0)


class PlaybackError(NexusError):
    pass


class PlaybackController:
    def __init__(self, t) -> None:
        t = np.asarray(t, float)
        if t.ndim != 1 or len(t) < 2 or not np.all(np.diff(t) > 0):
            raise PlaybackError("Tempos de reprodução devem ser estritamente crescentes (≥ 2 amostras)")
        self.t = t
        self.playing = False
        self.speed = 1.0
        self.loop = False
        self.time = float(t[0])

    def set_speed(self, s: float) -> None:
        if not (0 < s <= 100):
            raise PlaybackError("velocidade deve estar em (0, 100]")
        self.speed = float(s)

    def play(self) -> None:
        if self.time >= self.t[-1]:
            self.time = float(self.t[0])
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def restart(self) -> None:
        self.time = float(self.t[0])

    def seek(self, time_s: float) -> int:
        self.time = float(np.clip(time_s, self.t[0], self.t[-1]))
        return self.index

    @property
    def index(self) -> int:
        """Quadro mais próximo do tempo atual."""
        i = int(np.searchsorted(self.t, self.time))
        if i == 0:
            return 0
        return i if i < len(self.t) and abs(self.t[i] - self.time) < abs(self.t[i - 1] - self.time) else i - 1

    def advance(self, wall_dt_s: float) -> int:
        if wall_dt_s < 0:
            raise PlaybackError("Δt de parede não pode ser negativo")
        if self.playing:
            self.time += self.speed * wall_dt_s
            if self.time >= self.t[-1]:
                if self.loop:
                    self.time = float(self.t[0]) + (self.time - self.t[0]) % (self.t[-1] - self.t[0])
                else:
                    self.time, self.playing = float(self.t[-1]), False
        return self.index

    @property
    def finished(self) -> bool:
        return self.time >= self.t[-1]
