import streamlit as st

from djmgmt import tags_info
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper

# Constants
MODULE = 'tags_info'
FUNCTIONS = [
    tags_info.Namespace.FUNCTION_LOG_DUPLICATES,
    tags_info.Namespace.FUNCTION_COMPARE
]

# Function mapping
function_mapper = FunctionMapper(module=tags_info)
function_mapper.add_all({
    tags_info.Namespace.FUNCTION_LOG_DUPLICATES : tags_info.log_duplicates,
    tags_info.Namespace.FUNCTION_COMPARE        : tags_info.compare_tags
})

# Page initialization
page = PageBuilder(module_name=MODULE, module_ref=tags_info)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, function_mapper.get_description)

# Function arguments
page.render_arguments_header()

# Render required arguments
app_config = AppConfig.load()
input_path = page.render_path_input('Input Path', app_config.library_path, 'Unable to load input path')

# Render optional arguments
comparison = None
if function == tags_info.Namespace.FUNCTION_COMPARE:
    comparison = st.text_input('Comparison Path', value=app_config.client_mirror_path)

# Separator between Arguments and Run sections
page.render_section_separator()
    
# Handle Run button
run_clicked = page.render_run_button()
if run_clicked:
    if function == tags_info.Namespace.FUNCTION_LOG_DUPLICATES:
        # Run the function
        duplicates = tags_info.log_duplicates(input_path)
        
        # Render results
        page.render_results_header()
        st.dataframe(sorted(duplicates),
                        width='stretch',
                        column_config={
                            'value' : 'Duplicate Track Paths'
                        })
        
        # Update config to store the most recent working library path
        app_config.library_path = input_path
        AppConfig.save(app_config)
    elif function == tags_info.Namespace.FUNCTION_COMPARE and comparison:
        # Run the function
        results = tags_info.compare_tags(input_path, comparison)
        
        # Render results
        page.render_results_header()
        st.write(f"Found {len(results)} changes")
        st.dataframe(results,
                    hide_index=True,
                    column_config={
                        '0' : 'Input Path',
                        '1' : 'Comparison Path'
                    })
