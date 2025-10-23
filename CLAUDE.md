# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General Instructions

**Communication Style**: Do not provide summaries of work completed unless explicitly requested by the user.

**Persisted Investigation Notes**: If information needs to be persisted across sessions, always store investigation findings, research notes, and session-specific documentation in the `claude/` directory (which is gitignored).

**Code Reuse**: Use existing utility functions from `common.py` and other modules before creating new ones. Check for functions like `find_date_context()`, `collect_paths()`, and `configure_log()` that may already provide the needed functionality.

## Coding Style

### String Quoting Conventions

**Primary Rule**: Favor single quotes `'` for all strings unless the string is formatted (f-strings).

**Examples**:
```python
# Regular strings - use single quotes
path = 'src/djmgmt/library.py'
error_msg = 'Unable to load XML collection'
extension = '.aiff'

# F-strings - use double quotes for the outer string
logging.info(f"Error in FUNCTION_RECORD_DYNAMIC: {e}")
output_path = f"{constants.REKORDBOX_ROOT}{file_path}"
item = f"{tags.artist}{tags.title}".lower()

# Nested quotes in f-strings - use double quotes outside, single quotes inside
file_url = f"{constants.REKORDBOX_ROOT}{quote(file_path, safe='()/')}"
```

**Exceptions**:
1. **XPath expressions**: Use double quotes for attribute values in XPath predicates to avoid escaping issues
   ```python
   existing_track = collection.find(f'./{constants.TAG_TRACK}[@{constants.ATTR_PATH}="{file_url}"]')
   ```

2. **Docstrings**: Use triple single quotes `'''` for module and function docstrings
   ```python
   '''
   Module-level docstring describing the module purpose
   '''

   def function_name():
       '''Function-level docstring describing the function.'''
   ```

3. **Multi-line strings with newlines**: Use double quotes when representing explicit newlines in messages
   ```python
   parser.error(f"invalid function '{args.function}'\nexpect one of '{'\n'.join(sorted(functions))}'")
   ```

### Additional Style Guidelines

Reference `src/djmgmt/tags_info.py` for comprehensive style patterns:

- **Type hints**: Always include type hints for function parameters and return values
  ```python
  def log_duplicates(root: str) -> list[str]:
  ```

- **Lambda functions**: Inline type annotations where clarity is needed
  ```python
  normalize_filename: Callable[[str], str] = lambda path: os.path.splitext(os.path.basename(path))[0]
  ```

- **Dictionary and set literals**: Favor compact single-line format when items are short
  ```python
  comparison_files = {}
  valid_extensions = {'.mp3', '.wav', '.aiff'}
  ```

- **Comments**: Use inline comments to explain intent, placed on the line before the code
  ```python
  # check for duplicates based on set contents
  count = len(file_set)
  ```

- **String concatenation**: Prefer f-strings over `+` or `.format()`
  ```python
  # Good
  path = f"{root}/{name}"

  # Avoid
  path = root + '/' + name
  ```

## Project Overview

This is a DJ management toolkit for organizing, encoding, tagging, and syncing music libraries. It processes music files (AIFF, WAV, MP3, FLAC), manages Rekordbox XML collections, and syncs tracks to a remote Navidrome media server via rsync.

## Running Tests

```bash
# Run all tests
python3 -m unittest discover -s test -p "test_*.py"

# Run a specific test file
python3 -m unittest test.test_common

# Run a specific test case
python3 -m unittest test.test_common.TestCollectPaths

# Run with verbose output
python3 -m unittest discover -s test -p "test_*.py" -v
```

## Running Scripts

All scripts are Python modules meant to be run from the project root:

```bash
# Process music files (sweep, extract, flatten, encode, prune)
python3 -m src.music process <input_dir> <output_dir> [--interactive]

# Update library: process files and sync to media server
python3 -m src.music update_library <source_dir> <library_path> \
  --client-mirror-path <mirror_path> \
  --collection-backup-directory <backup_dir>

# Organize library files by date added
python3 -m src.library date_paths <collection.xml> --root-path <path> [--metadata-path]

# Sync library to media server
python3 -m src.sync sync <collection.xml> <output_dir>

# Encode tracks (lossless or lossy)
python3 -m src.encode lossless <input_dir> <output_dir> --extension .aiff
python3 -m src.encode lossy <input_dir> <output_dir> --extension .mp3

# Find tracks missing cover art
python3 -m src.encode missing_art <input_path> <output_file> --scan-mode xml
python3 -m src.encode missing_art <input_dir> <output_file> --scan-mode os
```

