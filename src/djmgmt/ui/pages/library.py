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
if 'xml_collection_path' not in st.session_state:
    default_collection_path = app_config.collection_path
    
    # Set the default collection path to the designated file in the collection directory
    if default_collection_path is None:
        default_collection_path = ''
        if app_config.collection_directory:
            default_collection_path = library.find_collection_backup(app_config.collection_directory)
            
    st.session_state.xml_collection_path = default_collection_path

xml_collection_path = st.text_input('XML Collection Path', value=st.session_state.xml_collection_path)
assert xml_collection_path is not None, "Unable to load XML collection path"

# Button to find latest collection backup
# TODO: fix bug: if user clears text_input via UI, then presses the button, the value of `xml_collection_path` = '', even though `st.session_state.xml_collection_path` is the correct path
if st.button('Find Latest Collection Backup'):
    if app_config.collection_directory:
        latest_collection = library.find_collection_backup(app_config.collection_directory)
        if latest_collection:
            st.session_state.xml_collection_path = latest_collection
            st.rerun()
        else:
            st.warning(f"No collection backups found in {app_config.collection_directory}")
    else:
        st.warning("Collection directory not configured in app settings")

# Optional arguments
output_path = None
if function in { library.Namespace.FUNCTION_RECORD_DYNAMIC }:
    output_path = st.text_input('Output Path', value=constants.DYNAMIC_COLLECTION_PATH)

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
                input_collection = library.load_collection(xml_collection_path)
                played_tracks = library.get_played_tracks(input_collection)
                unplayed_tracks = library.get_unplayed_tracks(input_collection)

                # Record dynamic tracks
                library.record_dynamic_tracks(xml_collection_path, output_path)

                # Save the collection path to config
                app_config.collection_path = xml_collection_path
                AppConfig.save(app_config)

                # Show stats
                st.write("### Results:")
                st.write(f"- Played tracks: {len(played_tracks)}")
                st.write(f"- Unplayed tracks: {len(unplayed_tracks)}")
                
                # Display success
                st.success(f"Successfully recorded dynamic tracks to `{output_path}`")
            except Exception as e:
                st.error(f"Error recording dynamic tracks: {e}")
                logging.error(f"Error in FUNCTION_RECORD_DYNAMIC: {e}", exc_info=True)
