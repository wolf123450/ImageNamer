"""
Image processing and renaming logic.

Discovers images, invokes the vision client for analysis, generates logical
filenames, handles naming conflicts, and executes safe file renames.

v2 additions:
- progress_callback parameter for live UI updates
- INPUT_FOLDER support via Config.INPUT_FOLDER
- move_to_output() for optional second-phase output relocation
- process_all() convenience wrapper used by the UI
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple

from config import Config
from ollama_client import OllamaClient, OllamaResponseError

logger = logging.getLogger(__name__)


@dataclass
class MoveResult:
    """Result of a move_to_output() call."""
    moved: int
    skipped: int
    errors: List[str] = field(default_factory=list)


class ImageProcessor:
    """Handles image discovery, analysis, and renaming."""

    def __init__(
        self,
        ollama_client: OllamaClient = None,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize image processor.

        Args:
            ollama_client: Vision client instance. Creates default LlamaClient if not provided.
            progress_callback: Optional callback invoked with (level, message) during processing.
                               level is one of: 'info', 'success', 'warning', 'error'.
        """
        self.ollama_client = ollama_client or OllamaClient()
        self.image_folder = Path(Config.INPUT_FOLDER)
        self.output_folder: str = Config.OUTPUT_FOLDER
        self.supported_extensions = Config.get_supported_extensions()
        self.progress_callback = progress_callback
        self._renamed_files: List[Path] = []  # Paths of successfully renamed files this session

    def _emit(self, level: str, message: str) -> None:
        """Emit a progress message to the callback (if set) and the logger."""
        if self.progress_callback:
            self.progress_callback(level, message)
        log_fn = {
            "info": logger.info,
            "success": logger.info,
            "warning": logger.warning,
            "error": logger.error,
        }.get(level, logger.info)
        log_fn(message)

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
        self, proposed_filename: str, directory: Path
    ) -> str:
        """
        Return a unique filename in directory by appending -2, -3, ... as needed.
        """
        target_path = directory / proposed_filename

        if not target_path.exists():
            return proposed_filename

        stem = target_path.stem
        suffix = target_path.suffix

        counter = 2
        while True:
            new_filename = f"{stem}-{counter}{suffix}"
            if not (directory / new_filename).exists():
                logger.debug(f"Resolved conflict: {proposed_filename} -> {new_filename}")
                return new_filename
            counter += 1
            if counter > 1000:
                raise RuntimeError(
                    f"Unable to resolve filename conflict for {proposed_filename} after 1000 attempts"
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
            if not dry_run:
                self._renamed_files.append(image_path.parent / final_filename)
            return True, final_filename, None
        else:
            return False, None, rename_error

    def process_all(self, dry_run: bool = False) -> Tuple[int, int]:
        """
        Discover and process all images in image_folder.

        Emits progress via progress_callback. Stops early if
        Config.MAX_CONSECUTIVE_FAILURES consecutive failures occur.

        Returns:
            Tuple of (success_count, failure_count).
        """
        images = self.discover_images()
        if not images:
            self._emit("warning", "No images found to process")
            return 0, 0

        self._emit("info", f"Found {len(images)} images to process")
        success_count = 0
        failure_count = 0
        consecutive_failures = 0

        for idx, image_path in enumerate(images, 1):
            self._emit("info", f"Processing {idx}/{len(images)}: {image_path.name}")
            success, new_filename, error = self.process_image(image_path, dry_run=dry_run)

            if success:
                success_count += 1
                consecutive_failures = 0
                action = "[DRY RUN] Would rename" if dry_run else "Renamed"
                self._emit("success", f"{action}: {image_path.name} -> {new_filename}")
            else:
                failure_count += 1
                consecutive_failures += 1
                self._emit("error", f"Failed: {image_path.name}: {error}")
                if consecutive_failures >= Config.MAX_CONSECUTIVE_FAILURES:
                    self._emit(
                        "error",
                        f"Stopping: {consecutive_failures} consecutive failures. "
                        "Check that the server is running and the model supports vision.",
                    )
                    break

        self._emit(
            "info",
            f"Done. Renamed: {success_count}, Failed: {failure_count}",
        )
        return success_count, failure_count

    def move_to_output(self, dry_run: bool = False) -> MoveResult:
        """
        Move all session-renamed files to output_folder.

        No-op if output_folder is empty or dry_run is True (logs intent only).

        Returns:
            MoveResult with counts of moved, skipped, and any error messages.
        """
        if not self.output_folder:
            self._emit("info", "No output folder configured — skipping move")
            return MoveResult(moved=0, skipped=len(self._renamed_files))

        output_path = Path(self.output_folder)
        if not dry_run:
            output_path.mkdir(parents=True, exist_ok=True)

        moved = 0
        skipped = 0
        errors: List[str] = []

        for file_path in self._renamed_files:
            if not file_path.exists():
                skipped += 1
                continue

            dest_filename = self.resolve_filename_conflict(file_path.name, output_path)
            dest = output_path / dest_filename

            if dry_run:
                self._emit("info", f"[DRY RUN] Would move: {file_path.name} -> {dest}")
                skipped += 1
                continue

            try:
                file_path.rename(dest)
                moved += 1
                self._emit("success", f"Moved: {file_path.name} -> {dest_filename}")
            except Exception as e:
                errors.append(f"{file_path.name}: {e}")
                self._emit("error", f"Failed to move {file_path.name}: {e}")

        return MoveResult(moved=moved, skipped=skipped, errors=errors)
