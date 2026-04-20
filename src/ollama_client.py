"""
Backward-compatibility shim.

All logic has moved to llama_client.py. This module re-exports the same
names so that existing imports (from ollama_client import OllamaClient) continue
to work without changes.
"""

from llama_client import (  # noqa: F401
    LlamaClient as OllamaClient,
    LlamaConnectionError as OllamaConnectionError,
    LlamaResponseError as OllamaResponseError,
)
