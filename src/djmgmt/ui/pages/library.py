import streamlit as st
import logging

from djmgmt import library, common, constants
from djmgmt.ui.utils import utils, config

# Constants
MODULE = 'library'
FUNCTIONS = [
    library.Namespace.FUNCTION_DATE_PATHS,
    library.Namespace.FUNCTION_IDENTIFIERS,
    library.Namespace.FUNCTION_FILENAMES,
    library.Namespace.FUNCTION_RECORD_DYNAMIC
]

# Helpers
def get_function_description(function_name: str) -> str:
    '''Return description based on selected function.'''
    if function_name == library.Namespace.FUNCTION_DATE_PATHS:
        return f"{library.generate_date_paths.__doc__}"
    elif function_name == library.Namespace.FUNCTION_IDENTIFIERS:
        return f"{library.collect_identifiers.__doc__}"
    elif function_name == library.Namespace.FUNCTION_FILENAMES:
        return f"{library.collect_filenames.__doc__}"
    elif function_name == library.Namespace.FUNCTION_RECORD_DYNAMIC:
        return f"{library.record_dynamic_tracks.__doc__}"
    else:
        return 'Description missing'

# Initialization
log_path = utils.create_log_path(MODULE)
common.configure_log(level=logging.DEBUG, path=str(log_path))

# Module Overiew
st.header(f"{MODULE}")
with st.expander("Overview", expanded=False):
    st.write(library.__doc__)

# Functions
function = st.selectbox('Function', FUNCTIONS)
st.write(get_function_description(function))
st.write('---')

# Required arguments
app_config = config.load()

# Initialize session state for collection path if not present
if 'xml_collection_path' not in st.session_state:
    default_collection_path = app_config.collection_path
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
if function in {library.Namespace.FUNCTION_IDENTIFIERS,
                library.Namespace.FUNCTION_FILENAMES,
                library.Namespace.FUNCTION_RECORD_DYNAMIC}:
    output_path = st.text_input('Output Path', value=constants.DYNAMIC_COLLECTION_PATH)
