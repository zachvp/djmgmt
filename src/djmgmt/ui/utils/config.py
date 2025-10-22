'''Configuration management for UI state and environment.'''
import json
from pathlib import Path
from typing import Any, Optional

# Constants
CONFIG_PATH = Path(__file__).parent.parent / 'config.json'

KEY_COLLECTION_PATH     = 'collection_path'
KEY_DOWNLOAD_DIRECTORY  = 'download_directory'
KEY_LIBRARY_PATH        = 'library_path'
CONFIG_TEMPLATE = {
    KEY_COLLECTION_PATH    : None,
    KEY_DOWNLOAD_DIRECTORY : None,
    KEY_LIBRARY_PATH       : None
}
class Config:
    def __init__(self, data: dict[str, Any]) -> None:
        self.collection_path    : Optional[str] = data['collection_path']
        self.download_directory : Optional[str] = data['download_directory']
        self.library_path       : Optional[str] = data['library_path']
    
    def to_dict(self) -> dict[str, Any]:
        return {
            KEY_COLLECTION_PATH    : self.collection_path,
            KEY_DOWNLOAD_DIRECTORY : self.download_directory,
            KEY_LIBRARY_PATH       : self.library_path
        }

# Primary functions
def load() -> Config:
    '''Load UI configuration from disk.'''
    if not CONFIG_PATH.exists():
        save(Config(CONFIG_TEMPLATE))

    with open(CONFIG_PATH) as f:
        return Config(json.load(f))

def save(config: Config) -> None:
    '''Save UI configuration to disk.'''
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w') as file:
        json.dump(config, file, indent=2, default=lambda obj: obj.to_dict())