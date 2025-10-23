import streamlit as st
from typing import Optional
from djmgmt import constants
from .config import AppConfig

def create_file_path(module_name: str) -> str:
    relative_path = f"src/djmgmt/{module_name}.py"
    return str(constants.PROJECT_ROOT / relative_path)

def render_path_input(label: str, config_value: Optional[str], error_msg: str) -> str:
    '''Renders a text input for a path with a default value from config.

    Args:
        label: The label to display for the input field
        config_value: The value from app config (or None)
        error_msg: The error message to use in assertion

    Returns:
        The path value entered by the user
    '''
    default_value = config_value or ''
    value = st.text_input(label, value=default_value)
    assert value is not None, error_msg
    return value

def render_checkbox_input(label: str, default_value: bool = True) -> bool:
    '''Renders a checkbox input with a default value.

    Args:
        label: The label to display for the checkbox
        default_value: The default checked state

    Returns:
        The checkbox state
    '''
    return st.checkbox(label, value=default_value)