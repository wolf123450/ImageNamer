# Three-Phase Workflow Design

**Date:** 2026-04-20  
**Status:** Approved  

---

## Goal

Replace the current Run / Dry-run / Move workflow with a three-phase Run / Apply Names / Move model. **Run** is now purely analytical — it calls the AI, proposes names, and saves results to JSON. No files are changed until the user explicitly clicks **Apply Names**. The user can review, edit, and selectively approve individual proposals in an editable table before applying.

---

## Background

Current flow:
1. **Run** — analyzes images AND renames them in one shot
2. **Dry-run** — same but only prints what would happen
3. **Move →** — moves renamed files to output folder

Problem: the user has no opportunity to review or correct AI-suggested names before files are touched.

New flow:
1. **▶ Run** — AI analysis only; writes `_imagenamer_proposals.json` to the input folder; shows proposals table
2. **Apply Names** — renames files listed as `selected=True, status=pending` in the table; updates JSON
3. **Move →** — moves renamed files to output folder (unchanged from current)

"Dry-run" is removed as a distinct button — Run is already a safe no-file-change preview step.

---

## Data Model

### `ImageProposal`

```python
@dataclass
class ImageProposal:
    original_path: str    # absolute path to the file
    proposed_name: str    # filename only (no directory), includes extension; user-editable
    selected: bool        # checkbox state in the UI (default True)
    status: str           # "pending" | "applied" | "skipped" | "error"
    error: str            # populated when status == "error", empty otherwise
```

### JSON Schema (`_imagenamer_proposals.json`)

```json
{
  "folder": "/abs/path/to/input",
  "generated_at": "2026-04-20T14:30:00",
  "proposals": [
    {
      "original_path": "/abs/path/to/input/IMG_001.jpg",
      "proposed_name": "dog-running-park.jpg",
      "selected": true,
      "status": "pending",
      "error": ""
    }
  ]
}
```

File location: `{input_folder}/_imagenamer_proposals.json`. Written by Run, updated in-place by Apply.

### Resume Behaviour

When Run is called a second time on the same folder:
- Load existing JSON (if present)
- Skip images whose entry has `status == "applied"` (already done)
- Re-queue images whose entry has `status == "error"` (retry failures)
- Add new images not yet in the file
- Images with `status == "pending"` are re-analyzed and their `proposed_name` is refreshed

---

## New Module: `src/proposals.py`

Single responsibility: JSON persistence for proposals. No UI or processor logic.

```python
def load(folder: Path) -> List[ImageProposal]: ...
def save(folder: Path, proposals: List[ImageProposal]) -> None: ...
def merge(existing: List[ImageProposal], discovered: List[Path]) -> List[ImageProposal]: ...
```

`merge` implements the resume logic: given the existing proposal list and the freshly-discovered image paths, returns the correctly-combined list to pass to the analyzer.

---

## `image_processor.py` Changes

### New method: `analyze_only() → List[ImageProposal]`

- Discovers images in `image_folder`
- Calls `proposals.load()` to load existing JSON (if any)
- Calls `proposals.merge()` to build the work list
- For each image to process: calls the AI, creates/updates its `ImageProposal`
- Emits progress via `_emit()`
- Saves updated JSON via `proposals.save()` after every image (safe against mid-run interruption)
- Returns the full proposal list

### New method: `apply_proposals(proposals: List[ImageProposal]) → Tuple[int, int]`

- For each proposal where `selected=True` and `status="pending"`:
  - Resolves filename conflicts (`resolve_filename_conflict`)
  - Renames the file
  - Updates `proposal.status` to `"applied"` (or `"error"`)
  - Appends renamed path to `self._renamed_files` (for Move phase)
- Saves updated JSON via `proposals.save()`
- Returns `(success_count, failure_count)`

### `process_all()` compatibility

`process_all(dry_run=False)` becomes a thin wrapper that calls `analyze_only()` then `apply_proposals()` (when `dry_run=False`), keeping all existing tests green and the CLI backward-compatible.

When `dry_run=True`, `process_all()` calls `analyze_only()` only (no file changes) and logs the proposals — same observable behavior as the old dry-run.

---

## UI Changes (`src/ui.py` + `src/ui_state.py`)

### Button bar

| Old | New |
|-----|-----|
| ▶ Run | ▶ Run |
| Dry-run | *(removed)* |
| Move → | Apply Names |
| *(none)* | Move → |

Button enable logic:
- **Run** — enabled when not running
- **Apply Names** — enabled when `pending_count > 0` and not running
- **Move →** — enabled when `applied_count > 0` and output folder set and not running

### Proposals table

Inserted between the button bar and the log panel. Implemented with `ui.table` or `ui.aggrid` with per-row:
- Checkbox (`selected`)
- Original filename (read-only)
- Proposed name (editable `ui.input`)
- Status badge (colored span using existing CSS classes)

Below the table: **✓ Select All** / **✗ Select None** buttons.

### `UIState` additions

```python
proposals: List[ImageProposal] = field(default_factory=list)

@property
def pending_count(self) -> int:
    return sum(1 for p in self.proposals if p.selected and p.status == "pending")

@property
def applied_count(self) -> int:
    return sum(1 for p in self.proposals if p.status == "applied")

@property
def apply_button_enabled(self) -> bool:
    return not self.is_running and self.pending_count > 0

@property
def move_button_enabled(self) -> bool:
    return not self.is_running and self.applied_count > 0 and bool(self.output_folder)
```

---

## CLI Changes (`src/main.py`)

New phase flags (mutually exclusive, default is all phases):

| Flag | Behavior |
|------|----------|
| *(none)* | Backward compat: analyze → apply → optionally move. Same as today. |
| `--analyze` | Phase 1 only: run AI, write JSON, print proposals table |
| `--apply` | Phase 2 only: load JSON, rename selected pending proposals |
| `--move-after` | Phase 3: move renamed files (unchanged) |
| `--dry-run` | With `--analyze`: prints proposals, does NOT write JSON. With no flags: old preview behavior. |

---

## File Map

| File | Action | Notes |
|------|--------|-------|
| `src/proposals.py` | **Create** | `ImageProposal` dataclass + `load/save/merge` |
| `src/image_processor.py` | **Modify** | Add `analyze_only`, `apply_proposals`; refactor `process_all` |
| `src/ui_state.py` | **Modify** | Add `proposals`, `pending_count`, `applied_count`, updated button properties |
| `src/ui.py` | **Modify** | New button bar, proposals table, `_run/_apply/_move` handlers |
| `src/main.py` | **Modify** | `--analyze` / `--apply` flags |
| `tests/test_proposals.py` | **Create** | Unit tests for `ProposalStore` load/save/merge |
| `tests/test_image_processor.py` | **Modify** | Tests for `analyze_only`, `apply_proposals`, updated `process_all` |
| `tests/test_ui_logic.py` | **Modify** | Tests for updated `UIState` properties |

---

## Out of Scope

- Undo/redo of applied renames
- Multi-folder batch mode
- Conflict resolution UI (auto-suffix `-2/-3` is retained as-is)
- Thumbnail preview in the table
