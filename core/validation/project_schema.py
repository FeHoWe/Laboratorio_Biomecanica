"""Validação do formato de projeto NEXUS (project.json)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from core.exceptions import ProjectValidationError

FORMAT_ID = "nexus-biomechanics-project"
SCHEMA_VERSION = 1
MAX_NAME = 120


def _need(data: dict, key: str, typ: type) -> Any:
    if key not in data:
        raise ProjectValidationError(f"Campo obrigatório ausente: '{key}'")
    if not isinstance(data[key], typ) or (typ is int and isinstance(data[key], bool)):
        raise ProjectValidationError(
            f"Campo '{key}' deve ser {typ.__name__}, recebido {type(data[key]).__name__}"
        )
    return data[key]


def validate_project_dict(data: Any) -> dict:
    """Valida o dicionário; devolve-o se válido, senão levanta ProjectValidationError."""
    if not isinstance(data, dict):
        raise ProjectValidationError("Raiz do projeto deve ser um objeto JSON")
    if _need(data, "format", str) != FORMAT_ID:
        raise ProjectValidationError(f"Formato desconhecido: {data['format']!r}")
    version = _need(data, "schema_version", int)
    if version < 1 or version > SCHEMA_VERSION:
        raise ProjectValidationError(
            f"schema_version {version} não suportado (máximo {SCHEMA_VERSION})"
        )
    _need(data, "id", str)
    name = _need(data, "name", str).strip()
    if not name or len(name) > MAX_NAME:
        raise ProjectValidationError(f"Nome deve ter 1 a {MAX_NAME} caracteres")
    _need(data, "description", str)
    for key in ("created", "modified"):
        try:
            datetime.fromisoformat(_need(data, key, str))
        except ValueError as exc:
            raise ProjectValidationError(f"Data inválida em '{key}'") from exc
    for key in ("models", "experiments"):
        items = _need(data, key, list)
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ProjectValidationError(f"Itens de '{key}' precisam ser objetos com 'name'")
    _need(data, "settings", dict)
    return data
