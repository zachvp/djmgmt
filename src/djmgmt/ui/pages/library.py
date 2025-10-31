import streamlit as st
import logging

from djmgmt import library, constants
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper
from djmgmt.ui.components.recent_file_input import RecentFileInput

# Constants
MODULE = 'library'
FUNCTIONS = [
    library.Namespace.FUNCTION_RECORD_DYNAMIC
]

# Function mapping
function_mapper = FunctionMapper(module=library)
function_mapper.add_all({
    library.Namespace.FUNCTION_RECORD_DYNAMIC : library.record_dynamic_tracks
})

# Page initialization
page = PageBuilder(module_name=MODULE, module_ref=library)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, function_mapper.get_description)

# Function arguments
page.render_arguments_header()

# Load the app config
app_config = AppConfig.load()

# Render collection path input with auto-loading and backup finder
collection_path = RecentFileInput.render(
    label='Collection Path',
    widget_key='widget_key_collection_path',
    default_value=app_config.collection_path,
    finder_directory=app_config.collection_directory,
    finder_function=library.find_collection_backup,
    button_label='Find Latest Collection Backup'
)

# Render optional arguments
output_path = None
if function in { library.Namespace.FUNCTION_RECORD_DYNAMIC }:
    output_path = st.text_input('Output Path', value=constants.COLLECTION_PATH_DYNAMIC)

# Render separator between Arguments and Run sections
page.render_section_separator()

# Handle Run button
run_clicked = page.render_run_button()
if run_clicked:
    if function == library.Namespace.FUNCTION_RECORD_DYNAMIC:
        if not output_path:
            st.error("Output path is required for this function")
        else:
            try:
                # Load input collection to get stats
                input_collection = library.load_collection(collection_path)
                played_tracks = library.get_played_tracks(input_collection)
                unplayed_tracks = library.get_unplayed_tracks(input_collection)

                # Run the function
                library.record_dynamic_tracks(collection_path, output_path)

                # Display results
                page.render_results_header()
                st.write(f"- Played tracks: {len(played_tracks)}")
                st.write(f"- Unplayed tracks: {len(unplayed_tracks)}")
                st.success(f"Successfully recorded dynamic tracks to `{output_path}`")
                
                # Update config to store the most recent collection path
                app_config.collection_path = collection_path
                AppConfig.save(app_config)
            except Exception as e:
                st.error(f"Error recording dynamic tracks:\n{e}")
                logging.error(f"Error in FUNCTION_RECORD_DYNAMIC: {e}", exc_info=True)
