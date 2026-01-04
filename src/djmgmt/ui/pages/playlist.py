import streamlit as st
import pandas as pd
import os

from djmgmt import playlist, common
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper
from djmgmt.ui.components.recent_file_input import RecentFileInput

# Constants
MODULE = 'playlist'
FUNCTION_EXTRACT = 'extract'
FUNCTIONS = [FUNCTION_EXTRACT]

# Function mapping
function_mapper = FunctionMapper(module=playlist)
function_mapper.add_all({
    FUNCTION_EXTRACT: playlist.extract
})

# Page initialization
PageBuilder.set_page_layout('wide')
page = PageBuilder(module_name=MODULE, module_ref=playlist)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, function_mapper.get_description)

# Function arguments
page.render_arguments_header()

# Load app config
app_config = AppConfig.load()

# Render playlist path input with auto-loading and latest file finder
finder = RecentFileInput.Finder(app_config.playlist_directory or '', common.find_latest_file, {'.tsv', '.txt', '.csv'})
input_path = RecentFileInput.render(
    label='Playlist Path',
    widget_key='widget_key_playlist_path',
    default_value=app_config.playlist_directory,
    finder=finder,
    button_label='Find Latest Playlist File'
)

# Render optional arguments - field selection checkboxes
st.write('**Field Selection**')
col1, col2, col3, col4 = st.columns(4)
with col1:
    include_number = st.checkbox('Number', value=False)
with col2:
    include_title = st.checkbox('Title', value=True)
with col3:
    include_artist = st.checkbox('Artist', value=True)
with col4:
    include_genre = st.checkbox('Genre', value=False)

# Separator between Arguments and Run sections
page.render_section_separator()

# Handle Run button
run_clicked = page.render_run_button()
if run_clicked:
    if function == FUNCTION_EXTRACT:
        # Validate input path
        if not input_path:
            st.error('Playlist path is required')
        elif not os.path.exists(input_path):
            st.error(f'File not found: {input_path}')
        else:
            extension = os.path.splitext(input_path)[1]
            if extension not in {'.tsv', '.txt', '.csv'}:
                st.error(f'Unsupported file extension: {extension}. Expected .tsv, .txt, or .csv')
            else:
                try:
                    # Run the function
                    results = playlist.extract(
                        input_path,
                        include_number,
                        include_title,
                        include_artist,
                        include_genre
                    )

                    # Build column names based on selections
                    column_names = []
                    if include_number:
                        column_names.append('Number')
                    if include_title:
                        column_names.append('Title')
                    if include_artist:
                        column_names.append('Artist')
                    if include_genre:
                        column_names.append('Genre')

                    # Default to all columns if none selected
                    if not column_names:
                        column_names = ['Number', 'Title', 'Artist', 'Genre']

                    # Parse tab-separated results into dataframe rows
                    rows = [line.split('\t') for line in results[1:]]

                    # Create dataframe
                    df = pd.DataFrame(rows, columns=column_names)

                    # Render results 
                    page.render_results_header()
                    st.success(f'Extracted {len(results)} tracks')
                    st.dataframe(
                        df,
                        hide_index=True,
                        width='stretch',
                        height=min((len(df) + 1) * 35, 800)
                    )

                    # Update config to store the most recent working playlist path
                    app_config.playlist_directory = os.path.dirname(input_path)
                    AppConfig.save(app_config)

                except Exception as e:
                    st.error(f'Error extracting playlist data: {e}')
