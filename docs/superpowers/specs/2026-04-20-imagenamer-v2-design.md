# ImageNamer v2 Design

**Date:** 2026-04-20  
**Status:** Approved — ready for implementation planning

---

## Overview

Three additive improvements to ImageNamer:

1. **Replace Ollama with llama-server / llama-swap** — switch the inference backend to the OpenAI-compatible API exposed by `llama-server` (llama.cpp) or `llama-swap`, which is already running locally at `http://localhost:8080`.
2. **Separate input/output directories** — allow scanning one folder and optionally moving renamed files to a different output folder as a second, explicit step.
3. **NiceGUI desktop UI** — a native desktop window with a side-by-side layout, styled with the same CSS token system used in the project's other Vue/Tauri apps.

All three are implemented test-first (TDD). The existing CLI (`main.py`) remains fully functional and unchanged.

---

## Architecture

### New / Modified Files

**Added:**
- `src/llama_client.py` — OpenAI-compatible inference client (replaces ollama_client.py logic)
- `src/ui.py` — NiceGUI UI component definitions
- `src/main_ui.py` — UI entry point
- `src/styles/app.css` — CSS token stylesheet (adapted from tauri-app-skeleton)
- `tests/conftest.py` — shared pytest fixtures
- `tests/test_llama_client.py`
- `tests/test_image_processor.py`
- `tests/test_config.py`
- `tests/test_ui_logic.py`

**Modified:**
- `src/ollama_client.py` — becomes a one-line shim: `LlamaClient` alias
- `src/config.py` — new env vars: `LLAMA_BASE_URL`, `LLAMA_MODEL`, `INPUT_FOLDER`, `OUTPUT_FOLDER`
- `src/image_processor.py` — `move_to_output()` method added
- `requirements.txt` — adds `nicegui`, `responses` (test HTTP mocking)
- `.env.example` — updated with new vars
- `README.md` — updated usage docs

---

## Module Specifications

### 1. `llama_client.py`

**Purpose:** Drop-in replacement for `OllamaClient`. Communicates with any OpenAI-compatible server.

**`ModelInfo` dataclass:**
```python
@dataclass
class ModelInfo:
    id: str
    is_vision: bool
```

**Vision detection:** A model is flagged `is_vision=True` if its `id` (lowercased) contains any of: `vl`, `vision`, `gemma4`, `mmproj`. This correctly auto-tags `qwen3-vl-8b`, `gemma4-e4b`, etc. Users can override by manually setting `LLAMA_MODEL` to any model ID in settings.

**`LlamaClient` public interface:**

| Method | Behaviour |
|--------|-----------|
| `list_models() → list[ModelInfo]` | GET `/v1/models`, parse `data[].id`, apply vision heuristic, sort vision-capable first |
| `validate_connection() → bool` | GET `/health`; fall back to `/v1/models` on 404. Raises `LlamaConnectionError` on failure |
| `analyze_image(path: Path) → tuple[str, str]` | POST `/v1/chat/completions` with text prompt + base64 image content part. Returns `(category, description)`. Same prompt and parsing logic as current `OllamaClient` |

**Config:**
- `LLAMA_BASE_URL` — default `http://localhost:8080`
- `LLAMA_MODEL` — default `qwen3-vl-8b`
- `LLAMA_TIMEOUT` — default `120` (reuses `OLLAMA_TIMEOUT` env var for backward compat)

**Backward compat:**
```python
# src/ollama_client.py (entire file after change)
from llama_client import LlamaClient as OllamaClient, LlamaConnectionError as OllamaConnectionError, LlamaResponseError as OllamaResponseError  # noqa: F401
```

**Exceptions:**
- `LlamaConnectionError` — cannot reach server
- `LlamaResponseError` — response cannot be parsed into category/description

---

### 2. Input/Output Directories

**New config vars (added to `Config`):**

| Var | Env key | Default |
|-----|---------|---------|
| `INPUT_FOLDER` | `INPUT_FOLDER` | Falls back to `IMAGE_FOLDER` if not set |
| `OUTPUT_FOLDER` | `OUTPUT_FOLDER` | `""` (empty = no output dir configured) |

**`IMAGE_FOLDER` is preserved** as the primary single-folder config for existing CLI users. When `INPUT_FOLDER` is set it takes precedence for scanning; `IMAGE_FOLDER` is then used as the rename-in-place target as before.

