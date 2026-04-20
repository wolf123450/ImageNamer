"""
Pure-Python UI state and helper functions.

No NiceGUI dependency — fully unit-testable. The NiceGUI layer in ui.py
reads from and writes to UIState to drive rendering.
"""

from dataclasses import dataclass, field
from typing import List

from llama_client import ModelInfo


def build_model_label(model: ModelInfo) -> str:
    """Return the display label for a model in the dropdown."""
    return f"{model.id} 👁" if model.is_vision else model.id


@dataclass
class UIState:
    """Tracks all mutable UI state in one place."""

    is_running: bool = False
    rename_count: int = 0
    output_folder: str = ""
    log_lines: List[str] = field(default_factory=list)

    @property
    def move_button_enabled(self) -> bool:
        """Move → button is enabled when a run finished with ≥1 rename and an output folder is set."""
        return not self.is_running and self.rename_count > 0 and bool(self.output_folder)

    @property
    def run_buttons_enabled(self) -> bool:
        """Run and Dry-run buttons are disabled while a run is in progress."""
        return not self.is_running

    def on_progress(self, level: str, message: str) -> None:
        """Append a progress message to log_lines. Used as progress_callback by ImageProcessor."""
        self.log_lines.append(f"[{level}] {message}")
