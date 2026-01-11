# ImageNamer Architecture

## Overview

ImageNamer is a modular, production-grade Python application that automatically renames images based on AI-powered content recognition using Ollama's qwen3-vl vision model. The architecture prioritizes separation of concerns, configurability, resilience, and extensibility.

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   main.py                           │
│          (Orchestration & CLI Entry Point)          │
└────────┬─────────────────────────────────┬──────────┘
         │                                  │
         ├──────────┬──────────────────┬───┴─────────┬──────────┐
         │          │                  │              │          │
    ┌────▼─┐  ┌────▼────┐  ┌──────────▼──┐  ┌───────▼──┐  ┌───▼────────┐
    │Config│  │  Logger │  │   Failure   │  │ Image    │  │   Ollama   │
    │      │  │  Setup  │  │   Logger    │  │Processor │  │   Client   │
    └──────┘  └─────────┘  └─────────────┘  └──────────┘  └────────────┘
```

## Module Responsibilities

### [config.py](src/config.py)

**Purpose**: Centralized configuration management

**Key Features**:
- Loads all configuration from environment variables with sensible defaults
- Defines all magic numbers and paths as class constants
- Provides configuration validation
- Enables easy future modifications

**Key Classes**:
- `Config`: Central configuration class with class methods for validation

**Example Usage**:
```python
from config import Config
Config.validate()  # Validates setup
print(Config.OLLAMA_BASE_URL)  # http://localhost:11434
```

### [ollama_client.py](src/ollama_client.py)

**Purpose**: REST communication with Ollama instance

**Key Features**:
- Encapsulates all Ollama API interaction
- Sends images to qwen3-vl model for analysis
- Parses structured responses into (category, description) tuples
- Implements error handling and response validation
- Sanitizes filenames to prevent filesystem issues
- Connection validation

**Key Classes**:
- `OllamaClient`: REST API wrapper
- `OllamaConnectionError`: Connection-specific exceptions
- `OllamaResponseError`: Response parsing exceptions

**Key Methods**:
- `validate_connection()`: Test Ollama connectivity
- `analyze_image(image_path)`: Returns (category, description)
- `_parse_response(response_text)`: Extracts structured data from model output
- `_sanitize_filename_part(text)`: Removes problematic characters

**Design Notes**:
- Uses base64 encoding for image transmission
- Implements timeout handling for long-running requests
- Flexible initialization (allows dependency injection for testing)

### [image_processor.py](src/image_processor.py)

**Purpose**: Image discovery, analysis, and safe renaming

**Key Features**:
- Discovers all supported image formats in a folder
- Orchestrates image analysis via OllamaClient
- Generates logical filenames from analysis results
- Handles filename conflicts with numeric suffixes
- Safe file renaming with error handling
- End-to-end image processing pipeline

**Key Classes**:
- `ImageProcessor`: Main image handling orchestrator

**Key Methods**:
- `discover_images()`: Find all supported images
- `analyze_and_generate_filename(image_path)`: Analysis + naming
- `_generate_filename(category, description, ext)`: Creates [category]-[description].ext format
- `resolve_filename_conflict(proposed, path)`: Adds -2, -3 suffix if needed
- `rename_image(image_path, new_filename, dry_run)`: Safely renames file
- `process_image(image_path, dry_run)`: Complete pipeline for one image

**Design Notes**:
- Supports formats: .jpg, .jpeg, .png, .webp
- Filename format: `[category]-[description].ext`
- Conflict resolution appends numeric suffixes: `-2`, `-3`, etc.
- Dry-run mode for safe previewing
- Per-image error handling (one failure doesn't stop batch)

### [failure_logger.py](src/failure_logger.py)

**Purpose**: Persistent failure tracking and retry management

**Key Features**:
- JSON-based failure log for persistence across runs
- Tracks failure history with timestamps
- Supports success status updates (preserving failure history)
- Enables selective retry of failed images
- Comprehensive failure records with error messages

**Key Classes**:
- `FailureLog`: Manages persistent failure tracking

**Key Methods**:
- `log_failure(filename, error_msg, retry_count)`: Record a failure
- `log_success(filename)`: Mark as success (preserves failure history)
- `get_pending_failures()`: Get filenames ready for retry
- `get_all_failures()`: Get all failure records
- `clear_file(filename)`: Remove from failure log

**Failure Record Schema**:
```json
{
  "filename": "image.jpg",
  "first_attempt": "2026-01-10T14:30:00",
  "last_attempt": "2026-01-10T14:35:00",
  "retry_count": 2,
  "status": "pending|success|failed",
  "errors": ["Error message 1", "Error message 2"],
  "success_time": "2026-01-10T14:40:00"  // Only if status=success
}
```

### [main.py](src/main.py)

**Purpose**: Orchestration and CLI entry point

**Key Features**:
- Dual logging (file + console)
- Command-line argument parsing
- Configuration validation
- Batch image processing with progress tracking
- Consecutive failure detection and abort
- Comprehensive result reporting
- Support for dry-run and retry modes

**Key Functions**:
- `setup_logging()`: Configure dual logging system
- `main()`: Primary orchestration and CLI handler

**CLI Arguments**:
- `--dry-run`: Preview changes without modifying files
- `--retry-failures`: Retry only previously failed images
- `--image-folder`: Override IMAGE_FOLDER from environment

**Consecutive Failure Logic**:
- Tracks consecutive failures across batch
- Aborts if threshold (MAX_CONSECUTIVE_FAILURES, default: 5) is exceeded
- Prevents runaway API calls when service is down

**Logging Levels**:
- **File**: DEBUG (all details)
- **Console**: INFO (user-friendly progress)

## Data Flow

### Normal Processing Flow

```
1. main.py initialization
   └─> setup_logging()
   └─> Config.validate()
   └─> OllamaClient.validate_connection()

