import streamlit as st
import os
import logging

from djmgmt.tags_info import log_duplicates, compare_tags
from djmgmt import common
from djmgmt.ui.utils import utils

# Constants
MODULE = 'tags_info'

function = st.selectbox('Function', [
        'log_duplicates',
        'write_identifiers',
        'compare'
    ])

input_path = st.text_input('Input Path', value=os.path.expanduser('~/Music/DJ'))

comparison = None
if function == 'compare':
    comparison = st.text_input('Comparison Path')

# TODO: implement
# output = st.text_input('Output File (optional)')

if st.button('Run'):
    if function == 'log_duplicates':
        # Configure logging before running function
        log_path = utils.create_log_path(MODULE)
        common.configure_log(level=logging.DEBUG, path=str(log_path))
        duplicates = log_duplicates(input_path)
        st.write("### Results:")
        st.dataframe(sorted(duplicates))
    elif function == 'compare' and comparison:
        results = compare_tags(input_path, comparison)
        st.write(f"Found {len(results)} changes")
        st.dataframe(results)