"""Tests for new config variables added in v2."""
import sys
import importlib

import pytest


@pytest.fixture(autouse=True)
def fresh_config():
    """Reload config module before and after each test to isolate env state."""
    if "config" in sys.modules:
        del sys.modules["config"]
    yield
    if "config" in sys.modules:
        del sys.modules["config"]


def test_llama_base_url_default(monkeypatch):
    monkeypatch.delenv("LLAMA_BASE_URL", raising=False)
    import config
    assert config.Config.LLAMA_BASE_URL == "http://localhost:8080"


def test_llama_model_default(monkeypatch):
    monkeypatch.delenv("LLAMA_MODEL", raising=False)
    import config
    assert config.Config.LLAMA_MODEL == "qwen3-vl-8b"


def test_output_folder_defaults_empty(monkeypatch):
    monkeypatch.delenv("OUTPUT_FOLDER", raising=False)
    import config
    assert config.Config.OUTPUT_FOLDER == ""


def test_input_folder_defaults_to_image_folder(monkeypatch):
    monkeypatch.delenv("INPUT_FOLDER", raising=False)
    monkeypatch.setenv("IMAGE_FOLDER", "/tmp/test-images")
    import config
    assert config.Config.INPUT_FOLDER == "/tmp/test-images"


def test_llama_timeout_inherits_ollama_timeout_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT", "60")
    import config
    assert config.Config.LLAMA_TIMEOUT == 60
