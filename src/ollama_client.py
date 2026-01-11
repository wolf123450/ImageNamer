"""
Ollama REST client for vision model interaction.

Handles communication with Ollama instance for image analysis using qwen3-vl model.
Provides error handling, response parsing, and connection validation.
"""

import base64
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import requests

from config import Config


logger = logging.getLogger(__name__)


class OllamaConnectionError(Exception):
    """Raised when unable to connect to Ollama service."""

    pass


class OllamaResponseError(Exception):
    """Raised when Ollama response is invalid or unexpected."""

    pass


class OllamaClient:
    """Client for communicating with Ollama REST API."""

    def __init__(self, base_url: str = None, model: str = None):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API base URL. Defaults to OLLAMA_BASE_URL from config.
            model: Vision model name. Defaults to OLLAMA_MODEL from config.
        """
        self.base_url = base_url or Config.OLLAMA_BASE_URL
        self.model = model or Config.OLLAMA_MODEL
        self.timeout = Config.OLLAMA_TIMEOUT

    def validate_connection(self) -> bool:
        """
        Validate connection to Ollama service.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            response.raise_for_status()
            logger.info("Successfully connected to Ollama service")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.base_url}: {e}"
            ) from e

    def analyze_image(self, image_path: Path) -> Tuple[str, str]:
        """
        Analyze an image using the vision model.

        Sends image to Ollama qwen3-vl model and extracts category and description.

        Args:
            image_path: Path to the image file.

        Returns:
            Tuple of (category, description).

        Raises:
            OllamaResponseError: If model response cannot be parsed into category and description.
            requests.exceptions.RequestException: If HTTP request fails.
        """
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Prepare the prompt for structured response
        prompt = (
            "Analyze this image and provide a response in exactly this format:\n"
            "CATEGORY: <single word category like: animal, object, landscape, person, food, other>\n"
            "DESCRIPTION: <detailed 5-10 word description. If you can identify specific named characters, brands, or recognizable things, include them>\n"
            "Do not include any other text."
        )

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [image_data],
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise OllamaResponseError(
                f"Request to Ollama timed out after {self.timeout}s"
            )
        except requests.exceptions.RequestException as e:
            raise OllamaResponseError(f"Failed to call Ollama API: {e}") from e

        # Parse response
        try:
            data = response.json()
            response_text = data.get("response", "").strip()

            if not response_text:
                raise OllamaResponseError("Empty response from Ollama")

            # Extract category and description from response
            category, description = self._parse_response(response_text)
            logger.debug(
                f"Analyzed {image_path.name}: category={category}, description={description}"
            )
            return category, description

        except json.JSONDecodeError as e:
            raise OllamaResponseError(f"Invalid JSON response from Ollama: {e}") from e

    def _parse_response(self, response_text: str) -> Tuple[str, str]:
        """
        Parse model response into category and description.

        Expected format:
            CATEGORY: <word>
            DESCRIPTION: <phrase>

        Args:
            response_text: Raw response text from model.

        Returns:
            Tuple of (category, description).

        Raises:
            OllamaResponseError: If response format is invalid.
        """
        lines = response_text.split("\n")

        category = None
        description = None

        for line in lines:
            line = line.strip()
            if line.startswith("CATEGORY:"):
                category = line.split(":", 1)[1].strip().lower()
            elif line.startswith("DESCRIPTION:"):
                description = line.split(":", 1)[1].strip().lower()

        if not category or not description:
            raise OllamaResponseError(
                f"Could not parse category or description from response: {response_text}"
            )

        # Sanitize strings (remove special characters that would break filenames)
        category = self._sanitize_filename_part(category)
        description = self._sanitize_filename_part(description)

        return category, description

    @staticmethod
    def _sanitize_filename_part(text: str) -> str:
        """
        Sanitize text for use in filenames.

        Removes or replaces characters that are problematic in filenames.
        Spaces are replaced with underscores for clean naming.

        Args:
            text: Input text to sanitize.

        Returns:
            Sanitized text safe for filenames.
        """
        # Replace problematic characters with underscores
        problematic_chars = '<>:"/\\|?*'
        for char in problematic_chars:
            text = text.replace(char, "_")

        # Remove leading/trailing whitespace and dots
        text = text.strip(". ")

        # Replace spaces with underscores
        text = text.replace(" ", "_")

        # Replace multiple underscores with single underscore
        while "__" in text:
            text = text.replace("__", "_")

        return text
