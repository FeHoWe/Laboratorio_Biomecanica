import pytest

from artificial_intelligence.base import (AI_LABEL, AiAnalysisError, AnalysisRequest, AnalysisResult, Analyzer, AnalyzerRegistry,
                              request_from_result)
from research.experiments import bio001


class Fake(Analyzer):
    name, model = "fake", "fake-1"

    def analyze(self, request):
        return AnalysisResult(f"resumo de {request.experiment_id}", self.name, self.model, ["apenas teste"])


class Broken(Analyzer):
    name, model = "broken", "x"

    def analyze(self, request):
        raise RuntimeError("rede caiu")


class Incomplete(Analyzer):
    name, model = "inc", "x"

    def analyze(self, request):
        return AnalysisResult("texto", "inc", "x", [])


def test_registry_rules():
    r = AnalyzerRegistry()
    assert len(r) == 0 and r.names() == []
    r.register(Fake())
    with pytest.raises(AiAnalysisError):
        r.register(Fake())
    with pytest.raises(AiAnalysisError):
        r.run("nao_existe", AnalysisRequest("x", "x", {}, {}))
    req = request_from_result(bio001.run(bio001.default_params()), "pergunta")
    res = r.run("fake", req)
    assert res.label == AI_LABEL and "BIO-001" in res.text and "não validado" in res.label


def test_provider_failures_are_handled_and_incomplete_rejected():
    r = AnalyzerRegistry()
    r.register(Broken())
    r.register(Incomplete())
    with pytest.raises(AiAnalysisError, match="rede caiu"):
        r.run("broken", AnalysisRequest("x", "x", {}, {}))
    with pytest.raises(AiAnalysisError, match="limitações"):
        r.run("inc", AnalysisRequest("x", "x", {}, {}))


def test_request_has_summary_only_and_is_deterministic_json():
    res = bio001.run(bio001.default_params())
    a, b = request_from_result(res), request_from_result(res)
    assert a.to_json() == b.to_json() and set(a.summary) == {"A", "B"}
    assert len(a.to_json()) < 20000  # só resumo/parâmetros, sem séries temporais completas
