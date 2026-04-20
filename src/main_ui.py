"""
NiceGUI entry point for ImageNamer desktop UI.

Run with:
    python src/main_ui.py

Opens a native desktop window (embedded Chromium via pywebview).
"""

import sys
from pathlib import Path

# Ensure src is importable when run directly
sys.path.insert(0, str(Path(__file__).parent))

from nicegui import ui

from ui import ImageNamerUI


def main() -> None:
    namer_ui = ImageNamerUI()
    namer_ui.build()
    ui.run(
        native=True,
        title="ImageNamer",
        window_size=(900, 650),
        reload=False,
    )


if __name__ == "__main__":
    main()
