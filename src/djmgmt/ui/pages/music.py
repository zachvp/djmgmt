import streamlit as st
import logging

from djmgmt import music, constants
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper

# Constants
MODULE = 'music'
FUNCTIONS = [
    music.Namespace.FUNCTION_PROCESS,
    music.Namespace.FUNCTION_UPDATE_LIBRARY
]

# Function mapping
function_mapper = FunctionMapper(module=music)
function_mapper.add_all({
    music.Namespace.FUNCTION_PROCESS        : music.process,
    music.Namespace.FUNCTION_UPDATE_LIBRARY : music.update_library
})

# Page initialization
page = PageBuilder(module_name=MODULE, module_ref=music)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, function_mapper.get_description)

# Function arguments
page.render_arguments_header()

# Load app config
app_config = AppConfig.load()

# Required arguments
source_path = None
output_path = None
if function == music.Namespace.FUNCTION_PROCESS:
    # Source/input path: load from config.download_directory as default
    default_source_path = app_config.download_directory or ''
    source_path = st.text_input('Source Path', value=default_source_path)
    assert source_path is not None, 'Unable to load source path'

    # Output path
    default_output_path = app_config.library_path or ''
    output_path = st.text_input('Output Path', value=default_output_path)
    assert output_path is not None, 'Unable to load output path'

# Render separator between Arguments and Run sections
page.render_section_separator()

# Handle Run button
run_clicked = page.render_run_button()
if run_clicked:
    if function == music.Namespace.FUNCTION_PROCESS:
        if not source_path or not output_path:
            st.error('Source and output paths are required')
        else:
            try:
                # Run the process function
                st.info(f"Processing files from `{source_path}` to `{output_path}`")
                with st.spinner('...'):
                    music.process(
                        source=source_path,
                        output=output_path,
                        interactive=False,
                        valid_extensions=constants.EXTENSIONS,
                        prefix_hints=music.PREFIX_HINTS
                    )

                # Display results
                page.render_results_header()
                message = ['**Success!**',
                           f"- Processed files to `{output_path}`",
                           f"- Missing artwork info saved to: `{constants.MISSING_ART_PATH}`"]
                st.success('\n'.join(message))

                # Update config to store the most recent working paths
                app_config.download_directory = source_path
                app_config.library_path = output_path
                AppConfig.save(app_config)
            except Exception as e:
                st.error(f"Error processing files:\n{e}")
                logging.error(f"Error in {music.Namespace.FUNCTION_PROCESS}:\n{e}", exc_info=True)
    else:
        st.info('Function execution not yet implemented')
