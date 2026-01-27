'''Configuration management for UI state and environment.'''
from __future__ import annotations
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Optional, Type, TypeVar

T = TypeVar('T', bound='BaseConfig')

class BaseConfig:
    '''Base configuration class with automatic serialization.'''
    PATH     : ClassVar[Path]
    TEMPLATE : ClassVar[dict[str, Any]]
    Key      : ClassVar[Type[StrEnum]]
    
    def __init__(self, data: dict[str, Any]) -> None:
        for key in self.Key:
            setattr(self, key.value, data.get(key))
    
    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key.value) for key in self.Key}
    
    @classmethod
    def load(cls: Type[T]) -> T:
        '''Load configuration from disk.'''
        if not cls.PATH.exists():
            cls.save(cls(cls.TEMPLATE))

        with open(cls.PATH) as f:
            data = json.load(f)

        # Merge missing keys from TEMPLATE
        needs_update = False
        for key, value in cls.TEMPLATE.items():
            if key not in data:
                data[key] = value
                needs_update = True

        config = cls(data)

        # Save if we added missing keys
        if needs_update:
            cls.save(config)

        return config
    
    @classmethod
    def save(cls, config: BaseConfig) -> None:
        '''Save configuration to disk.'''
        cls.PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(cls.PATH, 'w') as f:
            json.dump(config.to_dict(), f, indent=2)

class AppKey(StrEnum):
    COLLECTION_DIRECTORY     = 'collection_directory'
    COLLECTION_PATH          = 'collection_path'
    DOWNLOAD_DIRECTORY       = 'download_directory'
    LIBRARY_DIRECTORY        = 'library_directory'
    CLIENT_MIRROR_PATH       = 'client_mirror_directory'
    PLAYLIST_DIRECTORY       = 'playlist_directory'
    MIX_RECORDING_DIRECTORY  = 'mix_recording_directory'

class AppConfig(BaseConfig):
    PATH     = Path(__file__).parent.parent / 'config.json'
    Key      = AppKey
    TEMPLATE = {key: None for key in AppKey}
    
    collection_directory      : Optional[str]
    collection_path           : Optional[str]
    download_directory        : Optional[str]
    library_directory         : Optional[str]
    client_mirror_directory   : Optional[str]
    playlist_directory        : Optional[str]
    mix_recording_directory   : Optional[str]
