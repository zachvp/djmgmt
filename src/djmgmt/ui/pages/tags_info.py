import streamlit as st
import os
import logging

from djmgmt import tags_info
from djmgmt import common
from djmgmt.ui.utils import utils
from djmgmt.ui.utils import config

# Constants
MODULE = 'tags_info'
FUNCTIONS = [
    tags_info.Namespace.FUNCTION_LOG_DUPLICATES,
    tags_info.Namespace.FUNCTION_COMPARE
]

# Helpers
def get_function_description(function_name: str) -> str:
    '''Return description based on selected function.'''
    if function_name == tags_info.Namespace.FUNCTION_LOG_DUPLICATES:
        return f"{tags_info.log_duplicates.__doc__}"
    elif function_name == tags_info.Namespace.FUNCTION_COMPARE:
        return f"{tags_info.compare_tags.__doc__}"
    else:
        return 'Description missing'

# Initialization
log_path = utils.create_file_path(MODULE)
common.configure_log(level=logging.DEBUG, path=str(log_path))

# Module overview
st.header(f"{MODULE} module")
with st.expander("Overview", expanded=False):
    st.write(tags_info.__doc__)

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
default_library_path = app_config.library_path
if default_library_path is None:
    default_library_path = os.path.expanduser('~/Music/DJ')

input_path = st.text_input('Input Path', value=default_library_path)
assert input_path is not None, "Unable to load input path"

# Optional arguments
comparison = None
if function == tags_info.Namespace.FUNCTION_COMPARE:
    comparison = st.text_input('Comparison Path')

st.write('---')

# Handle Run
if st.button('Run'):
    if function == tags_info.Namespace.FUNCTION_LOG_DUPLICATES:
        duplicates = tags_info.log_duplicates(input_path)
        
        app_config.library_path = input_path
        config.save(app_config)
        
        st.write("### Results:")
        st.dataframe(sorted(duplicates))
    elif function == tags_info.Namespace.FUNCTION_COMPARE and comparison:
        results = tags_info.compare_tags(input_path, comparison)
        st.write(f"Found {len(results)} changes")
        st.dataframe(results,
                     hide_index=True,
                     column_config={
                         '0' : 'Input Path',
                         '1' : 'Comparison Path'
                     })
