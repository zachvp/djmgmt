import streamlit as st

from djmgmt import tags_info
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder

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

# Page initialization
page = PageBuilder(module_name=MODULE, module_ref=tags_info)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, get_function_description)

# Function arguments
page.render_arguments_header()

# Required
app_config = AppConfig.load()
default_library_path = app_config.library_path or ''

input_path = st.text_input('Input Path', value=default_library_path)
assert input_path is not None, "Unable to load input path"

# Optional arguments
comparison = None
if function == tags_info.Namespace.FUNCTION_COMPARE:
    comparison = st.text_input('Comparison Path', value=app_config.client_mirror_path)

st.write('---')

# Handle Run
if st.button('Run'):
    if function == tags_info.Namespace.FUNCTION_LOG_DUPLICATES:
        duplicates = tags_info.log_duplicates(input_path)
        
        app_config.library_path = input_path
        AppConfig.save(app_config)
        
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
