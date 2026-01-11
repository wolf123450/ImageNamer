"""
Image processing and renaming logic.

Discovers images, invokes Ollama for analysis, generates logical filenames,
handles naming conflicts, and executes safe file renames.
"""

import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple

from config import Config
from ollama_client import OllamaClient, OllamaResponseError


logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image discovery, analysis, and renaming."""

    def __init__(self, ollama_client: OllamaClient = None):
        """
        Initialize image processor.

        Args:
            ollama_client: OllamaClient instance. Creates default if not provided.
        """
        self.ollama_client = ollama_client or OllamaClient()
        self.image_folder = Path(Config.IMAGE_FOLDER)
        self.supported_extensions = Config.get_supported_extensions()

    def discover_images(self) -> List[Path]:
        """
        Discover all supported image files in the image folder.

        Returns:
            List of Path objects for discovered images.
        """
        if not self.image_folder.exists():
            logger.error(f"Image folder does not exist: {self.image_folder}")
            return []

        images = []
        for ext in self.supported_extensions:
            # Search for images with this extension (case-insensitive)
            images.extend(self.image_folder.glob(f"*{ext}"))
            images.extend(self.image_folder.glob(f"*{ext.upper()}"))

        # Remove duplicates and sort
        images = sorted(set(images))
        logger.info(f"Discovered {len(images)} images in {self.image_folder}")

        return images

    def analyze_and_generate_filename(
        self, image_path: Path
    ) -> Tuple[str, Optional[str]]:
        """
        Analyze an image and generate a new filename.

        Args:
            image_path: Path to the image file.

        Returns:
            Tuple of (new_filename_with_ext, error_message).
            error_message is None on success, otherwise contains the error description.
        """
        try:
            category, description = self.ollama_client.analyze_image(image_path)
            new_filename = self._generate_filename(
                category, description, image_path.suffix
            )
            return new_filename, None
        except OllamaResponseError as e:
            error_msg = f"Failed to analyze image: {e}"
            logger.warning(f"{image_path.name}: {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error during analysis: {e}"
            logger.error(f"{image_path.name}: {error_msg}")
            return None, error_msg

    def _generate_filename(
        self, category: str, description: str, file_extension: str
    ) -> str:
        """
        Generate a new filename from category and description.

        Format: [category]-[description].ext

        Args:
            category: Image category (e.g., 'animal').
            description: Image description (e.g., 'brown dog').
            file_extension: Original file extension including dot (e.g., '.jpg').

        Returns:
            New filename with extension.
        """
        # Ensure extension starts with dot and is lowercase
        if not file_extension.startswith("."):
            file_extension = f".{file_extension}"
        file_extension = file_extension.lower()

        # Generate base filename
        base_filename = f"{category}-{description}"

        return f"{base_filename}{file_extension}"

    def resolve_filename_conflict(
        self, proposed_filename: str, existing_path: Path
    ) -> str:
        """
        Resolve filename conflicts by appending numeric suffix.

        If proposed_filename already exists, appends -2, -3, etc. until unique.

        Args:
            proposed_filename: The desired filename.
            existing_path: The directory where the file would be placed.

        Returns:
            A unique filename that does not exist in existing_path.
        """
        target_path = existing_path / proposed_filename

        if not target_path.exists():
            return proposed_filename

        # File exists; need to add suffix
        stem = target_path.stem  # filename without extension
        suffix = target_path.suffix  # extension with dot

        counter = 2
        while True:
            new_filename = f"{stem}-{counter}{suffix}"
            new_path = existing_path / new_filename

            if not new_path.exists():
                logger.debug(
                    f"Resolved conflict for {proposed_filename} -> {new_filename}"
                )
                return new_filename

            counter += 1

            # Safety check: prevent infinite loop
            if counter > 1000:
                raise RuntimeError(
                    f"Unable to resolve filename conflict for {proposed_filename} "
                    "after 1000 attempts"
                )

    def rename_image(
        self, image_path: Path, new_filename: str, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Rename an image file to the new filename.

        Args:
            image_path: Path to the current image file.
            new_filename: Desired new filename (without path).
            dry_run: If True, log the rename but don't execute it.

        Returns:
            Tuple of (success, error_message).
            error_message is None on success.
        """
        try:
            new_path = image_path.parent / new_filename

            if dry_run:
                logger.info(f"[DRY RUN] Would rename: {image_path.name} -> {new_filename}")
                return True, None

            # Perform the actual rename
            image_path.rename(new_path)
            logger.info(f"Renamed: {image_path.name} -> {new_filename}")
            return True, None

        except Exception as e:
            error_msg = f"Failed to rename file: {e}"
            logger.error(f"{image_path.name}: {error_msg}")
            return False, error_msg

    def process_image(
        self, image_path: Path, dry_run: bool = False
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Process a single image: analyze, generate filename, and rename.

        Args:
            image_path: Path to the image file.
            dry_run: If True, log changes but don't execute them.

        Returns:
            Tuple of (success, new_filename, error_message).
            new_filename is only set on success.
            error_message is None on success.
        """
        # Check if file still exists (in case of concurrent modifications)
        if not image_path.exists():
            return False, None, "Image file no longer exists"

        # Step 1: Analyze and generate filename
        new_filename, analyze_error = self.analyze_and_generate_filename(image_path)
        if analyze_error:
            return False, None, analyze_error

        # Step 2: Resolve any naming conflicts
        try:
            final_filename = self.resolve_filename_conflict(
                new_filename, image_path.parent
            )
        except Exception as e:
            return False, None, f"Failed to resolve filename conflict: {e}"

        # Step 3: Rename the file
        success, rename_error = self.rename_image(image_path, final_filename, dry_run)

        if success:
            return True, final_filename, None
        else:
            return False, None, rename_error
