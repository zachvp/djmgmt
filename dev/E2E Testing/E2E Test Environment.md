# E2E Test Environment Configuration

## Overview

This document describes the Docker-based end-to-end testing environment for djmgmt, including programmatic credential configuration for Navidrome integration.

## Key Findings from Navidrome Source Code

### Auto-Admin User Creation Feature

Navidrome includes a development feature specifically designed for automated testing and development environments.

**Source code location:** `server/initial_setup.go:30-66`

```go
func initialSetup(ds model.DataStore) {
    // ...
    if conf.Server.DevAutoCreateAdminPassword != "" {
        if err = createInitialAdminUser(tx, conf.Server.DevAutoCreateAdminPassword); err != nil {
            return err
        }
    }
    // ...
}

func createInitialAdminUser(ds model.DataStore, initialPassword string) error {
    users := ds.User(context.TODO())
    c, err := users.CountAll(model.QueryOptions{Filters: squirrel.Eq{"user_name": consts.DevInitialUserName}})
    if c == 0 {
        newID := id.NewRandom()
        log.Warn("Creating initial admin user. This should only be used for development purposes!!",
            "user", consts.DevInitialUserName, "password", initialPassword, "id", newID)
        initialUser := model.User{
            ID:          newID,
            UserName:    consts.DevInitialUserName,    // "admin"
            Name:        consts.DevInitialName,        // "Dev Admin"
            Email:       "",
            NewPassword: initialPassword,
            IsAdmin:     true,
        }
        err := users.Put(&initialUser)
        // ...
    }
    return err
}
```

**Key constants** (`consts/consts.go:36-37`):
```go
DevInitialUserName = "admin"
DevInitialName     = "Dev Admin"
```

### Environment Variable Configuration

**Configuration binding** (`conf/configuration.go:630-633`):
```go
viper.SetEnvPrefix("ND")
replacer := strings.NewReplacer(".", "_")
viper.SetEnvKeyReplacer(replacer)
viper.AutomaticEnv()
```

**Environment variable:** `ND_DEVAUTOCREATEADMINPASSWORD`

When set, Navidrome will:
1. Check on startup if a user named "admin" exists
2. If not, create an admin user with the specified password
3. Use hardcoded username: `admin`
4. Grant full admin privileges

**Security Warning:** This feature logs a warning stating it should only be used for development purposes. Perfect for E2E testing, but **never use in production**.

## Docker Compose Test Configuration

### docker-compose.test.yml

```yaml
version: '3.8'

services:
  # Navidrome media server for testing
  navidrome:
    image: deluan/navidrome:latest
    container_name: navidrome-e2e-test
    ports:
      - "4533:4533"
    environment:
      # Auto-create admin user for testing (username: admin)
      - ND_DEVAUTOCREATEADMINPASSWORD=test_password_123

      # Core configuration
      - ND_MUSICFOLDER=/music
      - ND_DATAFOLDER=/data
      - ND_LOGLEVEL=debug

      # Behavior settings
      - ND_SCANONSTARTUP=true
      - ND_SESSIONTIMEOUT=24h

      # Disable external services for isolated testing
      - ND_ENABLEEXTERNALSERVICES=false
    volumes:
      - ./test/fixtures/music:/music
      - navidrome-data:/data
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:4533/ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks:
      - e2e-test-network

  # Rsync daemon for file transfer testing
  rsync-daemon:
    image: axiom/rsync-server
    container_name: rsync-e2e-test
    ports:
      - "12000:873"
    environment:
      - USERNAME=testuser
      - PASSWORD=testpass
      - ALLOW=0.0.0.0/0
    volumes:
      - rsync-music:/data
    networks:
      - e2e-test-network

  # djmgmt test runner (optional - can also run from host)
  djmgmt-test:
    build:
      context: .
      dockerfile: Dockerfile.test
    container_name: djmgmt-e2e-test
    depends_on:
      navidrome:
        condition: service_healthy
      rsync-daemon:
        condition: service_started
    environment:
      # Navidrome connection
      - NAVIDROME_HOST=navidrome
      - NAVIDROME_PORT=4533
      - NAVIDROME_USERNAME=admin
      - NAVIDROME_PASSWORD=test_password_123
      - NAVIDROME_CLIENT_ID=e2e_test_client

      # Rsync connection
      - RSYNC_HOST=rsync-daemon
      - RSYNC_PORT=873
      - RSYNC_USER=testuser
      - RSYNC_MODULE=data

      # djmgmt configuration
      - DJMGMT_STATE_DIR=/tmp/djmgmt/state
      - DJMGMT_LOG_DIR=/tmp/djmgmt/logs
      - REKORDBOX_ROOT=file://localhost

      # Test-specific paths
      - COLLECTION_DIR=/test/collections
      - DOWNLOAD_DIR=/test/downloads
      - LIBRARY_DIR=/test/library
      - CLIENT_MIRROR_DIR=/test/mirror
    volumes:
      - ./test:/test
      - djmgmt-state:/tmp/djmgmt
    networks:
      - e2e-test-network

volumes:
  navidrome-data:
  rsync-music:
  djmgmt-state:

networks:
  e2e-test-network:
    driver: bridge
```

