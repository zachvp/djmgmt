"""Utilities for executing djmgmt module functions."""
import subprocess
import sys
from typing import Any


def run_module_function(module: str, function: str, **kwargs: Any) -> tuple[int, str, str]:
    """
    Execute a djmgmt module function as a subprocess.

    Args:
        module: Module name (e.g., 'tags_info', 'library')
        function: Function name within module
        **kwargs: Function arguments

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    # Build command: python -m djmgmt.{module} {function} --arg1 val1 --arg2 val2
    cmd = [sys.executable, "-m", f"djmgmt.{module}", function]

    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=subprocess.PIPE
    )

    return result.returncode, result.stdout, result.stderr
