'''Configuration management for UI state and environment.'''
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

# Classes
class Key(StrEnum):
    COLLECTION_DIRECTORY = 'collection_directory'
    COLLECTION_PATH      = 'collection_path'
    DOWNLOAD_DIRECTORY   = 'download_directory'
    LIBRARY_PATH         = 'library_path'

class Config:
    # Constants
    PATH = Path(__file__).parent.parent / 'config.json'
    TEMPLATE = {
        Key.COLLECTION_DIRECTORY : None,
        Key.COLLECTION_PATH      : None,
        Key.DOWNLOAD_DIRECTORY   : None,
        Key.LIBRARY_PATH         : None
    }
    
    def __init__(self, data: dict[Key, Any]) -> None:
        self.collection_directory : Optional[str] = data.get(Key.COLLECTION_DIRECTORY)
        self.collection_path      : Optional[str] = data.get(Key.COLLECTION_PATH)
        self.download_directory   : Optional[str] = data.get(Key.DOWNLOAD_DIRECTORY)
        self.library_path         : Optional[str] = data.get(Key.LIBRARY_PATH)

    def to_dict(self) -> dict[str, Any]:
        return {
            Key.COLLECTION_DIRECTORY : self.collection_directory,
            Key.COLLECTION_PATH      : self.collection_path,
            Key.DOWNLOAD_DIRECTORY   : self.download_directory,
            Key.LIBRARY_PATH         : self.library_path
        }

# Primary functions
def load() -> Config:
    '''Load UI configuration from disk.'''
    if not Config.PATH.exists():
        save(Config(Config.TEMPLATE))

    with open(Config.PATH) as f:
        return Config(json.load(f))

def save(config: Config) -> None:
    '''Save UI configuration to disk.'''
    Config.PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(Config.PATH, 'w') as file:
        json.dump(config, file, indent=2, default=lambda obj: obj.to_dict())