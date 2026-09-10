import sys
from types import SimpleNamespace

from app.providers import enhance_result


def test_missing_credentials_falls_back(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    result, provider, warnings = enhance_result("test", {"value": 1})
    assert result == {"value": 1}
    assert provider == "mock-fallback"
    assert warnings


def test_timeout_falls_back(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            raise TimeoutError("simulated")

    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    result, provider, warnings = enhance_result("test", {"value": 2})
    assert result == {"value": 2}
    assert provider == "mock-fallback"
    assert "TimeoutError" in warnings[0]


def test_malformed_model_output_falls_back(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            return SimpleNamespace(output_text="not-json")

    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    result, provider, warnings = enhance_result("test", {"value": 3})
    assert result == {"value": 3}
    assert provider == "mock-fallback"
    assert "JSONDecodeError" in warnings[0]

