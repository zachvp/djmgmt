'''Reusable file path input component with auto-loading and finder functionality.'''

import streamlit as st
from typing import Callable, Optional


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

    @staticmethod
    def render(
        label: str,
        widget_key: str,
        default_value: Optional[str],
        finder_directory: Optional[str],
        finder_function: Callable[[str], str],
        button_label: str = 'Find Latest File'
    ) -> str:
        '''Renders a file path input with auto-loading and finder button.

        Args:
            label: Display label for the text input
            widget_key: Unique session state key for this input widget
            config_value: Default value from app config (or None)
            finder_directory: Directory to search for files (or None to disable finder)
            finder_function: Function that takes directory and returns latest file path
            button_label: Label for the finder button

        Returns:
            The file path from session state
        '''
        # Initialize session state for path if not present
        if widget_key not in st.session_state:
            # Set default path to config value
            default_path = default_value

            # Override default to latest file if config value is None and finder directory exists
            if default_path is None:
                default_path = ''
                if finder_directory:
                    default_path = finder_function(finder_directory)

            st.session_state[widget_key] = default_path

        # Check if we need to update the path from a previous button click
        pending_key = f"pending_{widget_key}"
        if pending_key in st.session_state:
            st.session_state[widget_key] = st.session_state[pending_key]
            del st.session_state[pending_key]

        # Render the text input bound to session state
        st.text_input(label, key=widget_key)
        path = st.session_state[widget_key]
        assert path is not None, f"Unable to load file path for {label}"

        # Button to find latest file
        if st.button(button_label):
            if finder_directory:
                latest_file = finder_function(finder_directory)
                if latest_file:
                    st.session_state[pending_key] = latest_file
                    st.rerun()
                else:
                    st.warning(f"No files found in {finder_directory}")
            else:
                st.warning('Directory not configured in app settings')

        return path
