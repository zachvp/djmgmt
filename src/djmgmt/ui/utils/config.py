"""Configuration management for UI state and environment."""
import json
from pathlib import Path
from typing import Any

# Store config in project state directory
CONFIG_PATH = Path(__file__).parent.parent.parent.parent.parent / "state" / "ui_config.json"


def load_config() -> dict[str, Any]:
    """Load persistent UI configuration."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "collection_path": "",
        "download_directory": "",
        "library_path": "",
        "recent_commands": []
    }


def save_config(config: dict[str, Any]) -> None:
    """Save UI configuration to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def add_recent_command(module: str, function: str, params: dict[str, Any]) -> None:
    """Add a command to recent history."""
    config = load_config()
    recent = config.get("recent_commands", [])

    # Add to front of list
    recent.insert(0, {
        "module": module,
        "function": function,
        "params": params
    })

    # Keep last 10 commands
    config["recent_commands"] = recent[:10]
    save_config(config)
