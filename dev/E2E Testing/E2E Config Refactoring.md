Refactoring Required for E2E Testing

1. Server Connection Configuration (constants.py:28-35 and subsonic_client.py:65)

Hardcoded values:
- COREVEGA_HOST = 'corevega.local'
- COREVEGA_USER = 'zachvp'
- RSYNC_PORT = '12000'
- RSYNC_MODULE_NAVIDROME = 'navidrome'
- base_url = f"http://corevega.local:4533/rest" in subsonic_client.py

Needed:
- Environment variables: NAVIDROME_HOST, NAVIDROME_PORT, RSYNC_HOST, RSYNC_PORT, RSYNC_USER, RSYNC_MODULE
- Default to current values for backward compatibility

2. Rekordbox Root Path (constants.py:51)

Hardcoded value:
- REKORDBOX_ROOT = 'file://localhost'

Needed:
- Environment variable: REKORDBOX_ROOT_URL
- For Docker testing, this might need to be configurable to match container filesystem structure

3. State File Paths (constants.py:74-81)

Hardcoded values:
- STATE_PATH_BASE = PROJECT_ROOT / 'state'
- COLLECTION_PATH_TEMPLATE  = STATE_PATH_BASE / 'collection-template.xml'
- COLLECTION_PATH_PROCESSED = STATE_PATH_BASE / 'output' / 'processed-collection.xml'
- COLLECTION_PATH_DYNAMIC   = STATE_PATH_BASE / 'output' / 'dynamic-collection.xml'
- COLLECTION_PATH_MERGED    = STATE_PATH_BASE / 'output' / 'merged-collection.xml'
- MISSING_ART_PATH          = STATE_PATH_BASE / 'output' / 'missing-art.txt'
- PLAYLIST_OUTPUT_PATH      = STATE_PATH_BASE / 'output' / 'playlists'

Needed:
- Environment variable: DJMGMT_STATE_DIR
- Allow tests to specify temporary state directory

4. Keyring/Credentials Management (subsonic_client.py:47)

Hardcoded:
- keyring.get_password('navidrome_client', 'api_client')

Needed:
- Environment variables: NAVIDROME_USERNAME, NAVIDROME_PASSWORD
- Fallback to keyring for non-test scenarios

5. UI Configuration Path (ui/config.json)

Hardcoded user-specific paths:
- collection_directory: /Users/zachvp/Library/CloudStorage/...
- collection_path: /Users/zachvp/Library/CloudStorage/.../mac-collection-02-19-2026.xml
- download_directory: /Users/zachvp/developer/test-data/...
- library_directory: /Users/zachvp/Music/DJ/_weddings
- client_mirror_directory: /Users/zachvp/Music/corevega/
- playlist_directory: /Users/zachvp/Documents/rekordbox/playlists
- mix_recording_directory: /Users/zachvp/Music/PioneerDJ/Recording/sol_reason/
- pressed_mix_directory: /Users/zachvp/developer/test-data/output

Needed:
- Move to environment variables or make config.json location configurable
- Environment variables: COLLECTION_DIR, COLLECTION_PATH, DOWNLOAD_DIR, LIBRARY_DIR,
  CLIENT_MIRROR_DIR, PLAYLIST_DIR, MIX_RECORDING_DIR, PRESSED_MIX_DIR

6. Logging Paths (common.py - configure_log(), BASE_LOGS_PATH at line 15)

Current behavior:
- BASE_LOGS_PATH = os.path.join(str(constants.PROJECT_ROOT), 'logs')
- Logs to {PROJECT_ROOT}/logs/ directory (project root level, not inside src/)

Needed:
- Environment variable: DJMGMT_LOG_DIR
- Allow tests to redirect logs to temporary directories

7. Sync State Persistence (sync.py:78)

Hardcoded:
- FILE_SYNC = f"{constants.PROJECT_ROOT}{os.sep}state{os.sep}sync_state.txt"