## Type Checking

The project uses Pyright for type checking:

```bash
pyright src/
```

Configuration is in `pyrightconfig.json`. Note that `src/audacity_script_sample.py` is ignored.

## Architecture

### Core Data Flow

1. **Ingest**: Download music files → `music.sweep()` → temp directory
2. **Process**: Extract archives → flatten → encode to standard format → prune non-music files
3. **Organize**: Move to library with date-based structure (YYYY/MM month/DD/Artist/Album/)
4. **Record**: Update Rekordbox XML collection with metadata
5. **Sync**: Encode to MP3 → rsync to media server → trigger Navidrome scan

### Key Modules

**library.py**: Rekordbox XML collection management
- Parses Rekordbox XML collections and playlists
- Generates date-structured paths from DateAdded attributes
- Maps collection tracks to filesystem paths
- XPath queries for playlists: `_pruned`, `mixtapes`, `archive`, `unplayed`, `played`

**sync.py**: Media server synchronization
- Batch syncs files by date context (year/month/day)
- Uses rsync daemon for file transfer to Navidrome server
- Encodes lossless files to MP3 before transfer
- Triggers remote scans via Subsonic API
- Persists sync state to resume interrupted operations

**music.py**: Batch music file operations
- `process()`: End-to-end pipeline (sweep → extract → flatten → encode → prune)
- `update_library()`: Full workflow including sync to media server
- `record_collection()`: Updates XML with new tracks, generates UUIDs
- Handles zip archives from music stores (Beatport, Juno)

**encode.py**: Audio transcoding with ffmpeg
- Async batch encoding using asyncio
- Lossless: converts to 44.1kHz/16-bit AIFF
- Lossy: encodes to 320kbps MP3
- Detects and preserves cover art in video streams
- Finds tracks missing artwork

**tags.py**: Audio metadata extraction
- Uses mutagen for reading ID3, FLAC tags
- Extracts: artist, album, title, genre, key, cover image
- Perceptual image hashing for cover art comparison

### XML Collection Structure

The Rekordbox XML format (`collection.xml`) contains:
- `COLLECTION`: All tracks with metadata (TrackID, Location, DateAdded, Artist, etc.)
- `PLAYLISTS/NODE[@Name='_pruned']`: Curated library subset to sync
- `PLAYLISTS/NODE[@Name='mixtapes']`: Recorded sets (tracks are "played")
- `PLAYLISTS/NODE[@Name='unplayed']`: Dynamic playlist of unplayed pruned tracks

Track paths use `file://localhost` URL format. The library manages:
1. Collection tracks (source of truth for metadata)
2. Playlist references (by TrackID/Key)
3. Date-based organization via DateAdded attribute

### Date-Structured Paths

Music files are organized: `/YYYY/MM monthname/DD/Artist/Album/track.ext`

Example: `/2023/04 april/27/Artist Name/Album Title/track.aiff`

This structure:
- Preserves chronological discovery order
- Enables batch syncing by date context
- Allows resuming interrupted sync operations
- Maps directly from Rekordbox DateAdded attribute

### Remote Sync Configuration

Server connection defined in `constants.py`:
- Host: `corevega.local`
- Rsync daemon on port 12000
- Module: `navidrome`
- Protocol: `rsync://user@host:port/module`

Sync process validates rsync daemon availability before transfer.

## Important Constants

`PROJECT_ROOT`: Base directory for state files and logs
`REKORDBOX_ROOT`: URL prefix for collection paths (`file://localhost`)
`EXTENSIONS`: Supported audio formats: `.mp3`, `.wav`, `.aif`, `.aiff`, `.flac`

State files stored in `state/`:
- `processed-collection.xml`: Current library state
- `sync_state.txt`: Last synced date context
- `output/`: Various output files (missing art, track identifiers)

Logs written to `src/logs/` directory.

## Subsonic API Integration

The `subsonic_client.py` module interacts with the Navidrome server:
- Triggers library scans after file transfers
- Polls scan status until completion
- Uses Subsonic API for remote operations

## Common Patterns

**Logging**: All scripts use `common.configure_log()` to set up file-based logging in `src/logs/`

**Path Collection**: Use `common.collect_paths(root, filter={extensions})` to recursively gather file paths

**Date Context**: Use `common.find_date_context(path)` to extract date structure from paths

**Async Encoding**: Use `asyncio.run()` to execute batch encoding operations with configurable thread count

**Interactive Mode**: Most functions support `--interactive` flag for confirmation prompts
