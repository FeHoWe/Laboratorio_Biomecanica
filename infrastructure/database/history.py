"""Histórico de experimentos em SQLite (arquivo history.db dentro da pasta do projeto).

O banco é um ÍNDICE derivado do project.json: pode ser apagado e é reconstruído a cada abrir/salvar.
Permite consultar experimentos por tipo e ordenar/filtrar por métrica numérica do resumo.
"""
from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path

from core.exceptions import NexusError

DB_FILE = "history.db"
SCHEMA_VERSION = 1


class HistoryError(NexusError):
    pass


def flatten_metrics(summary: dict) -> dict[str, float]:
    """Achata um resumo em {caminho: número}. Listas viram 'chave[i]'; textos, booleanos e não finitos são ignorados."""
    out: dict[str, float] = {}

    def walk(prefix: str, v) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            if math.isfinite(v):
                out[prefix] = float(v)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(f"{prefix}.{k}" if prefix else str(k), x)
        elif isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                walk(f"{prefix}[{i}]", x)

    walk("", summary)
    return out


class ExperimentHistory:
    def __init__(self, db_path: Path | str) -> None:
        self.path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def _init(self, con: sqlite3.Connection) -> None:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS experiments(
                id TEXT PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL, created TEXT NOT NULL,
                params_json TEXT NOT NULL, summary_json TEXT NOT NULL, results_file TEXT);
            CREATE TABLE IF NOT EXISTS metrics(
                exp_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                key TEXT NOT NULL, value REAL NOT NULL, PRIMARY KEY(exp_id, key));
            CREATE INDEX IF NOT EXISTS idx_metrics_key ON metrics(key);
            CREATE INDEX IF NOT EXISTS idx_exp_type ON experiments(type);""")
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def rebuild(self, project_data: dict) -> int:
        """Substitui o conteúdo pelo estado do projeto (transação única). Retorna nº de experimentos."""
        try:
            with closing(self._connect()) as con:
                self._init(con)
                with con:
                    con.execute("DELETE FROM metrics")
                    con.execute("DELETE FROM experiments")
                    for e in project_data.get("experiments", []):
                        con.execute("INSERT INTO experiments VALUES(?,?,?,?,?,?,?)",
                                    (e["id"], e["type"], e["name"], e["created"], json.dumps(e["params"]),
                                     json.dumps(e["summary"]), e.get("results_file")))
                        con.executemany("INSERT INTO metrics VALUES(?,?,?)",
                                        [(e["id"], k, v) for k, v in flatten_metrics(e["summary"]).items()])
                return len(project_data.get("experiments", []))
        except (sqlite3.Error, KeyError, OSError) as exc:
            raise HistoryError(f"Falha ao atualizar histórico: {exc}") from exc

    def list_experiments(self, exp_type: str | None = None, metric: str | None = None,
                         order_desc: bool = False, only_with_metric: bool = False) -> list[dict]:
        """Experimentos (mais antigos primeiro) com o valor da métrica escolhida (ou None). Com metric, ordena por ela."""
        sql = ("SELECT e.id, e.type, e.name, e.created, m.value FROM experiments e "
               "LEFT JOIN metrics m ON m.exp_id = e.id AND m.key = ?")
        args: list = [metric or ""]
        where = []
        if exp_type:
            where.append("e.type = ?")
            args.append(exp_type)
        if metric and only_with_metric:
            where.append("m.value IS NOT NULL")
        if where:
            sql += " WHERE " + " AND ".join(where)
        if metric:
            sql += f" ORDER BY m.value IS NULL, m.value {'DESC' if order_desc else 'ASC'}, e.created, e.id"
        else:
            sql += " ORDER BY e.created, e.id"
        try:
            with closing(self._connect()) as con:
                rows = con.execute(sql, args).fetchall()
        except sqlite3.Error as exc:
            raise HistoryError(f"Falha ao consultar histórico: {exc}") from exc
        return [{"id": r[0], "type": r[1], "name": r[2], "created": r[3], "value": r[4]} for r in rows]

    def metric_names(self, exp_type: str | None = None) -> list[str]:
        sql = "SELECT DISTINCT m.key FROM metrics m JOIN experiments e ON e.id = m.exp_id"
        args: list = []
        if exp_type:
            sql += " WHERE e.type = ?"
            args.append(exp_type)
        try:
            with closing(self._connect()) as con:
                return sorted(r[0] for r in con.execute(sql, args))
        except sqlite3.Error as exc:
            raise HistoryError(f"Falha ao consultar métricas: {exc}") from exc

    def types(self) -> list[str]:
        try:
            with closing(self._connect()) as con:
                return [r[0] for r in con.execute("SELECT DISTINCT type FROM experiments ORDER BY type")]
        except sqlite3.Error as exc:
            raise HistoryError(f"Falha ao consultar tipos: {exc}") from exc
