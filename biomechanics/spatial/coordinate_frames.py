"""Árvore de referenciais: global (mundo) e locais, com conversão de pontos e vetores entre eles."""
from __future__ import annotations

import numpy as np

from biomechanics.spatial import transforms as T
from core.exceptions import NexusError

WORLD = "world"


class FrameError(NexusError):
    pass


class FrameTree:
    def __init__(self) -> None:
        self._parent: dict[str, str | None] = {WORLD: None}
        self._local: dict[str, np.ndarray] = {WORLD: np.eye(4)}

    def add(self, name: str, parent: str, T_parent_frame: np.ndarray) -> None:
        if name in self._parent:
            raise FrameError(f"Referencial já existe: {name}")
        if parent not in self._parent:
            raise FrameError(f"Referencial pai desconhecido: {parent}")
        if not T.is_transform(T_parent_frame):
            raise FrameError(f"Transformação inválida para {name}")
        self._parent[name], self._local[name] = parent, np.array(T_parent_frame, float)

    def set_local(self, name: str, T_parent_frame: np.ndarray) -> None:
        if name not in self._parent or name == WORLD:
            raise FrameError(f"Referencial inválido para alteração: {name}")
        if not T.is_transform(T_parent_frame):
            raise FrameError(f"Transformação inválida para {name}")
        self._local[name] = np.array(T_parent_frame, float)

    def names(self) -> list[str]:
        return list(self._parent)

    def world(self, name: str) -> np.ndarray:
        """T_mundo←name."""
        if name not in self._parent:
            raise FrameError(f"Referencial desconhecido: {name}")
        out = np.eye(4)
        cur: str | None = name
        while cur is not None:
            out = self._local[cur] @ out
            cur = self._parent[cur]
        return out

    def relative(self, src: str, dst: str) -> np.ndarray:
        """T_dst←src: converte coordenadas expressas em `src` para coordenadas em `dst`."""
        return T.invert(self.world(dst)) @ self.world(src)

    def point(self, p, src: str, dst: str) -> np.ndarray:
        return T.apply(self.relative(src, dst), p)

    def vector(self, v, src: str, dst: str) -> np.ndarray:
        return T.apply_vector(self.relative(src, dst), v)
