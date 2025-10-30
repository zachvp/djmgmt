'''Base utilities for building Streamlit pages with common patterns.'''

import streamlit as st
import logging
from streamlit.delta_generator import DeltaGenerator
from typing import Callable, Optional
from types import ModuleType

from djmgmt import common
from djmgmt.ui.utils import utils


class PageBuilder:
    '''Builder pattern for creating Streamlit pages with standardized structure.

    Handles common patterns across pages:
    - Logging initialization
    - Module header and overview display
    - Function selection UI
    - Standard section separators

    Example:
        page = PageBuilder(module_name='library', module_ref=library)
        page.initialize_logging()
        page.render_header_and_overview()
        function = page.render_function_selector(FUNCTIONS, get_function_description)
    '''

    def __init__(self, module_name: str, module_ref: ModuleType):
        '''Initialize the page builder.

        Args:
            module_name: Name of the module (e.g., 'library', 'tags_info')
            module_ref: Reference to the module object for accessing __doc__
        '''
        self.module_name = module_name
        self.module_ref = module_ref

    def initialize_logging(self, level: int = logging.DEBUG) -> None:
        '''Configure logging for the page.

        Args:
            level: Logging level (default: logging.DEBUG)
        '''
        log_path = utils.create_file_path(self.module_name)
        common.configure_log(level=level, path=str(log_path))

    def render_header_and_overview(self, expanded: bool = False) -> None:
        '''Render the module header and overview expander.

        Args:
            expanded: Whether the overview expander should be initially expanded
        '''
        st.header(f"{self.module_name} module")
        with st.expander('Overview', expanded=expanded):
            st.write(self.module_ref.__doc__)

    @staticmethod
    def render_function_selector(
        functions: list[str],
        get_description_fn: Callable[[str], str]
    ) -> str:
        '''Render function selection UI with description expander.

        Args:
            functions: List of function names to display in selectbox
            get_description_fn: Function that takes a function name and returns its description

        Returns:
            Selected function name
        '''
        st.write('#### Function')
        function = st.selectbox('Functions', functions, label_visibility='collapsed')
        assert function is not None, 'Function selection returned None'

        with st.expander('Description', expanded=False):
            st.write(get_description_fn(function))

        PageBuilder.render_section_separator()
        return function

    @staticmethod
    def render_section_separator() -> None:
        '''Render a horizontal separator line.'''
        st.write('---')

    @staticmethod
    def render_arguments_header() -> None:
        '''Render the standard 'Arguments' section header.'''
        st.write('##### Arguments')
    
    @staticmethod
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

    @staticmethod
    def render_checkbox_input(label: str, default_value: bool = True) -> bool:
        '''Renders a checkbox input with a default value.

        Args:
            label: The label to display for the checkbox
            default_value: The default checked state

        Returns:
            The checkbox state
        '''
        return st.checkbox(label, value=default_value)

    @staticmethod
    def render_run_button() -> bool:
        '''Render the standard 'Run' button prominently centered.'''
        center = PageBuilder.create_center_context()
        with center:
            return st.button('Run', width='stretch')

    @staticmethod
    def render_results_header() -> None:
        '''Render the standard 'Results' section header.'''
        st.write('### Results')


    @staticmethod
    def create_center_context() -> DeltaGenerator:
        _, center, _ = st.columns([1, 1, 1])
        return center