**`ImageProcessor.move_to_output(dry_run: bool = False) → MoveResult`:**
- Moves all files that were successfully renamed in the current session from their current location to `OUTPUT_FOLDER`.
- If `OUTPUT_FOLDER` is empty or `dry_run=True`, logs what would be moved and returns without acting.
- Filename conflicts resolved with the same `-2`, `-3` suffix logic already in place.
- Returns `MoveResult(moved: int, skipped: int, errors: list[str])`.

**CLI additions:**
```
python main.py --input-folder PATH   # override INPUT_FOLDER
python main.py --output-folder PATH  # override OUTPUT_FOLDER
python main.py --move-after          # run move_to_output after processing
```

---

### 3. NiceGUI UI

#### Entry Point: `src/main_ui.py`

```python
from nicegui import ui
from ui import ImageNamerUI

app = ImageNamerUI()
app.build()
ui.run(native=True, title="ImageNamer", window_size=(820, 600))
```

`native=True` opens a standalone desktop window (embedded Chromium via pywebview). No browser tab required.

#### Styling

`src/styles/app.css` is adapted from `tauri-app-skeleton/src/styles/global.css`:
- Same CSS custom properties (`--bg-primary`, `--bg-secondary`, `--bg-tertiary`, `--border-color`, `--accent-color`, `--text-primary`, etc.)
- Same `[data-theme="dark"]` and `[data-theme="light"]` attribute-based theming
- Same `@media (prefers-color-scheme: dark)` auto-detection fallback

Injected into NiceGUI via:
```python
ui.add_head_html('<link rel="stylesheet" href="/styles/app.css">')
app.add_static_files('/styles', Path(__file__).parent / 'styles')
```

#### Layout

Side-by-side panels. Left panel takes 60% width, right panel 40%.

```
┌─────────────────────────────────────────────────────┐
│ ● ● ●   ImageNamer                             ⚙   │  titlebar
├────────────────────────────┬────────────────────────┤
│ CONTROLS                   │ SETTINGS               │
│                            │                        │
│ Input folder               │ Server URL             │
│ [D:\Dropbox\Wallpapers] [📁]│ [http://localhost:8080]│
│                            │                        │
│ Output folder              │ Theme                  │
│ [(optional)]           [📁]│ [Dark] [Light] [System]│
│                            │                        │
│ Model                      │ Max failures           │
│ [qwen3-vl-8b 👁]       [↺] │ [5]                    │
│                            │                        │
│ [▶ Run] [Dry-run] [Move →] │ ● Connected            │
│                            │                        │
│ Progress                   │                        │
│ [████████░░░░░] 12 / 28    │                        │
│                            │                        │
│ Log                   [✕]  │                        │
│ ✓ renamed: sunset-sky.jpg  │                        │
│ ✓ renamed: dog-brown.jpg   │                        │
│ → processing: IMG_0042.jpg │                        │
└────────────────────────────┴────────────────────────┘
```

#### Component Behaviour

**Model dropdown:**
- Populated on startup via `LlamaClient.list_models()`
- Vision-capable models shown with 👁 badge and listed first
- Non-vision models listed below a divider, selectable with a warning tooltip
- Refresh button (↺) re-queries the server without restarting the app
- If server is unreachable on startup, dropdown shows last-used model from `.env` with a warning

**Buttons:**
| Button | Enabled when | Action |
|--------|-------------|--------|
| ▶ Run | Not currently running | `processor.process_all(dry_run=False)` |
| Dry-run | Not currently running | `processor.process_all(dry_run=True)` |
| Move → | Run completed, `OUTPUT_FOLDER` set, ≥1 rename succeeded | `processor.move_to_output()` |

All three disabled while a run is in progress.

**Live log:**
- `ImageProcessor` accepts an optional `progress_callback: Callable[[str, str], None]` — called with `(level, message)` where level is `info`, `success`, `warning`, `error`
- UI appends colour-coded lines in real time via NiceGUI's async `ui.run_coroutine` + `log.push()`
- Clear button (✕) wipes the log display only (does not affect `failures.json`)

**Progress bar:**
- Shows `current / total` images
- Hidden when idle, visible during a run

**Theme toggle:**
- Three-way pill: `Dark` / `Light` / `System`
- Applies `data-theme` attribute to `document.documentElement` via `ui.run_javascript`
- Persisted to `.env` as `UI_THEME=dark|light|system` on change

**Connection status:**
- Green dot + "Connected" when `validate_connection()` passes
- Red dot + "Disconnected" with server URL shown when it fails
- Re-checked on each Run/Dry-run, and on ↺ refresh

