import streamlit as st
import logging

from djmgmt import music
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper

# Constants
MODULE = 'music'
FUNCTIONS = [
    music.Namespace.FUNCTION_PROCESS,
    music.Namespace.FUNCTION_UPDATE_LIBRARY
]

# Function mapping
function_mapper = FunctionMapper(module=music)
function_mapper.add_all({
    music.Namespace.FUNCTION_PROCESS        : music.process,
    music.Namespace.FUNCTION_UPDATE_LIBRARY : music.update_library
})

# Page initialization
page = PageBuilder(module_name=MODULE, module_ref=music)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, function_mapper.get_description)

# Function arguments
page.render_arguments_header()

# TODO: Add argument inputs based on selected function

page.render_section_separator()

# Handle Run button
run_clicked = page.render_run_button()
if run_clicked:
    st.info('Function execution not yet implemented')
