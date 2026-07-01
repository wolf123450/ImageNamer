# ImageNamer

AI-powered image renaming tool. Sends images to a vision model and renames
them to descriptive filenames like `landscape-sunset-over-mountains.jpg`.

## Requirements

- Python 3.8+
- [llama-swap](https://github.com/mostlygeek/llama-swap) or
  [llama-server](https://github.com/ggerganov/llama.cpp) running locally
  with a vision-capable model loaded

## Starting the inference server

**llama-server** (single model — Qwen3-VL-8B, your model is in the HuggingFace cache):
```powershell
$qwen = "$env:USERPROFILE\.cache\huggingface\hub\models--unsloth--Qwen3-VL-8B-Instruct-GGUF\snapshots\b93a7ee713758252c555be4210c00540df954dc2"
llama-server -m "$qwen\Qwen3-VL-8B-Instruct-Q4_K_M.gguf" --mmproj "$qwen\mmproj-BF16.gguf" --port 8080 --n-gpu-layers 99
```

Or with Gemma4-E4B:
```powershell
$gemma = "$env:USERPROFILE\.cache\huggingface\hub\models--unsloth--gemma-4-E4B-it-GGUF\snapshots\ce152932ac27bc40bc9c727386760424d50bb456"
llama-server -m "$gemma\gemma-4-E4B-it-Q4_K_M.gguf" --mmproj "$gemma\mmproj-BF16.gguf" --port 8080 --n-gpu-layers 99
```

**llama-swap** (multi-model, loads on demand — recommended):
```powershell
llama-swap --config C:\models\swap.yaml
```

The app expects the server at `http://localhost:8080` by default (override with `LLAMA_BASE_URL` in `.env`).

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env with your folder paths and model name
```

## Usage

### Desktop UI

```powershell
python src/main_ui.py
```

Opens a native desktop window. Choose folders, select a model, then press
**▶ Run** or **Dry-run**. After a successful run, **Move →** becomes active
if an output folder is configured.

### CLI

```powershell
python src/main.py [options]
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview renames without changing files |
| `--input-folder PATH` | Override the folder to scan |
| `--output-folder PATH` | Override the destination folder |
| `--move-after` | Move renamed files to output folder when done |
| `--retry-failures` | Retry only images that previously failed |
| `--image-folder PATH` | Legacy: same as `--input-folder` |

### Examples

```powershell
# Dry-run on a specific folder
python src/main.py --input-folder "D:\Photos\Unsorted" --dry-run

# Full run with output relocation
python src/main.py --input-folder "D:\Photos\Unsorted" --output-folder "D:\Photos\Named" --move-after
```

## Configuration

Copy `.env.example` to `.env` and edit:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLAMA_BASE_URL` | `http://localhost:8080` | llama-swap / llama-server URL |
| `LLAMA_MODEL` | `qwen3-vl-8b` | Vision model name |
| `OLLAMA_TIMEOUT` | `120` | Request timeout (seconds) |
| `INPUT_FOLDER` | (from `IMAGE_FOLDER`) | Folder to scan |
| `OUTPUT_FOLDER` | `` | Move destination (empty = disabled) |
| `IMAGE_FOLDER` | `~/Pictures` | Legacy default input folder |
| `MAX_CONSECUTIVE_FAILURES` | `5` | Stop threshold for consecutive errors |
| `UI_THEME` | `system` | Desktop UI theme: `dark`, `light`, `system` |

## Running Tests

```powershell
pytest tests/ -v
```

## Architecture

```
src/
  llama_client.py     — OpenAI-compatible inference client
  ollama_client.py    — Compatibility shim (aliases LlamaClient)
  config.py           — Env-var configuration
  image_processor.py  — Discovery, rename, move logic
  failure_logger.py   — Persistent failure tracking (JSON)
  ui_state.py         — Pure-Python UI state helpers
  ui.py               — NiceGUI rendering
  main_ui.py          — Desktop UI entry point
  main.py             — CLI entry point
  styles/app.css      — CSS token stylesheet
tests/
  conftest.py         — Shared fixtures
  test_config.py
  test_llama_client.py
  test_image_processor.py
  test_ui_logic.py
```