---

## Test Strategy (TDD)

Tests are written before implementation code. Each test must be observed to fail before the corresponding implementation is written.

### Test Infrastructure

**Stack:** `pytest` + `pytest-mock` + `responses` (HTTP mocking)

**`tests/conftest.py` fixtures:**
- `tmp_image_dir` — temp directory pre-populated with small valid JPG/PNG fixtures
- `mock_llama_server` — `responses` context that mocks `/v1/models`, `/v1/chat/completions`, `/health`
- `sample_model_list` — fixture returning a realistic `/v1/models` JSON payload including vision and non-vision models

### `test_llama_client.py`

| Test | Behaviour verified |
|------|--------------------|
| `test_list_models_returns_model_ids` | Returns list of `ModelInfo` objects with correct ids |
| `test_vision_flag_set_for_vl_in_name` | `qwen3-vl-8b` → `is_vision=True` |
| `test_vision_flag_set_for_gemma4` | `gemma4-e4b` → `is_vision=True` |
| `test_vision_flag_false_for_text_model` | `qwen3.5-9b` → `is_vision=False` |
| `test_vision_models_sorted_first` | Vision models appear before non-vision in returned list |
| `test_analyze_image_sends_base64` | Request body contains `image_url` content part with base64 data |
| `test_analyze_image_returns_category_description` | Parses `CATEGORY: / DESCRIPTION:` from response |
| `test_analyze_image_raises_on_bad_response` | `LlamaResponseError` when response lacks expected format |
| `test_validate_connection_true_on_200` | Returns `True` on successful `/health` |
| `test_validate_connection_raises_on_failure` | Raises `LlamaConnectionError` on connection refused |

### `test_image_processor.py`

| Test | Behaviour verified |
|------|--------------------|
| `test_rename_in_place` | File renamed in its source directory |
| `test_rename_dry_run_no_change` | Dry-run logs but does not rename |
| `test_separate_input_folder_scanned` | `INPUT_FOLDER` overrides `IMAGE_FOLDER` for discovery |
| `test_move_to_output_moves_renamed_files` | Files moved to `OUTPUT_FOLDER` after successful run |
| `test_move_to_output_dry_run_no_move` | `move_to_output(dry_run=True)` logs but does not move |
| `test_move_to_output_noop_when_no_output_folder` | No-op when `OUTPUT_FOLDER` is empty |
| `test_move_resolves_filename_conflict` | Numeric suffix applied when destination file already exists |

### `test_config.py`

| Test | Behaviour verified |
|------|--------------------|
| `test_input_folder_defaults_to_image_folder` | `INPUT_FOLDER` not set → falls back to `IMAGE_FOLDER` |
| `test_output_folder_defaults_empty` | `OUTPUT_FOLDER` not set → empty string |
| `test_llama_base_url_default` | `LLAMA_BASE_URL` defaults to `http://localhost:8080` |
| `test_llama_model_default` | `LLAMA_MODEL` defaults to `qwen3-vl-8b` |
| `test_llama_timeout_inherits_ollama_timeout_env` | `OLLAMA_TIMEOUT` env var still works |

### `test_ui_logic.py`

| Test | Behaviour verified |
|------|--------------------|
| `test_model_dropdown_populated_from_client` | Dropdown items match `list_models()` return value |
| `test_vision_models_have_badge` | Vision models include 👁 in their label text |
| `test_move_button_disabled_before_run` | Move button starts disabled |
| `test_move_button_enabled_after_successful_run` | Enabled after ≥1 rename and `OUTPUT_FOLDER` set |
| `test_progress_callback_appends_to_log` | Log receives messages emitted by processor callback |
| `test_run_button_disabled_during_run` | Run + Dry-run buttons disabled while processing |

---

## Not In Scope

- Packaging / installer
- Remote server support (non-localhost llama-swap)
- Batch undo / rename history
- Image preview in UI
- Visual/CSS pixel-accuracy testing (verified manually)

---

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Ollama vs llama-swap | llama-swap / llama-server; Ollama shim kept for backward compat |
| UI framework | NiceGUI with `native=True` |
| Input/output mode | Rename in-place; explicit Move button for second-phase output |
| Vision tagging | Name-pattern heuristic; no server metadata available |
| UI layout | Side-by-side panels (controls left, settings right) |
| Dark/light mode | CSS tokens from tauri-app-skeleton; `data-theme` attribute toggle |
| Test approach | TDD throughout; HTTP mocked via `responses` library |
