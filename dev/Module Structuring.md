# Module Structuring

## Problem

Several modules used flat or binary section labels (`# Helper functions`, `# Primary functions`, `# Internal helpers`, `# External helpers`) that didn't reflect the actual dependency structure of the code. The labels were too coarse, causing unrelated functions to share sections, private helpers to be separated from the functions they support, and dataclasses to be scattered throughout the file.

## Convention: `# region` / `# endregion`

Use VS Code's native region markers as section separators:

```python
# region Section Name

... definitions ...

# endregion
```

**Why this approach:**
- VS Code supports code folding on `# region` blocks
- Region names appear in the minimap on hover
- Recognized by Pylance/Pyright
- Pure comment — no runtime cost, no imports
- More semantic than `# ---` dividers

## Section Taxonomy

Sections are ordered **shallowest to deepest dependency** — code that has no internal dependencies comes first; code that depends on everything else comes last.

| Section | Contents | Notes |
|---|---|---|
| **Data** | Dataclasses, type aliases, module-level constants | No logic, no dependencies |
| **Configuration** | `Namespace` (argparse), stateful config classes (e.g., `SavedDateContext`) | May depend on Data |
| **Utilities** | Pure helpers with no intra-module dependencies | Broadly reused across the file |
| **[Domain]** | Optional mid-tier section named for its domain (e.g., `Archive`, `Transfer`) | Use when there's a coherent infrastructure layer below Features |
| **Features** | Public-facing entry points; per-feature groups with private helpers co-located | Depends on everything above |
| **CLI** | `parse_args`, `_validate_function_args`, `main` | Always last |

Not every module needs all sections. `common.py`, for example, has no Configuration or Features sections — just Data, Logging, File System, and Strings.

## Co-location Principle

Private helpers (underscore-prefixed functions) should be placed **immediately above the function that calls them**, not collected into a generic internal helpers section. This makes the dependency relationship self-documenting.

```python
# region Features

def _build_track_index(collection):       # private helper for merge_collections
    ...

def _merge_playlist_references(...):      # private helper for merge_collections
    ...

def merge_collections(primary, secondary): # consumer — helpers are right above it
    ...

def _add_playlist_tracks(base_root, ...): # private helper for record_dynamic_tracks
    ...

def record_dynamic_tracks(...):           # consumer
    ...

# endregion
```

If a private helper is used by **multiple** functions across the file, it belongs in Utilities instead.

## Process for Restructuring a File

1. **Read the file top to bottom** and catalogue every definition with its type (dataclass, class, private function, public function).

2. **Trace dependencies** for each function: what does it call within the same file? Build a rough dependency graph. Depth = number of hops to a function with no intra-module dependencies.

3. **Identify the section breakdown** using the taxonomy above. Name domain-specific sections after what they do (e.g., `Archive`, `Transfer`, `Sync Engine`) rather than generic labels like `Helpers`.

4. **Group private helpers with their consumers** in the Features section. If a private helper serves only one function, it goes immediately above that function. If it serves multiple, move it up to Utilities.

5. **Write the file** preserving all logic exactly — this is pure reorganization. No behavioral changes.

6. **Verify** by running the existing test suite. Because no logic changes, all tests must pass unchanged.

## Applied Examples

### sync.py — 7 sections
`Data` → `Configuration` (Namespace, SavedDateContext) → `Utilities` (format_timing, relative_paths) → `Transfer` (transform_implied_path, rsync_healthcheck, transfer_files) → `Sync Engine` (key_date_context, create_sync_mappings, sync_batch, sync_mappings) → `Features` (preview_sync, run_music, run_playlist) → `CLI`

Key moves: `SyncPreviewTrack` dataclass moved from mid-file to join other dataclasses at top; `rsync_healthcheck` moved adjacent to `transfer_files`; `parse_args` moved from between classes and helpers to CLI section.

### library.py — 5 sections
`Data` → `Configuration` → `Utilities` (XML/path helpers, broadly reused `_create_track_metadata`) → `Features` (private helpers co-located per consumer) → `CLI`

Key moves: `Namespace` and `parse_args` were at the very top before dataclasses — moved `Namespace` to Configuration, `parse_args` to CLI. Four clusters of private helpers (`_full_path`, merge helpers, playlist helpers) each placed immediately above their single consumer.

### music.py — 5 sections
`Data` → `Configuration` → `Utilities` (is_prefix_match, has_no_user_files, get_dirs, prune) → `Archive` (extract_all_normalized_encodings, flatten_zip, compress_dir) → `Features` → `CLI`

Key move: `Archive` is a domain section that sits between Utilities and Features — it's infrastructure (zip I/O) that Features depends on, but isn't general enough to be a Utility.

### common.py — 4 sections
`Data` → `Logging` → `File System` → `Strings`

No Configuration, Features, or CLI because `common.py` is a pure utility module with no classes and no entry point.

## Remaining Files

### Core modules (apply full process)
- `encode.py` — async batch encoding; likely has Utilities + async layers
- `playlist.py` — TSV parsing, M3U8 generation, Mix dataclass
- `tags.py` — mutagen-based metadata extraction; likely class-heavy
- `tags_info.py` — tag comparison utilities
- `subsonic_client.py` — API client; likely Configuration + Transfer + Features
- `tags_sort.py` — directory sorting logic
- `genre.py` — genre analysis and reporting
- `batch_general.py` — bulk file operations
- `restore_metadata.py` — collection restoration

### Config/constants (likely minimal changes)
- `config.py` — path constants; probably just a Data section or no regions needed
- `constants.py` — pure constants; same

### UI files (11 files)
Apply the same taxonomy. Streamlit page files typically follow: Data → Configuration → Utilities → Features (render functions) — no CLI section since Streamlit pages don't use `main`.
