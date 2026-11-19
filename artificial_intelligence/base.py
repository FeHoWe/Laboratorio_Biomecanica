"""Contratos do módulo de IA (somente arquitetura).

Princípios (do master prompt): nada de resultado inventado; toda saída de IA é rotulada como tal, com procedência
(provedor, modelo, parâmetros) e limitações; saídas de IA NUNCA entram nos cálculos nem são tratadas como validação científica.
O núcleo não depende de nenhum provedor: um provedor concreto (modelo local, API) é um plugin que implementa `Analyzer`.
"""
from __future__ import annotations

import abc
import json
from dataclasses import dataclass, field

from core.exceptions import NexusError

AI_LABEL = "Gerado por IA — não validado; não use como evidência clínica ou científica sem verificação humana."


class AiAnalysisError(NexusError):
    pass


@dataclass(frozen=True)
class AnalysisRequest:
    experiment_id: str
    experiment_type: str
    params: dict
    summary: dict
    messages: list = field(default_factory=list)
    question: str = ""

    def to_json(self) -> str:
        return json.dumps({"experiment_id": self.experiment_id, "type": self.experiment_type, "params": self.params,
                           "summary": self.summary, "messages": self.messages, "question": self.question}, sort_keys=True)


@dataclass(frozen=True)
class AnalysisResult:
    text: str
    provider: str
    model: str
    limitations: list
    label: str = AI_LABEL

    def validate(self) -> None:
        if not self.text.strip() or not self.provider or not self.model:
            raise AiAnalysisError("Resultado de IA incompleto: texto, provedor e modelo são obrigatórios")
        if not self.limitations:
            raise AiAnalysisError("Resultado de IA deve declarar limitações")


class Analyzer(abc.ABC):
    """Provedor de análise. Implementações devem ser determinísticas ou declarar que não são."""
    name: str = ""
    model: str = ""

    @abc.abstractmethod
    def analyze(self, request: AnalysisRequest) -> AnalysisResult: ...


class AnalyzerRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Analyzer] = {}

    def register(self, analyzer: Analyzer) -> None:
        if not analyzer.name or not analyzer.model:
            raise AiAnalysisError("Analyzer precisa de 'name' e 'model'")
        if analyzer.name in self._items:
            raise AiAnalysisError(f"Provedor já registrado: {analyzer.name}")
        self._items[analyzer.name] = analyzer

    def names(self) -> list[str]:
        return sorted(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def run(self, name: str, request: AnalysisRequest) -> AnalysisResult:
        if name not in self._items:
            raise AiAnalysisError(f"Provedor desconhecido: {name}")
        try:
            res = self._items[name].analyze(request)
        except AiAnalysisError:
            raise
        except Exception as exc:  # provedor externo: erro tratado, nunca derruba o app
            raise AiAnalysisError(f"Falha no provedor {name}: {exc}") from exc
        res.validate()
        return res


def request_from_result(result: dict, question: str = "") -> AnalysisRequest:
    """Monta o pedido a partir de um resultado de experimento (só resumo e parâmetros; sem séries temporais)."""
    summ = result.get("A", {}).get("summary") if "A" in result else None
    full = {"A": result["A"]["summary"]} if "A" in result else {}
    if "B" in result:
        full["B"] = result["B"]["summary"]
    return AnalysisRequest(result["id"], result["id"], result.get("params", {}), full if summ is not None else {},
                           list(result.get("messages", [])), question)
