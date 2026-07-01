"""
NiceGUI UI for ImageNamer.

Builds the side-by-side desktop UI. All state lives in UIState; this module
is responsible only for rendering and wiring up event handlers.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

import webview
from nicegui import app, run, ui

from config import Config
from image_processor import ImageProcessor
from llama_client import LlamaClient, LlamaConnectionError, ModelInfo
from ui_state import UIState, build_model_label

logger = logging.getLogger(__name__)

_CSS_PATH = Path(__file__).parent / "styles" / "app.css"


class ImageNamerUI:
    """Constructs and wires the NiceGUI UI."""

    def __init__(self):
        self.state = UIState(output_folder=Config.OUTPUT_FOLDER)
        self.client = LlamaClient()
        self.models: List[ModelInfo] = []
        self.selected_model: str = Config.LLAMA_MODEL

        # NiceGUI element references (set during build)
        self._model_select = None
        self._run_btn = None
        self._dry_run_btn = None
        self._move_btn = None
        self._progress_bar = None
        self._log = None
        self._status_label = None
        self._input_input = None
        self._output_input = None
        self._dark_mode = None

    def build(self) -> None:
        """Register static files, inject CSS, and define the page layout."""
        app.add_static_files("/styles", str(Path(__file__).parent / "styles"))

        @ui.page("/")
        async def index():
            ui.add_head_html('<link rel="stylesheet" href="/styles/app.css">')
            await self._render()
            # Schedule network calls as background tasks so the page renders
            # immediately and doesn't hit NiceGUI's 3-second render timeout.
            asyncio.ensure_future(self._load_models())
            asyncio.ensure_future(self._check_connection())

    async def _render(self) -> None:
        """Render the full page layout."""
        self._dark_mode = ui.dark_mode()
        # Apply saved theme immediately
        if Config.UI_THEME == "dark":
            self._dark_mode.enable()
        elif Config.UI_THEME == "light":
            self._dark_mode.disable()
        else:
            self._dark_mode.auto()
        with ui.row().classes("w-full gap-4 p-4"):
            # ── LEFT PANEL (controls) ────────────────────────────────
            with ui.column().classes("flex-1 gap-3 imagenamer-panel"):
                ui.label("Controls").classes("text-lg font-semibold")

                # Input folder
                with ui.row().classes("w-full items-center gap-2"):
                    self._input_input = ui.input(
                        label="Input folder",
                        value=Config.INPUT_FOLDER,
                    ).classes("flex-1").on(
                        "change", lambda e: self._on_input_folder_change(e.value)
                    )
                    ui.button(
                        icon="folder_open",
                        on_click=self._pick_input_folder,
                    ).props("flat dense")

                # Output folder
                with ui.row().classes("w-full items-center gap-2"):
                    self._output_input = ui.input(
                        label="Output folder (optional)",
                        value=Config.OUTPUT_FOLDER,
                    ).classes("flex-1").on(
                        "change", lambda e: self._on_output_folder_change(e.value)
                    )
                    ui.button(
                        icon="folder_open",
                        on_click=self._pick_output_folder,
                    ).props("flat dense")

                # Model selector
                with ui.row().classes("w-full items-center gap-2"):
                    self._model_select = ui.select(
                        options=[self.selected_model],
                        value=self.selected_model,
                        label="Model",
                        on_change=lambda e: setattr(self, "selected_model", e.value),
                    ).classes("flex-1")
                    ui.button(
                        icon="refresh",
                        on_click=self._refresh_models,
                    ).props("flat dense").tooltip("Refresh model list from server")

                # Action buttons
                with ui.row().classes("gap-2"):
                    self._run_btn = ui.button(
                        "▶ Run",
                        on_click=lambda: self._run(dry_run=False),
                    ).props("color=primary")
                    self._dry_run_btn = ui.button(
                        "Dry-run",
                        on_click=lambda: self._run(dry_run=True),
                    ).props("outline")
                    self._move_btn = (
                        ui.button(
                            "Move →",
                            on_click=lambda: self._move(),
                        )
                        .props("outline")
                        .set_enabled(False)
                    )

                # Progress bar (hidden initially)
                self._progress_bar = ui.linear_progress(value=0).classes("w-full").set_visibility(False)

                # Log
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Log").classes("font-semibold")
                    ui.button(
                        icon="clear_all",
                        on_click=self._clear_log,
                    ).props("flat dense").tooltip("Clear log")
                self._log = ui.log(max_lines=200).classes("w-full h-48 font-mono text-sm")

            # ── RIGHT PANEL (settings) ───────────────────────────────
            with ui.column().classes("w-72 gap-3 imagenamer-panel"):
                ui.label("Settings").classes("text-lg font-semibold")

                # Server URL
                ui.input(
                    label="Server URL",
                    value=Config.LLAMA_BASE_URL,
                    on_change=lambda e: self._on_server_url_change(e.value),
                ).classes("w-full")

                # Theme toggle
                ui.label("Theme").classes("text-sm font-medium mt-2")
                with ui.row().classes("gap-1"):
                    for theme in ("Dark", "Light", "System"):
                        ui.button(
                            theme,
                            on_click=lambda t=theme: self._set_theme(t.lower()),
                        ).classes("theme-pill").props("flat dense")

                # Max failures
                ui.number(
                    label="Max consecutive failures",
                    value=Config.MAX_CONSECUTIVE_FAILURES,
                    min=1,
                    max=50,
                    on_change=lambda e: setattr(Config, "MAX_CONSECUTIVE_FAILURES", int(e.value)),
                ).classes("w-full")

                # Connection status
                with ui.row().classes("items-center mt-4"):
                    self._status_label = ui.html(
                        '<span class="status-dot disconnected"></span> Checking…'
                    )

    # ── Event handlers ──────────────────────────────────────────────

    def _on_input_folder_change(self, value: str) -> None:
        Config.INPUT_FOLDER = value

    def _on_output_folder_change(self, value: str) -> None:
        Config.OUTPUT_FOLDER = value
        self.state.output_folder = value
        self._refresh_move_button()

    def _on_server_url_change(self, value: str) -> None:
        Config.LLAMA_BASE_URL = value
        self.client = LlamaClient(base_url=value, model=self.selected_model)

    async def _pick_input_folder(self) -> None:
        result = await app.native.main_window.create_file_dialog(
            webview.FileDialog.FOLDER if hasattr(webview, "FileDialog") else webview.FOLDER_DIALOG,
            directory=str(Path(Config.INPUT_FOLDER).expanduser()) if Config.INPUT_FOLDER else str(Path.home()),
        )
        if result:
            folder = result[0]
            if self._input_input:
                self._input_input.value = folder
            self._on_input_folder_change(folder)

    async def _pick_output_folder(self) -> None:
        result = await app.native.main_window.create_file_dialog(
            webview.FileDialog.FOLDER if hasattr(webview, "FileDialog") else webview.FOLDER_DIALOG,
            directory=str(Path(Config.OUTPUT_FOLDER).expanduser()) if Config.OUTPUT_FOLDER else str(Path.home()),
        )
        if result:
            folder = result[0]
            if self._output_input:
                self._output_input.value = folder
            self._on_output_folder_change(folder)

    async def _load_models(self) -> None:
        try:
            models = await run.io_bound(self.client.list_models)
            self.models = models or []
            options = [build_model_label(m) for m in self.models]
            if self._model_select:
                self._model_select.options = options
                # Keep current selection if still available, else default to first
                current_labels = [build_model_label(m) for m in self.models if m.id == self.selected_model]
                self._model_select.value = current_labels[0] if current_labels else (options[0] if options else "")
        except Exception:
            # Server unreachable — keep the config default visible in the dropdown
            self.models = []
            if self._model_select:
                self._model_select.options = [self.selected_model]
            # Avoid ui.notify here — it requires slot context which background tasks lack
            self._push_log("warning", "Cannot reach llama server — using config default model")

    async def _refresh_models(self) -> None:
        await self._load_models()
        await self._check_connection()

    async def _check_connection(self) -> None:
        try:
            await run.io_bound(self.client.validate_connection)
            html = '<span class="status-dot connected"></span> Connected'
        except Exception:
            html = f'<span class="status-dot disconnected"></span> Disconnected ({Config.LLAMA_BASE_URL})'
        if self._status_label:
            self._status_label.set_content(html)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.state.is_running = not enabled
        if self._run_btn:
            self._run_btn.set_enabled(enabled)
        if self._dry_run_btn:
            self._dry_run_btn.set_enabled(enabled)
        self._refresh_move_button()

    def _refresh_move_button(self) -> None:
        if self._move_btn:
            self._move_btn.set_enabled(self.state.move_button_enabled)

    def _clear_log(self) -> None:
        if self._log:
            self._log.clear()
        self.state.log_lines.clear()

    def _push_log(self, level: str, message: str) -> None:
        """progress_callback compatible — push a line to the log element."""
        self.state.on_progress(level, message)
        if self._log:
            prefix = {"success": "✓", "error": "✗", "warning": "⚠", "info": "→"}.get(level, "·")
            self._log.push(f"{prefix} {message}")

    async def _run(self, dry_run: bool) -> None:
        self._set_buttons_enabled(False)
        if self._progress_bar:
            self._progress_bar.set_visibility(True)
            self._progress_bar.set_value(0)

        # Sync selected_model from dropdown label back to bare ID
        selected_label = self._model_select.value if self._model_select else self.selected_model
        model_id = next(
            (m.id for m in self.models if build_model_label(m) == selected_label),
            self.selected_model,
        )
        client = LlamaClient(base_url=Config.LLAMA_BASE_URL, model=model_id)

        processor = ImageProcessor(
            ollama_client=client,
            progress_callback=self._push_log,
        )
        processor.image_folder = Path(Config.INPUT_FOLDER)
        processor.output_folder = Config.OUTPUT_FOLDER

        # Check connection first
        try:
            await run.io_bound(client.validate_connection)
        except LlamaConnectionError as e:
            self._push_log("error", str(e))
            await self._check_connection()
            self._set_buttons_enabled(True)
            if self._progress_bar:
                self._progress_bar.set_visibility(False)
            return

        success_count, failure_count = await run.io_bound(processor.process_all, dry_run)

        self.state.rename_count = success_count
        if self._progress_bar:
            self._progress_bar.set_value(1)

        # Store processor for move phase
        self._last_processor = processor

        self._set_buttons_enabled(True)
        await self._check_connection()

    async def _move(self) -> None:
        if not hasattr(self, "_last_processor"):
            return
        self._set_buttons_enabled(False)
        result = await run.io_bound(self._last_processor.move_to_output)
        self._push_log("info", f"Move complete — moved: {result.moved}, skipped: {result.skipped}")
        for err in result.errors:
            self._push_log("error", err)
        self._set_buttons_enabled(True)
        self.state.rename_count = 0  # Reset — already moved
        self._refresh_move_button()

    async def _set_theme(self, theme: str) -> None:
        """Apply theme by setting data-theme attribute and persisting to config."""
        Config.UI_THEME = theme
        if theme == "dark":
            if self._dark_mode:
                self._dark_mode.enable()
            js = "document.documentElement.setAttribute('data-theme', 'dark')"
        elif theme == "light":
            if self._dark_mode:
                self._dark_mode.disable()
            js = "document.documentElement.setAttribute('data-theme', 'light')"
        else:
            if self._dark_mode:
                self._dark_mode.auto()
            js = "document.documentElement.removeAttribute('data-theme')"
        await ui.run_javascript(js)