Needed:
- Should use configurable state directory from constants

8. Client ID (subsonic_client.py:55)

Hardcoded:
- 'c': 'corevega_client'

Needed:
- Environment variable: NAVIDROME_CLIENT_ID

Recommended Refactoring Approach

Create a new config.py module that:

1. Loads from environment variables with fallbacks:
import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(os.getenv('DJMGMT_PROJECT_ROOT', Path(__file__).parent.parent.parent))
STATE_DIR = Path(os.getenv('DJMGMT_STATE_DIR', PROJECT_ROOT / 'state'))
LOG_DIR = Path(os.getenv('DJMGMT_LOG_DIR', PROJECT_ROOT / 'logs'))

# Server configuration
RSYNC_HOST = os.getenv('RSYNC_HOST', 'corevega.local')
RSYNC_PORT = os.getenv('RSYNC_PORT', '12000')
RSYNC_USER = os.getenv('RSYNC_USER', 'zachvp')
RSYNC_MODULE = os.getenv('RSYNC_MODULE', 'navidrome')  # maps to RSYNC_MODULE_NAVIDROME in constants.py

NAVIDROME_HOST = os.getenv('NAVIDROME_HOST', 'corevega.local')
NAVIDROME_PORT = os.getenv('NAVIDROME_PORT', '4533')
NAVIDROME_USERNAME = os.getenv('NAVIDROME_USERNAME', 'api_client')
NAVIDROME_PASSWORD = os.getenv('NAVIDROME_PASSWORD')  # fallback to keyring if None
NAVIDROME_CLIENT_ID = os.getenv('NAVIDROME_CLIENT_ID', 'corevega_client')

# Rekordbox
REKORDBOX_ROOT = os.getenv('REKORDBOX_ROOT', 'file://localhost')

2. Update all modules to import from config.py instead of constants.py for configurable values
3. Keep music-specific constants (like EXTENSIONS, MAPPING_MONTH, XML attributes) in constants.py
4. For E2E tests, set environment variables before running tests:
export RSYNC_HOST=localhost
export RSYNC_PORT=12000
export NAVIDROME_HOST=localhost
export NAVIDROME_PORT=4533
export NAVIDROME_PASSWORD=test_password
export DJMGMT_STATE_DIR=/tmp/djmgmt_test/state
export DJMGMT_LOG_DIR=/tmp/djmgmt_test/logs

This approach allows the codebase to work unchanged in production while being fully configurable for Docker-based E2E testing.

9. Unit Test Updates

No fundamental restructuring required. Tests already rely on @patch decorators for isolation; only the patch targets shift from constants.* to config.* for values that migrate.

Affected test files:

- tests/test_sync.py: Update references to constants.RSYNC_URL, constants.RSYNC_MODULE_NAVIDROME,
  constants.PLAYLIST_OUTPUT_PATH → config.RSYNC_URL, config.RSYNC_MODULE, config.PLAYLIST_OUTPUT_PATH

- tests/test_music.py: Update references to constants.MISSING_ART_PATH, constants.RSYNC_URL,
  constants.RSYNC_MODULE_NAVIDROME → config.* equivalents

- tests/test_library.py: Update reference to constants.COLLECTION_PATH_TEMPLATE →
  config.COLLECTION_PATH_TEMPLATE

- tests/test_common.py: configure_log() tests assert log file paths derived from PROJECT_ROOT.
  After refactoring, common.BASE_LOGS_PATH reads from config.LOG_DIR. Patch common.BASE_LOGS_PATH
  directly (same as today) or patch config.LOG_DIR in tests that verify log output paths.

Unaffected test files (use only static constants that stay in constants.py):
- test_encode.py — uses only XPATH_COLLECTION, XPATH_PRUNED
- test_tags_sort.py — uses only MAPPING_MONTH
- test_playlist.py, test_tags.py, test_tags_info.py — no constants import
