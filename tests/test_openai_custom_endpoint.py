"""Tests for CUSTOM_OPENAI_URL / CUSTOM_OPEN_AI_KEY env-var overrides.

Two env vars let users route any OpenAI-compatible client through a custom
endpoint and key — useful for proxies, self-hosted gateways, etc. These tests
verify:
  1. Both vars override provider defaults when set.
  2. Partial overrides (URL only / key only) let the other field fall back.
  3. Neither set → normal provider resolution works.
"""

from __future__ import annotations

import importlib

import pytest


def _reload_client():
    import tradingagents.llm_clients.openai_client as mod
    return importlib.reload(mod)


# ---- absolute override -----------------------------------------------------


class TestCustomOverride:
    """CUSTOM_OPENAI_URL / CUSTOM_OPEN_AI_KEY take absolute precedence."""

    def test_both_vars_override_provider_defaults(self, monkeypatch):
        """Both env vars win over a known provider's built-in defaults."""
        monkeypatch.setenv("CUSTOM_OPENAI_URL", "https://my-proxy.example.com/v1")
        monkeypatch.setenv("CUSTOM_OPEN_AI_KEY", "sk-custom-abc123")
        mod = _reload_client()
        client = mod.OpenAIClient(model="grok-3", provider="xai")
        llm = client.get_llm()
        assert "my-proxy.example.com" in str(llm.openai_api_base)
        assert "sk-custom-abc123" in llm.openai_api_key.get_secret_value()

    def test_url_override_uses_provider_key(self, monkeypatch):
        """URL overridden; API key falls back to the provider-specific env var."""
        monkeypatch.setenv("CUSTOM_OPENAI_URL", "https://my-proxy.example.com/v1")
        monkeypatch.delenv("CUSTOM_OPEN_AI_KEY", raising=False)
        mod = _reload_client()
        client = mod.OpenAIClient(model="grok-3", provider="xai")
        llm = client.get_llm()
        assert "my-proxy.example.com" in str(llm.openai_api_base)
        # conftest._dummy_api_keys sets XAI_API_KEY to "placeholder"
        assert llm.openai_api_key.get_secret_value() == "placeholder"

    def test_key_override_uses_provider_url(self, monkeypatch):
        """API key overridden; base URL falls back to provider default."""
        monkeypatch.delenv("CUSTOM_OPENAI_URL", raising=False)
        monkeypatch.setenv("CUSTOM_OPEN_AI_KEY", "sk-override-xyz")
        mod = _reload_client()
        client = mod.OpenAIClient(model="grok-3", provider="xai")
        llm = client.get_llm()
        assert "api.x.ai" in str(llm.openai_api_base)
        assert llm.openai_api_key.get_secret_value() == "sk-override-xyz"

    def test_fallback_to_provider_defaults(self, monkeypatch):
        """Neither custom var set → known provider uses its own defaults."""
        monkeypatch.delenv("CUSTOM_OPENAI_URL", raising=False)
        monkeypatch.delenv("CUSTOM_OPEN_AI_KEY", raising=False)
        mod = _reload_client()
        client = mod.OpenAIClient(model="grok-3", provider="xai")
        llm = client.get_llm()
        assert "api.x.ai" in str(llm.openai_api_base)
        assert llm.openai_api_key.get_secret_value() == "placeholder"


class TestCustomFallback:
    """CUSTOM env vars absent → normal provider resolution still works."""

    def test_openai_provider_no_custom_vars(self, monkeypatch):
        """OpenAI provider without custom vars uses env key (no base_url set)."""
        monkeypatch.delenv("CUSTOM_OPENAI_URL", raising=False)
        monkeypatch.delenv("CUSTOM_OPEN_AI_KEY", raising=False)
        mod = _reload_client()
        client = mod.OpenAIClient(model="gpt-4", provider="openai")
        llm = client.get_llm()
        # "openai" is not in _PROVIDER_BASE_URL so no base_url is written to
        # llm_kwargs — ChatOpenAI uses its own default.
        # api_key comes from OPENAI_API_KEY (set to "placeholder" by conftest).
        assert llm.openai_api_key.get_secret_value() == "placeholder"

    def test_deepseek_provider_no_custom_vars(self, monkeypatch):
        """DeepSeek without custom vars uses its built-in base and env key."""
        monkeypatch.delenv("CUSTOM_OPENAI_URL", raising=False)
        monkeypatch.delenv("CUSTOM_OPEN_AI_KEY", raising=False)
        mod = _reload_client()
        client = mod.OpenAIClient(model="deepseek-chat", provider="deepseek")
        llm = client.get_llm()
        assert "api.deepseek.com" in str(llm.openai_api_base)
        assert llm.openai_api_key.get_secret_value() == "placeholder"

    def test_custom_vars_with_openai(self, monkeypatch):
        """Custom vars also work when provider is 'openai' (not in _PROVIDER_BASE_URL)."""
        monkeypatch.setenv("CUSTOM_OPENAI_URL", "https://openai-gateway.example.com/v1")
        monkeypatch.setenv("CUSTOM_OPEN_AI_KEY", "sk-gateway-key")
        mod = _reload_client()
        client = mod.OpenAIClient(model="gpt-4", provider="openai")
        llm = client.get_llm()
        assert "openai-gateway.example.com" in str(llm.openai_api_base)
        assert llm.openai_api_key.get_secret_value() == "sk-gateway-key"



class TestCustomEdgeCases:
    """Corner cases for the custom endpoint logic."""

    def test_explicit_base_url_still_overridden_by_custom_url(self, monkeypatch):
        """Even an explicit ``base_url`` passed to the client loses to CUSTOM_OPENAI_URL."""
        monkeypatch.setenv("CUSTOM_OPENAI_URL", "https://override.example.com/v1")
        monkeypatch.delenv("CUSTOM_OPEN_AI_KEY", raising=False)
        mod = _reload_client()
        client = mod.OpenAIClient(
            model="grok-3",
            provider="xai",
            base_url="https://explicit.example.com/v1",
        )
        llm = client.get_llm()
        assert "override.example.com" in str(llm.openai_api_base)
        assert "explicit.example.com" not in str(llm.openai_api_base)
