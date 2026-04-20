"""
llama-server / llama-swap REST client using OpenAI-compatible API.

Drop-in replacement for OllamaClient. Works with any server that exposes
the OpenAI /v1/chat/completions and /v1/models endpoints.
"""

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import requests

from config import Config

logger = logging.getLogger(__name__)

# Substrings that identify a vision-capable model by name
_VISION_PATTERNS = ("vl", "vision", "gemma4", "mmproj")

# Map file extensions to MIME types for the image data URL
_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class LlamaConnectionError(Exception):
    """Raised when unable to connect to the llama server."""
    pass


class LlamaResponseError(Exception):
    """Raised when the server response cannot be parsed into category/description."""
    pass


@dataclass
class ModelInfo:
    """Metadata for a model returned by /v1/models."""
    id: str
    is_vision: bool


def _is_vision_model(model_id: str) -> bool:
    """Return True if the model name suggests vision capability."""
    low = model_id.lower()
    return any(pattern in low for pattern in _VISION_PATTERNS)


class LlamaClient:
    """Client for any OpenAI-compatible inference server (llama-server, llama-swap)."""

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        timeout: int = None,
    ):
        self.base_url = (base_url or Config.LLAMA_BASE_URL).rstrip("/")
        self.model = model or Config.LLAMA_MODEL
        self.timeout = timeout if timeout is not None else Config.LLAMA_TIMEOUT

    def list_models(self) -> List[ModelInfo]:
        """
        Fetch available models from /v1/models.

        Returns models sorted vision-capable first, then alphabetically.
        """
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise LlamaConnectionError(
                f"Cannot reach {self.base_url}/v1/models: {e}"
            ) from e

        data = response.json().get("data", [])
        models = [
            ModelInfo(id=m["id"], is_vision=_is_vision_model(m["id"]))
            for m in data
        ]
        # Vision models first, then alphabetical within each group
        models.sort(key=lambda m: (not m.is_vision, m.id))
        return models

    def validate_connection(self) -> bool:
        """
        Check server reachability.

        Tries GET /health first; falls back to GET /v1/models on 404 (some
        servers don't expose /health).

        Returns:
            True if the server is reachable.

        Raises:
            LlamaConnectionError: If the server cannot be reached.
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 404:
                response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            response.raise_for_status()
            logger.info(f"Connected to llama server at {self.base_url}")
            return True
        except (requests.exceptions.RequestException, ConnectionError) as e:
            raise LlamaConnectionError(
                f"Cannot reach llama server at {self.base_url}: {e}"
            ) from e

    def analyze_image(self, image_path: Path) -> Tuple[str, str]:
        """
        Analyze an image using the vision model via /v1/chat/completions.

        Args:
            image_path: Path to the image file.

        Returns:
            Tuple of (category, description) — both sanitized for use in filenames.

        Raises:
            LlamaResponseError: If the request fails or the response cannot be parsed.
        """
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        mime = _MIME_TYPES.get(image_path.suffix.lower(), "image/jpeg")
        data_url = f"data:{mime};base64,{image_data}"

        prompt = (
            "Analyze this image and provide a response in exactly this format:\n"
            "CATEGORY: <single word category like: animal, object, landscape, person, food, other>\n"
            "DESCRIPTION: <detailed 5-10 word description. If you can identify specific named "
            "characters, brands, or recognizable things, include them>\n"
            "Do not include any other text."
        )

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                            ],
                        }
                    ],
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise LlamaResponseError(
                f"Request to {self.base_url} timed out after {self.timeout}s"
            )
        except requests.exceptions.RequestException as e:
            raise LlamaResponseError(f"Failed to call {self.base_url}: {e}") from e

        try:
            content = response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError) as e:
            raise LlamaResponseError(
                f"Unexpected response structure from {self.base_url}: {e}"
            ) from e

        return self._parse_response(content)

    def _parse_response(self, response_text: str) -> Tuple[str, str]:
        """Parse 'CATEGORY: x\\nDESCRIPTION: y' into (category, description)."""
        category: Optional[str] = None
        description: Optional[str] = None

        for line in response_text.split("\n"):
            line = line.strip()
            if line.startswith("CATEGORY:"):
                category = line.split(":", 1)[1].strip().lower()
            elif line.startswith("DESCRIPTION:"):
                description = line.split(":", 1)[1].strip().lower()

        if not category or not description:
            raise LlamaResponseError(
                f"Could not parse CATEGORY/DESCRIPTION from response: {response_text!r}"
            )

        return self._sanitize(category), self._sanitize(description)

    @staticmethod
    def _sanitize(text: str) -> str:
        """Replace characters that are unsafe in filenames with underscores."""
        for char in '<>:"/\\|?*':
            text = text.replace(char, "_")
        text = text.strip(". ")
        text = text.replace(" ", "_")
        while "__" in text:
            text = text.replace("__", "_")
        return text
