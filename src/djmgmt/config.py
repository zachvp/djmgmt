'''
Runtime configuration loaded from environment variables with production defaults.

Import this module instead of constants.py for any configurable value.
For E2E testing, set environment variables before running tests:

    export RSYNC_HOST=localhost
    export NAVIDROME_HOST=localhost
    export NAVIDROME_PASSWORD=test_password
    export DJMGMT_STATE_DIR=/tmp/djmgmt_test/state
    export DJMGMT_LOG_DIR=/tmp/djmgmt_test/logs
'''

import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(os.getenv('DJMGMT_PROJECT_ROOT', str(Path(__file__).parent.parent.parent)))
STATE_DIR    = Path(os.getenv('DJMGMT_STATE_DIR', str(PROJECT_ROOT / 'state')))
LOG_DIR      = Path(os.getenv('DJMGMT_LOG_DIR', str(PROJECT_ROOT / 'logs')))

# Server: rsync
RSYNC_HOST   = os.getenv('RSYNC_HOST', 'corevega.local')
RSYNC_PORT   = os.getenv('RSYNC_PORT', '12000')
RSYNC_USER   = os.getenv('RSYNC_USER', 'zachvp')
RSYNC_MODULE = os.getenv('RSYNC_MODULE', 'navidrome')
RSYNC_URL    = f"rsync://{RSYNC_USER}@{RSYNC_HOST}:{RSYNC_PORT}"

# Server: Navidrome
NAVIDROME_HOST      = os.getenv('NAVIDROME_HOST', 'corevega.local')
NAVIDROME_PORT      = os.getenv('NAVIDROME_PORT', '4533')
NAVIDROME_USERNAME  = os.getenv('NAVIDROME_USERNAME', 'api_client')
NAVIDROME_PASSWORD  = os.getenv('NAVIDROME_PASSWORD')  # fallback to keyring if None
NAVIDROME_CLIENT_ID = os.getenv('NAVIDROME_CLIENT_ID', 'corevega_client')

# Rekordbox
REKORDBOX_ROOT = os.getenv('REKORDBOX_ROOT', 'file://localhost')

# State file paths
COLLECTION_PATH_TEMPLATE  = str(STATE_DIR / 'collection-template.xml')
COLLECTION_PATH_PROCESSED = str(STATE_DIR / 'output' / 'processed-collection.xml')
COLLECTION_PATH_DYNAMIC   = str(STATE_DIR / 'output' / 'dynamic-collection.xml')
COLLECTION_PATH_MERGED    = str(STATE_DIR / 'output' / 'merged-collection.xml')
MISSING_ART_PATH          = str(STATE_DIR / 'output' / 'missing-art.txt')
PLAYLIST_OUTPUT_PATH      = str(STATE_DIR / 'output' / 'playlists')
SYNC_STATE_PATH           = str(STATE_DIR / 'sync_state.txt')
