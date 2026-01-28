'''Reusable file path input component with auto-loading and finder functionality.'''

import streamlit as st
from typing import Callable, Optional
from dataclasses import dataclass

class RecentFileInput:
    '''Generic file path input with session state management and latest file finder.

    Handles the common pattern of:
    - Initializing session state with a default value from config
    - Optionally finding the most recent file if config value is missing
    - Managing pending path updates for Streamlit reruns
    - Rendering text input with a "Find Latest" button

    Example:
        collection_path = RecentFileInput.render(
            label='Collection Path',
            widget_key='widget_key_collection_path',
            config_value=app_config.collection_path,
            finder_directory=app_config.collection_directory,
            finder_function=library.find_collection_backup,
            button_label='Find Latest Collection Backup'
        )
    '''
    @dataclass(frozen=True)
    class Finder:
        directory: str
        function: Callable[[str, set[str]], str]
        filter: set[str]

    @staticmethod
    def _find_latest_callback(widget_key: str, finder: 'RecentFileInput.Finder') -> None:
        '''Callback executed when Find Latest button is clicked.

        Runs BEFORE widget processing phase, ensuring all widgets commit state first.
        Updates session state with latest file, or sets a warning flag if not found.
        '''
        warning_key = f'warning_{widget_key}'

        # Clear any previous warnings
        if warning_key in st.session_state:
            del st.session_state[warning_key]

        if not finder.directory:
            st.session_state[warning_key] = 'Directory not configured in app settings'
            return

        latest_file = finder.function(finder.directory, finder.filter)
        if latest_file:
            st.session_state[widget_key] = latest_file
        else:
            st.session_state[warning_key] = f'No files found in {finder.directory}'

    @staticmethod
    def render(
        label: str,
        widget_key: str,
        finder: Finder,
        default_value: Optional[str],
        button_label: str = 'Find Latest File'
    ) -> str:
        '''Renders a file path input with auto-loading and finder button.

        Args:
            label: Display label for the text input
            widget_key: Unique session state key for this input widget
            finder: Finder configuration with directory, function, and file filter
            default_value: Default value from app config (or None)
            button_label: Label for the finder button

        Returns:
            The file path from session state
        '''
        # Initialize session state for path if not present
        if widget_key not in st.session_state:
            default_path = default_value
            if default_path is None:
                default_path = ''
                if finder.directory:
                    default_path = finder.function(finder.directory, finder.filter)
            st.session_state[widget_key] = default_path

        # Render the text input bound to session state
        st.text_input(label, key=widget_key)
        path = st.session_state[widget_key]
        assert path is not None, f'Unable to load file path for {label}'

        # Button with callback (no st.rerun() needed)
        button_key = f'button_{widget_key}'
        st.button(
            button_label,
            key=button_key,
            on_click=RecentFileInput._find_latest_callback,
            args=(widget_key, finder)
        )

        # Display any warnings from callback
        warning_key = f'warning_{widget_key}'
        if warning_key in st.session_state:
            st.warning(st.session_state[warning_key])
            del st.session_state[warning_key]

        return path
