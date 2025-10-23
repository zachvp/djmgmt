import streamlit as st
import logging

from djmgmt import library, common, constants
from djmgmt.ui.utils import utils, config

# Constants
MODULE = 'library'
FUNCTIONS = [
    library.Namespace.FUNCTION_RECORD_DYNAMIC
]

# Helpers
def get_function_description(function_name: str) -> str:
    '''Return description based on selected function.'''
    if function_name == library.Namespace.FUNCTION_RECORD_DYNAMIC:
        return f"{library.record_dynamic_tracks.__doc__}"
    else:
        return 'Description missing'

# Initialization
log_path = utils.create_file_path(MODULE)
common.configure_log(level=logging.DEBUG, path=str(log_path))

# Module Overiew
st.header(f"{MODULE} module")
with st.expander("Overview", expanded=False):
    st.write(library.__doc__)

# Functions
st.write('#### Function')
function = st.selectbox('Functions', FUNCTIONS, label_visibility='collapsed')
with st.expander("Description", expanded=False):
    st.write(get_function_description(function))
st.write('---')

# Function arguments
st.write('##### Arguments')

# Required
app_config = config.load()

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

st.write('---')

# Handle Run
if st.button('Run'):
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
                config.save(app_config)

                # Show stats
                st.write("### Results:")
                st.write(f"- Played tracks: {len(played_tracks)}")
                st.write(f"- Unplayed tracks: {len(unplayed_tracks)}")
                
                # Display success
                st.success(f"Successfully recorded dynamic tracks to `{output_path}`")
            except Exception as e:
                st.error(f"Error recording dynamic tracks: {e}")
                logging.error(f"Error in FUNCTION_RECORD_DYNAMIC: {e}", exc_info=True)
