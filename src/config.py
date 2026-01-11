"""
Configuration management for the ImageNamer application.

This module loads configuration from environment variables with sensible defaults.
All configurable parameters are defined here to facilitate future modifications.
"""

import os
from pathlib import Path
from typing import Set

from dotenv import load_dotenv

# Load environment variables from .env file
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


class Config:
    """Central configuration class for ImageNamer."""

    # Ollama configuration
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3-vl:30b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # Image processing configuration
    IMAGE_FOLDER: str = os.getenv("IMAGE_FOLDER", str(Path.home() / "Pictures"))
    SUPPORTED_FORMATS: Set[str] = {"jpg", "jpeg", "png", "webp"}

    # Failure handling configuration
    MAX_CONSECUTIVE_FAILURES: int = int(
        os.getenv("MAX_CONSECUTIVE_FAILURES", "5")
    )

    # Logging configuration
    LOG_DIR: Path = Path(__file__).parent.parent / "logs"
    LOG_FILE: Path = LOG_DIR / "image_namer.log"
    FAILURES_LOG_FILE: Path = LOG_DIR / "failures.json"

    # Application behavior
    DRY_RUN: bool = False  # Set by CLI args
    RETRY_FAILURES: bool = False  # Set by CLI args

    @classmethod
    def validate(cls) -> None:
        """Validate configuration and create required directories."""
        # Ensure log directory exists
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Validate image folder exists
        image_path = Path(cls.IMAGE_FOLDER)
        if not image_path.exists():
            raise ValueError(f"IMAGE_FOLDER does not exist: {cls.IMAGE_FOLDER}")

        if not image_path.is_dir():
            raise ValueError(f"IMAGE_FOLDER is not a directory: {cls.IMAGE_FOLDER}")

    @classmethod
    def get_supported_extensions(cls) -> Set[str]:
        """Get supported file extensions (lowercase, with dots)."""
        return {f".{fmt}" for fmt in cls.SUPPORTED_FORMATS}