## Required Source Code Changes

### 1. Create `src/djmgmt/config.py`

New configuration module to support environment-based configuration:

```python
'''
Configuration module for djmgmt

Loads configuration from environment variables with fallbacks to default values.
This allows the codebase to work unchanged in production while being fully
configurable for Docker-based E2E testing.
'''

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

# Construct rsync URL
RSYNC_PROTOCOL = 'rsync://'
RSYNC_URL = f"{RSYNC_PROTOCOL}{RSYNC_USER}@{RSYNC_HOST}:{RSYNC_PORT}"

# Navidrome/Subsonic configuration
NAVIDROME_HOST = os.getenv('NAVIDROME_HOST', 'corevega.local')
NAVIDROME_PORT = os.getenv('NAVIDROME_PORT', '4533')
NAVIDROME_USERNAME = os.getenv('NAVIDROME_USERNAME', 'api_client')
NAVIDROME_PASSWORD = os.getenv('NAVIDROME_PASSWORD')  # None if not set, will fall back to keyring
NAVIDROME_CLIENT_ID = os.getenv('NAVIDROME_CLIENT_ID', 'corevega_client')
NAVIDROME_BASE_URL = f"http://{NAVIDROME_HOST}:{NAVIDROME_PORT}/rest"

# Rekordbox
REKORDBOX_ROOT = os.getenv('REKORDBOX_ROOT', 'file://localhost')

# UI Configuration paths (optional, can be overridden)
COLLECTION_DIR = os.getenv('COLLECTION_DIR')
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR')
LIBRARY_DIR = os.getenv('LIBRARY_DIR')
CLIENT_MIRROR_DIR = os.getenv('CLIENT_MIRROR_DIR')
PLAYLIST_DIR = os.getenv('PLAYLIST_DIR')

# State file paths
COLLECTION_PATH_TEMPLATE = str(STATE_DIR / 'collection-template.xml')
COLLECTION_PATH_PROCESSED = str(STATE_DIR / 'output' / 'processed-collection.xml')
COLLECTION_PATH_DYNAMIC = str(STATE_DIR / 'output' / 'dynamic-collection.xml')
MISSING_ART_PATH = str(STATE_DIR / 'output' / 'missing-art.txt')
SYNC_STATE_FILE = str(STATE_DIR / 'sync_state.txt')
```

### 2. Update `src/djmgmt/subsonic_client.py`

Modify credential handling to support both keyring (production) and environment variables (testing):

```python
import os
import keyring
# ... other imports

def create_query(params: dict[str, str] = {}) -> str:
    from . import config

    # Try environment variable first (for testing), fall back to keyring
    password = config.NAVIDROME_PASSWORD
    if password is None:
        password = keyring.get_password('navidrome_client', 'api_client')
    assert password is not None, 'unable to fetch password (check NAVIDROME_PASSWORD env var or keyring)'

    username = config.NAVIDROME_USERNAME
    client_id = config.NAVIDROME_CLIENT_ID

    salt = create_salt(12)
    base_params = {
        'u': username,
        't': f'{create_token(password, salt)}',
        's': f'{salt}',
        'v': '1.16.1',
        'c': client_id
    }
    # add any params
    for key, value in params.items():
        base_params[key] = value
    return urlencode(base_params)

def call_endpoint(endpoint: str, params: dict[str, str] = {}) -> Response:
    from . import config

    # call the endpoint
    query_string = create_query(params)
    base_url = config.NAVIDROME_BASE_URL
    url = f"{base_url}/{endpoint}.view?{query_string}"
    logging.debug(f'send request: {url}')
    return requests.get(url)
```

### 3. Update `src/djmgmt/constants.py`

Replace hardcoded values with imports from config module:

```python
# Import configurable values from config module
from . import config

# Project root (now configurable)
PROJECT_ROOT = config.PROJECT_ROOT

# Server configuration (now configurable)
COREVEGA_HOST = config.RSYNC_HOST  # Keep old name for backward compatibility
COREVEGA_USER = config.RSYNC_USER
RSYNC_PORT = config.RSYNC_PORT
RSYNC_PROTOCOL = config.RSYNC_PROTOCOL
RSYNC_MODULE_NAVIDROME = config.RSYNC_MODULE
RSYNC_URL = config.RSYNC_URL

# Rekordbox (now configurable)
REKORDBOX_ROOT = config.REKORDBOX_ROOT

# State paths (now configurable)
COLLECTION_PATH_TEMPLATE = config.COLLECTION_PATH_TEMPLATE
COLLECTION_PATH_PROCESSED = config.COLLECTION_PATH_PROCESSED
COLLECTION_PATH_DYNAMIC = config.COLLECTION_PATH_DYNAMIC
MISSING_ART_PATH = config.MISSING_ART_PATH

# ... rest of constants (MAPPING_MONTH, ATTR_*, XPATH_*, EXTENSIONS, etc.)
# These remain unchanged as they are music-specific constants
```

