"""Leitura de malhas STL (binário e ASCII) com validação e estatísticas geométricas.

Sem dependências além de NumPy. Limites defensivos: arquivo <= 200 MB, <= 2.000.000 triângulos.
O volume só é reportado se a malha for fechada (cada aresta compartilhada por exatamente 2 triângulos).
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.exceptions import NexusError

MAX_BYTES = 200 * 1024 * 1024
MAX_TRIANGLES = 2_000_000


class StlError(NexusError):
    pass


@dataclass
class StlMesh:
    vertices: np.ndarray   # (V, 3) float64, unidades do arquivo
    faces: np.ndarray      # (F, 3) int64

    @property
    def n_triangles(self) -> int:
        return int(len(self.faces))

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return self.vertices.min(axis=0), self.vertices.max(axis=0)

    def area(self) -> float:
        t = self.vertices[self.faces]
        return float(0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum())

    def is_closed(self) -> bool:
        e = np.sort(np.concatenate([self.faces[:, [0, 1]], self.faces[:, [1, 2]], self.faces[:, [2, 0]]]), axis=1)
        _, counts = np.unique(e, axis=0, return_counts=True)
        return bool(np.all(counts == 2))

    def volume(self) -> float | None:
        if not self.is_closed():
            return None
        t = self.vertices[self.faces]
        return float(abs(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6.0))

    def stats(self) -> dict:
        lo, hi = self.bounds()
        vol = self.volume()
        return {"triangles": self.n_triangles, "vertices": int(len(self.vertices)),
                "bounds_min": [float(x) for x in lo], "bounds_max": [float(x) for x in hi],
                "area": self.area(), "closed": self.is_closed(), "volume": vol}

    def scaled(self, factor: float) -> "StlMesh":
        return StlMesh(self.vertices * factor, self.faces)


def _weld(tri: np.ndarray) -> StlMesh:
    flat = tri.reshape(-1, 3)
    verts, inv = np.unique(flat, axis=0, return_inverse=True)
    return StlMesh(verts.astype(np.float64), inv.reshape(-1, 3).astype(np.int64))


def _parse_binary(raw: bytes) -> np.ndarray:
    n = struct.unpack("<I", raw[80:84])[0]
    if n == 0 or n > MAX_TRIANGLES:
        raise StlError(f"Número de triângulos inválido ou acima do limite ({MAX_TRIANGLES}): {n}")
    if len(raw) != 84 + 50 * n:
        raise StlError("STL binário inconsistente: tamanho do arquivo não corresponde ao número de triângulos")
    dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    return np.frombuffer(raw, dtype=dt, count=n, offset=84)["v"].astype(np.float64)


def _parse_ascii(text: str) -> np.ndarray:
    nums = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text)
    if not nums or len(nums) % 3:
        raise StlError("STL ASCII inválido: número de vértices não é múltiplo de 3")
    if len(nums) // 3 > MAX_TRIANGLES:
        raise StlError(f"Triângulos acima do limite ({MAX_TRIANGLES})")
    try:
        arr = np.array(nums, dtype=np.float64)
    except ValueError as exc:
        raise StlError("STL ASCII com valor numérico inválido") from exc
    return arr.reshape(-1, 3, 3)


def load_stl(path: Path | str) -> StlMesh:
    path = Path(path)
    try:
        if path.stat().st_size > MAX_BYTES:
            raise StlError(f"Arquivo acima do limite de {MAX_BYTES // 2**20} MB")
        raw = path.read_bytes()
    except OSError as exc:
        raise StlError(f"Não foi possível ler {path}: {exc}") from exc
    if len(raw) < 15:
        raise StlError("Arquivo muito pequeno para ser um STL")
    # binário se o tamanho bate com o cabeçalho (arquivos ASCII podem começar com 'solid' também)
    is_bin = len(raw) >= 84 and len(raw) == 84 + 50 * struct.unpack("<I", raw[80:84])[0]
    if is_bin:
        tri = _parse_binary(raw)
    elif raw.lstrip()[:5].lower() == b"solid":
        tri = _parse_ascii(raw.decode("utf-8", errors="replace"))
    else:
        raise StlError("Formato não reconhecido (nem STL binário válido nem ASCII)")
    if not np.all(np.isfinite(tri)):
        raise StlError("STL contém coordenadas não finitas (NaN/Inf)")
    mesh = _weld(tri)
    # remove triângulos degenerados (dois vértices iguais)
    f = mesh.faces
    keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    if not keep.any():
        raise StlError("STL sem triângulos válidos (todos degenerados)")
    return StlMesh(mesh.vertices, f[keep])


def write_binary_stl(mesh: StlMesh, path: Path | str, header: str = "NEXUS BIOMECHANICS") -> None:
    t = mesh.vertices[mesh.faces].astype("<f4")
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.divide(nrm, ln, out=np.zeros_like(nrm), where=ln > 0).astype("<f4")
    dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    arr = np.zeros(len(t), dtype=dt)
    arr["n"], arr["v"] = nrm, t
    Path(path).write_bytes(header.encode("ascii", "ignore")[:80].ljust(80, b" ") + struct.pack("<I", len(t)) + arr.tobytes())
