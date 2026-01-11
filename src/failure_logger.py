"""
Failure tracking and logging for image processing.

Maintains persistent failure log in JSON format to track retry attempts,
failure reasons, and resolution status across script runs.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import Config


logger = logging.getLogger(__name__)


class FailureLog:
    """Manages persistent failure logging for images that fail processing."""

    def __init__(self, failures_file: Path = None):
        """
        Initialize failure log.

        Args:
            failures_file: Path to JSON file for storing failures.
                          Defaults to Config.FAILURES_LOG_FILE.
        """
        self.failures_file = failures_file or Config.FAILURES_LOG_FILE
        self._failures: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load failures from file if it exists."""
        if self.failures_file.exists():
            try:
                with open(self.failures_file, "r") as f:
                    data = json.load(f)
                    self._failures = data
                logger.debug(f"Loaded {len(self._failures)} failures from log")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load failures file: {e}. Starting fresh.")
                self._failures = {}
        else:
            self._failures = {}

    def _save(self) -> None:
        """Save failures to file."""
        try:
            self.failures_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.failures_file, "w") as f:
                json.dump(self._failures, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save failures log: {e}")

    def log_failure(
        self, filename: str, error_message: str, retry_count: int = 0
    ) -> None:
        """
        Log a failure for an image.

        Args:
            filename: Name of the image file that failed.
            error_message: Error message describing the failure.
            retry_count: Number of retry attempts so far.
        """
        now = datetime.now().isoformat()

        if filename not in self._failures:
            # First failure for this file
            self._failures[filename] = {
                "filename": filename,
                "first_attempt": now,
                "last_attempt": now,
                "retry_count": retry_count,
                "status": "pending",
                "errors": [error_message],
            }
        else:
            # Update existing failure record
            record = self._failures[filename]
            record["last_attempt"] = now
            record["retry_count"] = retry_count
            if error_message not in record.get("errors", []):
                record.setdefault("errors", []).append(error_message)

        self._save()
        logger.debug(f"Logged failure for {filename}: {error_message}")

    def log_success(self, filename: str) -> None:
        """
        Mark a previously failed file as successfully processed.

        Args:
            filename: Name of the image file that succeeded.
        """
        if filename in self._failures:
            self._failures[filename]["status"] = "success"
            self._failures[filename]["success_time"] = datetime.now().isoformat()
            self._save()
            logger.info(f"Marked {filename} as successfully processed")

    def get_pending_failures(self) -> List[str]:
        """
        Get list of filenames that are pending retry.

        Returns:
            List of filenames with status 'pending'.
        """
        return [
            filename
            for filename, record in self._failures.items()
            if record.get("status") == "pending"
        ]

    def get_all_failures(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all failure records.

        Returns:
            Dictionary of all failures indexed by filename.
        """
        return self._failures.copy()

    def clear_file(self, filename: str) -> None:
        """
        Remove a file from the failure log.

        Args:
            filename: Name of the image file to remove.
        """
        if filename in self._failures:
            del self._failures[filename]
            self._save()
            logger.debug(f"Removed {filename} from failure log")

    def has_pending_failures(self) -> bool:
        """
        Check if there are any pending failures.

        Returns:
            True if there are pending failures, False otherwise.
        """
        return any(
            record.get("status") == "pending" for record in self._failures.values()
        )