2. Image discovery
   └─> ImageProcessor.discover_images() -> [Path, ...]

3. For each image:
   ├─> ImageProcessor.analyze_and_generate_filename()
   │   ├─> OllamaClient.analyze_image()
   │   │   ├─> Read image & base64 encode
   │   │   ├─> POST to Ollama API
   │   │   └─> Parse response -> (category, description)
   │   └─> ImageProcessor._generate_filename()
   │
   ├─> ImageProcessor.resolve_filename_conflict()
   │   └─> Check for existing file, append suffix if needed
   │
   ├─> ImageProcessor.rename_image()
   │   └─> Execute rename (or log if --dry-run)
   │
   ├─> Success
   │   └─> FailureLog.log_success()
   │
   └─> Failure
       └─> FailureLog.log_failure()
       └─> Track consecutive_failures++
       └─> If consecutive_failures >= MAX_CONSECUTIVE_FAILURES
           └─> Abort processing

4. Report summary
   └─> Log successes, failures, and next steps
```

### Failure Retry Flow

```
1. main.py --retry-failures
   └─> FailureLog.get_pending_failures()

2. Process pending images (same as normal flow)

3. On success
   └─> FailureLog.log_success() -> status changed to "success"

4. On continued failure
   └─> FailureLog.log_failure() -> increments errors list
```

## Configuration Hierarchy

```
Defaults (hardcoded in config.py)
    ↓
Environment Variables (.env file)
    ↓
CLI Arguments (--image-folder overrides)
```

Example: IMAGE_FOLDER resolution
1. Starts with default: `~/.Pictures`
2. Checked if defined in `.env`: `IMAGE_FOLDER=/custom/path`
3. Can be overridden by CLI: `--image-folder /cli/path`

## Error Handling Strategy

### Per-Image Errors
- **Cause**: Network timeout, invalid response format, etc.
- **Handling**: Log error, skip image, continue processing
- **Recovery**: User can retry with `--retry-failures`

### Service-Level Errors
- **Cause**: Ollama down, model broken
- **Symptom**: N consecutive image failures
- **Handling**: Abort processing to prevent wasted resources
- **Recovery**: Fix underlying issue, use `--retry-failures`

### System Errors
- **Cause**: File permissions, missing folders, disk issues
- **Handling**: Log and terminate with error code
- **Recovery**: Address system issue and restart

## Extensibility Points

### 1. Add New Image Formats
```python
# In config.py
SUPPORTED_FORMATS: Set[str] = {"jpg", "jpeg", "png", "webp", "gif"}
```

### 2. Change Naming Convention
```python
# In image_processor.py - modify _generate_filename()
# E.g., to use timestamp: f"{timestamp}-{category}-{description}"
```

### 3. Add New Ollama Model
```python
# In .env
OLLAMA_MODEL=llava:34b
```

### 4. Implement Different Analysis Strategy
```python
# Create new client class inheriting from or replacing OllamaClient
# Override analyze_image() method
```

### 5. Add Database Logging
```python
# In failure_logger.py - add new FailureLog subclass
# Implement save/load with database instead of JSON
```

## Testing Strategy (Recommendations)

### Unit Tests
```python
# Test OllamaClient._sanitize_filename_part()
# Test ImageProcessor._generate_filename()
# Test ImageProcessor.resolve_filename_conflict()
```

### Integration Tests
```python
# Mock Ollama API responses
# Test end-to-end processing with sample images
# Test failure logging and retry
```

### System Tests
```python
# With real Ollama instance
# With real image folders
# Test all CLI flags
```

## Performance Considerations

### Bottlenecks
1. **Ollama API calls**: ~30-120s per image depending on model
2. **Network latency**: Between local script and Ollama instance
3. **Disk I/O**: Reading images and writing renamed files

### Optimization Opportunities
1. **Batch processing**: Send multiple images to Ollama in parallel
2. **Caching**: Cache analysis results to avoid re-processing
3. **Async I/O**: Use asyncio for concurrent API calls

### Current Design
- Sequential processing (simple, reliable)
- Per-image timeout handling
- Configurable timeout via `OLLAMA_TIMEOUT`

## Security Considerations

1. **File Access**: Only reads/writes image files in specified folder
2. **API Communication**: HTTP to localhost (no encryption needed for typical setup)
3. **Error Messages**: All logged locally (no remote telemetry)
4. **Input Validation**: File paths, model names, URLs validated
5. **Filename Sanitization**: Prevents directory traversal and special character issues

## Future Enhancements

1. **Parallel Processing**: Process multiple images concurrently
2. **Database Backend**: Store analysis results in database
3. **Web UI**: Dashboard to monitor processing, review results
4. **Custom Models**: Support for alternative vision models
5. **Advanced Conflict Resolution**: Merge strategies, manual review mode
6. **Scheduled Runs**: Cron integration for automatic processing
7. **Webhook Integration**: Notify external systems on completion

---

**Version**: 1.0
**Last Updated**: January 10, 2026
