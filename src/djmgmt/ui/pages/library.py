import streamlit as st
import logging

from djmgmt import library, constants
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper

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

# Initialize session state for collection path if not present
if 'widget_key_collection_path' not in st.session_state:
    # Set default collection path to app config value
    default_collection_path = app_config.collection_path

    # Override the default collection path to the designated file in the collection directory if it does not exist in the config
    if default_collection_path is None:
        default_collection_path = ''
        if app_config.collection_directory:
            default_collection_path = library.find_collection_backup(app_config.collection_directory)

    st.session_state.widget_key_collection_path = default_collection_path

# Check if we need to update the path from a previous button click
if 'pending_collection_path' in st.session_state:
    st.session_state.widget_key_collection_path = st.session_state.pending_collection_path
    del st.session_state.pending_collection_path

# Render the collection path to be the session state reference
st.text_input('Collection Path', key='widget_key_collection_path')
collection_path = st.session_state.widget_key_collection_path
assert collection_path is not None, "Unable to load XML collection path"

# Button to find latest collection backup
if st.button('Find Latest Collection Backup'):
    if app_config.collection_directory:
        latest_collection = library.find_collection_backup(app_config.collection_directory)
        if latest_collection:
            st.session_state.pending_collection_path = latest_collection
            st.rerun()
        else:
            st.warning(f"No collection backups found in {app_config.collection_directory}")
    else:
        st.warning("Collection directory not configured in app settings")

# Render optional arguments
output_path = None
if function in { library.Namespace.FUNCTION_RECORD_DYNAMIC }:
    output_path = st.text_input('Output Path', value=constants.DYNAMIC_COLLECTION_PATH)

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
