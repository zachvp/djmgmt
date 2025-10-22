import streamlit as st
import os
import logging

from djmgmt import library
from djmgmt import common
from djmgmt.ui.utils import utils
from djmgmt.ui.utils import config

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

# Main UI
st.header(f"{MODULE}")
with st.expander("Summary", expanded=True):
    st.write(library.__doc__)

## Functions
function = st.selectbox('Function', FUNCTIONS)
st.write(get_function_description(function))
