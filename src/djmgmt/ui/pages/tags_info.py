import streamlit as st
import os
import logging

from djmgmt import tags_info
from djmgmt import common
from djmgmt.ui.utils import utils

# Constants
MODULE = 'tags_info'

function = st.selectbox('Function', [
        tags_info.Namespace.FUNCTION_LOG_DUPLICATES,
        tags_info.Namespace.FUNCTION_WRITE_PATHS,
        tags_info.Namespace.FUNCTION_COMPARE
    ])

input_path = st.text_input('Input Path', value=os.path.expanduser('~/Music/DJ'))

comparison = None
if function == tags_info.Namespace.FUNCTION_COMPARE:
    comparison = st.text_input('Comparison Path')

if st.button('Run'):
    if function == tags_info.Namespace.FUNCTION_LOG_DUPLICATES:
        # Configure logging before running function
        log_path = utils.create_log_path(MODULE)
        common.configure_log(level=logging.DEBUG, path=str(log_path))
        duplicates = tags_info.log_duplicates(input_path)
        st.write("### Results:")
        st.dataframe(sorted(duplicates))
    elif function == tags_info.Namespace.FUNCTION_COMPARE and comparison:
        results = tags_info.compare_tags(input_path, comparison)
        st.write(f"Found {len(results)} changes")
        st.dataframe(results)