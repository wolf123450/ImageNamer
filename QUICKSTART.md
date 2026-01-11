# Quick Start Guide

## Setup (One-time)

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Ensure Ollama is running**:
   ```bash
   ollama serve
   # In another terminal:
   ollama pull qwen3-vl:30b
   ```

## Basic Usage

### Preview Changes (Recommended First Step)

```bash
cd src
python main.py --dry-run
```

This shows what would happen without modifying any files.

### Process Images

```bash
cd src
python main.py
```

### Retry Failed Images

```bash
cd src
python main.py --retry-failures
```

### Process Specific Folder

```bash
cd src
python main.py --image-folder C:\path\to\images
```

## Understanding the Output

### Console Output
- `INFO`: Status messages and progress
- `WARNING`: Images that couldn't be processed
- `ERROR`: System issues

### Log Files
- `logs/image_namer.log`: Full detailed log of all operations
- `logs/failures.json`: Failed images with error details (for retries)

### Result
- Images are renamed to: `[category]-[description].[ext]`
- Example: `animal-brown_dog.jpg`, `landscape-sunset.png`
- If filename exists, numeric suffix is added: `animal-brown_dog-2.jpg`

## Common Scenarios

### Scenario 1: First Run (Safe)
```bash
cd src
python main.py --dry-run  # Preview
# Review output
python main.py            # Actually rename files
```

### Scenario 2: Some Failed
```bash
# See which failed
# (check console output and logs/failures.json)

# Fix the issue (e.g., restart Ollama if needed)
cd src
python main.py --retry-failures
```

### Scenario 3: Different Folder
```bash
cd src
python main.py --image-folder D:\MyPhotos --dry-run
python main.py --image-folder D:\MyPhotos
```

## Troubleshooting

**Q: "Cannot reach Ollama"**
- Is Ollama running? Run `ollama serve` in a terminal
- Check OLLAMA_BASE_URL in .env (default: http://localhost:11434)

**Q: Script aborted after 5 failures**
- Ollama is likely down or model is broken
- Fix the issue, then use `--retry-failures` to continue

**Q: Files not renaming**
- Check `logs/image_namer.log` for details
- Ensure you have write permissions to the image folder
- Run with `--dry-run` first to see what would happen

**Q: Want to change failure threshold**
- Edit `MAX_CONSECUTIVE_FAILURES` in `.env`

## Project Structure

```
src/
├── main.py              # Run this file
├── config.py            # Configuration (edit .env instead)
├── ollama_client.py     # Ollama integration
├── image_processor.py   # Image handling
└── failure_logger.py    # Failure tracking

logs/
├── image_namer.log      # Detailed operation log
└── failures.json        # Failed images for retry
```

## Next Steps

1. Try `python main.py --dry-run` to see what the script would do
2. Review the full [README.md](README.md) for detailed documentation
3. Check [logs/image_namer.log](logs/image_namer.log) for operation history
