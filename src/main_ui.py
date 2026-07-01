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

import webview
from nicegui import app, ui

from ui import ImageNamerUI

# Enable right-click → Inspect Element / DevTools in the native window.
# OPEN_DEVTOOLS_IN_DEBUG=False prevents the panel opening automatically on launch.
app.native.start_args['debug'] = True
app.native.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False


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
