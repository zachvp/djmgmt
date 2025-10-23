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
            return cls(json.load(f))
    
    @classmethod
    def save(cls, config: BaseConfig) -> None:
        '''Save configuration to disk.'''
        cls.PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(cls.PATH, 'w') as f:
            json.dump(config.to_dict(), f, indent=2)

class AppKey(StrEnum):
    COLLECTION_DIRECTORY = 'collection_directory'
    COLLECTION_PATH      = 'collection_path'
    DOWNLOAD_DIRECTORY   = 'download_directory'
    LIBRARY_PATH         = 'library_path'

class AppConfig(BaseConfig):
    PATH     = Path(__file__).parent.parent / 'config.json'
    Key      = AppKey
    TEMPLATE = {key: None for key in AppKey}
    
    collection_directory : Optional[str]
    collection_path      : Optional[str]
    download_directory   : Optional[str]
    library_path         : Optional[str]