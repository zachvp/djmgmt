  Refactoring Required for E2E Testing

  1. Server Connection Configuration (constants.py:28-35 and subsonic_client.py:65)

  Hardcoded values:
  - COREVEGA_HOST = 'corevega.local'
  - COREVEGA_USER = 'zachvp'
  - RSYNC_PORT = '12000'
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

  3. State File Paths (constants.py:69-74)

  Hardcoded values:
  - PROJECT_ROOT / 'state' / ... paths for:
    - Collection templates
    - Processed collections
    - Sync state
    - Missing art output

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
  - /Users/zachvp/Library/CloudStorage/...
  - /Users/zachvp/developer/test-data/...
  - /Users/zachvp/Music/corevega/

  Needed:
  - Move to environment variables or make config.json location configurable
  - Environment variables: COLLECTION_DIR, DOWNLOAD_DIR, LIBRARY_DIR, CLIENT_MIRROR_DIR, PLAYLIST_DIR

  6. Logging Paths (common.py - configure_log())

  Current behavior:
  - Logs to src/logs/ directory

  Needed:
  - Environment variable: DJMGMT_LOG_DIR
  - Allow tests to redirect logs to temporary directories

  7. Sync State Persistence (sync.py:62-63)

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
  LOG_DIR = Path(os.getenv('DJMGMT_LOG_DIR', PROJECT_ROOT / 'src' / 'logs'))

  # Server configuration
  RSYNC_HOST = os.getenv('RSYNC_HOST', 'corevega.local')
  RSYNC_PORT = os.getenv('RSYNC_PORT', '12000')
  RSYNC_USER = os.getenv('RSYNC_USER', 'zachvp')
  RSYNC_MODULE = os.getenv('RSYNC_MODULE', 'navidrome')

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
  