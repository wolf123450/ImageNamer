# ImageNamer: AI-Powered Image Renaming Tool

Automatically rename images based on AI-powered content recognition using Ollama's qwen3-vl vision model.

## Features

- **AI-Powered Image Analysis**: Uses Ollama's qwen3-vl:30b model to understand image content
- **Intelligent Renaming**: Generates logical filenames in format `[category]-[description]`
- **Error Handling**: Automatically skips failed images and logs them for retry
- **Resilient Processing**: Aborts on service issues (e.g., Ollama unavailable after N consecutive failures)
- **Dry-Run Mode**: Preview all changes before applying
- **Retry Support**: Re-process previously failed images with `--retry-failures`
- **Comprehensive Logging**: File and console logging with full operation history
- **Production-Grade Code**: Modular, well-documented, easily extensible

## Requirements

- Python 3.8+
- Ollama instance running and accessible (default: `http://localhost:11434`)
- qwen3-vl:30b model installed in Ollama

## Installation

1. Clone/download this repository

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your settings:
   # - OLLAMA_BASE_URL: URL to your Ollama instance
   # - IMAGE_FOLDER: Path to folder with images
   # - MAX_CONSECUTIVE_FAILURES: Failure threshold (default: 5)
   ```

4. Ensure Ollama is running and the model is available:
   ```bash
   ollama pull qwen3-vl:30b
   ```

## Usage

### Basic Usage

Process all images in configured folder:
```bash
cd src
python main.py
```

### Preview Changes (Dry-Run)

See what changes would be made without modifying files:
```bash
cd src
python main.py --dry-run
```

### Retry Failed Images

Re-process images that previously failed:
```bash
cd src
python main.py --retry-failures
```

### Override Image Folder

Process a specific folder:
```bash
cd src
python main.py --image-folder /path/to/images
```

### Combined Options

```bash
cd src
python main.py --image-folder /path/to/images --dry-run
```

## Configuration

All configuration is managed through environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Vision model name | `qwen3-vl:30b` |
| `OLLAMA_TIMEOUT` | Request timeout (seconds) | `120` |
| `IMAGE_FOLDER` | Folder with images to process | `~/Pictures` |
| `MAX_CONSECUTIVE_FAILURES` | Abort threshold on consecutive failures | `5` |

## Output

### Logs

- **Console**: Real-time progress with INFO level messages
- **File**: Detailed logs in `logs/image_namer.log` including DEBUG level messages
- **Failures**: Persistent failure log in `logs/failures.json` for retry support

### Filename Format

Images are renamed to: `[category]-[description].ext`

Examples:
- `animal-brown_dog.jpg`
- `landscape-mountain_sunset.png`
- `food-chocolate_cake.webp`

### Conflict Resolution

If a filename already exists, a numeric suffix is appended:
- `animal-brown_dog.jpg` (original)
- `animal-brown_dog-2.jpg` (conflict)
- `animal-brown_dog-3.jpg` (another conflict)

## Supported Image Formats

- `.jpg` / `.jpeg`
- `.png`
- `.webp`

## How It Works

1. **Discovery**: Scans the image folder for supported image formats
2. **Analysis**: Sends each image to Ollama's qwen3-vl:30b model
3. **Parsing**: Extracts category and description from model response
4. **Renaming**: Generates logical filename and safely renames the file
5. **Logging**: Tracks successes and failures for future retries

### Failure Handling

- Individual image failures don't stop processing of other images
- Failed images are logged to `logs/failures.json` with error details
- If N consecutive images fail (where N = `MAX_CONSECUTIVE_FAILURES`), processing aborts
  - This typically indicates Ollama is down or the model is broken
- Use `--retry-failures` to re-process failed images later

## Project Structure

```
ImageNamer/
├── src/
│   ├── main.py              # Main entry point and orchestration
│   ├── config.py            # Configuration management
│   ├── ollama_client.py     # Ollama REST API client
│   ├── image_processor.py   # Image discovery, analysis, renaming
│   └── failure_logger.py    # Failure tracking and logging
├── logs/
│   ├── image_namer.log      # Detailed operation log
│   └── failures.json        # Persistent failure tracking
├── requirements.txt         # Python dependencies
├── .env.example            # Example configuration
└── README.md               # This file
```

## Design Principles

- **Modularity**: Each component has a single, well-defined responsibility
- **Configurability**: All magic numbers are configurable constants or environment variables
- **Resilience**: Graceful failure handling with comprehensive logging
- **Production-Grade**: Type hints, docstrings, error handling, logging
- **Extensibility**: Easy to add new features or modify existing ones

## Troubleshooting

### "Cannot reach Ollama at http://localhost:11434"
- Ensure Ollama is running: `ollama serve`
- Check `OLLAMA_BASE_URL` in `.env` is correct
- Test connectivity: `curl http://localhost:11434/api/tags`

### "Could not parse category or description from response"
- Check that qwen3-vl:30b model is installed: `ollama list`
- Ensure model is properly pulled: `ollama pull qwen3-vl:30b`

### Script aborts after N consecutive failures
- This is intentional—it likely means Ollama is down or model is broken
- Fix the underlying issue, then use `--retry-failures` to continue

### File permissions denied
- Ensure you have write permissions to `IMAGE_FOLDER`
- Check the file isn't in use by another application

## License

[Your License Here]

## Contributing

[Contributing Guidelines Here]
