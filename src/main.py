"""
Main entry point for the ImageNamer application.

Orchestrates image discovery, analysis, and renaming with error handling,
failure logging, and retry support.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from config import Config
from failure_logger import FailureLog
from image_processor import ImageProcessor
from ollama_client import OllamaClient, OllamaConnectionError


# Configure logging
def setup_logging() -> None:
    """Set up dual logging: file and console."""
    Config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # File handler (detailed)
    file_handler = logging.FileHandler(Config.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (less verbose)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Rename images based on AI-powered content recognition using Ollama"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry only images that previously failed",
    )
    parser.add_argument(
        "--image-folder",
        type=str,
        help="Path to image folder (overrides IMAGE_FOLDER env var)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("ImageNamer started")
    logger.info(f"Ollama URL: {Config.OLLAMA_BASE_URL}")
    logger.info(f"Ollama Model: {Config.OLLAMA_MODEL}")
    logger.info(f"Image Folder: {Config.IMAGE_FOLDER}")
    logger.info(f"Max Consecutive Failures: {Config.MAX_CONSECUTIVE_FAILURES}")
    if args.dry_run:
        logger.info("MODE: DRY RUN (no files will be modified)")
    if args.retry_failures:
        logger.info("MODE: RETRY FAILURES")
    logger.info("=" * 60)

    # Override configuration if provided
    if args.image_folder:
        Config.IMAGE_FOLDER = args.image_folder

    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    # Initialize components
    try:
        ollama_client = OllamaClient()
        ollama_client.validate_connection()
    except OllamaConnectionError as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        return 1

    processor = ImageProcessor(ollama_client)
    failure_log = FailureLog()

    # Determine images to process
    if args.retry_failures:
        pending_failures = failure_log.get_pending_failures()
        if not pending_failures:
            logger.info("No pending failures to retry")
            return 0

        image_paths = [Path(Config.IMAGE_FOLDER) / filename for filename in pending_failures]
        logger.info(f"Retrying {len(image_paths)} previously failed images")
    else:
        image_paths = processor.discover_images()
        if not image_paths:
            logger.warning("No images found to process")
            return 0

    # Process images
    success_count = 0
    skipped_count = 0
    consecutive_failures = 0
    persistent_failures = []

    for idx, image_path in enumerate(image_paths, 1):
        logger.info(f"Processing {idx}/{len(image_paths)}: {image_path.name}")

        success, new_filename, error = processor.process_image(
            image_path, dry_run=args.dry_run
        )

        if success:
            success_count += 1
            consecutive_failures = 0
            failure_log.log_success(image_path.name)
        else:
            consecutive_failures += 1
            failure_log.log_failure(image_path.name, error, retry_count=0)
            persistent_failures.append((image_path.name, error))

            logger.warning(
                f"Failed to process {image_path.name}: {error} "
                f"({consecutive_failures}/{Config.MAX_CONSECUTIVE_FAILURES})"
            )

            if consecutive_failures >= Config.MAX_CONSECUTIVE_FAILURES:
                logger.critical(
                    f"Aborting: {Config.MAX_CONSECUTIVE_FAILURES} consecutive failures detected. "
                    "This likely indicates Ollama is down or the model is broken."
                )
                break

    # Print summary
    logger.info("=" * 60)
    logger.info("Processing Summary:")
    logger.info(f"  Successfully processed: {success_count}")
    logger.info(f"  Failed (logged for retry): {len(persistent_failures)}")
    logger.info(f"  Total processed: {success_count + len(persistent_failures)}")

    if persistent_failures:
        logger.warning("Failed images (use --retry-failures to retry):")
        for filename, error in persistent_failures:
            logger.warning(f"  - {filename}: {error}")

    if args.dry_run:
        logger.info("DRY RUN completed - no files were modified")

    logger.info(f"Full log available at: {Config.LOG_FILE}")
    logger.info("=" * 60)

    return 0 if consecutive_failures < Config.MAX_CONSECUTIVE_FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