### 4. Update `src/djmgmt/sync.py`

Update sync state file path:

```python
from . import config

class SavedDateContext:
    FILE_SYNC = config.SYNC_STATE_FILE
    FILE_SYNC_KEY = 'sync_date'

    # ... rest of class remains unchanged
```

### 5. Update `src/djmgmt/common.py`

Update logging configuration to use configurable log directory:

```python
from . import config

def configure_log(level: int = logging.INFO, path: str | None = None) -> None:
    '''Standard log configuration.'''
    if path:
        filename = os.path.basename(path)
    else:
        filename = 'djmgmt'

    log_path = config.LOG_DIR / f"{filename}.log"
    os.makedirs(config.LOG_DIR, exist_ok=True)

    logging.basicConfig(
        filename=str(log_path),
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
```

## E2E Test Execution

### Starting the Test Environment

```bash
# Start all services
docker-compose -f docker-compose.test.yml up -d

# Wait for services to be healthy
docker-compose -f docker-compose.test.yml ps

# Check Navidrome logs to verify admin user creation
docker-compose -f docker-compose.test.yml logs navidrome | grep "Creating initial admin user"
```

### Running Tests from Host

```bash
# Set environment variables
export NAVIDROME_HOST=localhost
export NAVIDROME_PORT=4533
export NAVIDROME_USERNAME=admin
export NAVIDROME_PASSWORD=test_password_123
export RSYNC_HOST=localhost
export RSYNC_PORT=12000
export DJMGMT_STATE_DIR=/tmp/djmgmt_test/state
export DJMGMT_LOG_DIR=/tmp/djmgmt_test/logs

# Run tests
python3 -m unittest discover -s test -p "test_integration.py" -v
```

### Running Tests in Container

```bash
# Run tests inside the djmgmt-test container
docker-compose -f docker-compose.test.yml run --rm djmgmt-test \
    python3 -m unittest discover -s test -p "test_integration.py" -v
```

### Cleanup

```bash
# Stop and remove all test containers and volumes
docker-compose -f docker-compose.test.yml down -v
```

## Test Fixtures

### Directory Structure

```
test/
   fixtures/
      music/                    # Dummy music files
         track1.mp3
         track2.aiff
         track3.flac
      collections/              # Test collection XML files
         test-collection.xml
      downloads/                # Files to sweep/process
         new-track.zip
      manifests/                # Test manifests
          dummy-files.json
   test_integration.py           # Integration tests
   test_music.py                 # Music processing tests
```

### Example Test Manifest (test/fixtures/manifests/dummy-files.json)

```json
{
  "files": [
    {
      "path": "track1.mp3",
      "title": "Test Track 1",
      "artist": "Test Artist 1",
      "album": "Test Album",
      "genre": "Electronic",
      "has_cover_art": true
    },
    {
      "path": "track2.aiff",
      "title": "Test Track 2",
      "artist": "Test Artist 2",
      "album": "Test Album",
      "genre": "House",
      "has_cover_art": false
    }
  ]
}
```

## Security Considerations

1. **ND_DEVAUTOCREATEADMINPASSWORD** is a development-only feature
   - Only use in testing/development environments
   - Never enable in production
   - Navidrome logs a warning when this feature is used

2. **Password in Environment Variables**
   - Test credentials are exposed in docker-compose.yml
   - Use secrets management for any production-like environments
   - Rotate test credentials regularly

3. **Network Isolation**
   - E2E test network should be isolated from production networks
   - Use Docker networks to contain test traffic

## Migration Path

To migrate existing djmgmt code:

1. Create `src/djmgmt/config.py` with environment variable loading
2. Update `constants.py` to import from `config.py`
3. Update `subsonic_client.py` for dual credential sources
4. Update `sync.py` for configurable sync state path
5. Update `common.py` for configurable log directory
6. Test in production mode (no env vars) to ensure backward compatibility
7. Test in E2E mode (with env vars) to verify test environment works

## Backward Compatibility

All changes maintain backward compatibility:
- If no environment variables are set, defaults to original hardcoded values
- Existing production deployments continue working without changes
- Keyring-based credential storage still works when `NAVIDROME_PASSWORD` is not set
