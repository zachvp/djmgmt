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
FUNCTION_PRESS_MIX = 'press_mix'
FUNCTIONS = [FUNCTION_EXTRACT, FUNCTION_PRESS_MIX]

# Function mapping
function_mapper = FunctionMapper(module=playlist)
function_mapper.add_all({
    FUNCTION_EXTRACT: playlist.extract,
    FUNCTION_PRESS_MIX: playlist.press_mix
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

# Common inputs
# Render playlist path input with auto-loading and latest file finder
playlist_finder = RecentFileInput.Finder(app_config.playlist_directory or '', common.find_latest_file, {'.tsv', '.txt', '.csv'})
input_path = RecentFileInput.render(
    label='Playlist Path',
    widget_key='widget_key_playlist_path',
    default_value=app_config.playlist_directory,
    finder=playlist_finder,
    button_label='Find Latest Playlist File'
)

# Function-specific inputs
# Initialize variables
music_file_path = ''
csv_file_path = ''
include_number = False
include_title = True
include_artist = True
include_genre = False

if function == FUNCTION_PRESS_MIX:
    # Render music file path input with latest file finder
    music_finder = RecentFileInput.Finder(app_config.mix_recording_directory or '', common.find_latest_file, {'.wav', '.aiff', '.aif'})
    music_file_path = RecentFileInput.render(
        label='Music File Path',
        widget_key='widget_key_music_file_path',
        default_value=app_config.mix_recording_directory,
        finder=music_finder,
        button_label='Find Latest Music File'
    )

    # Render CSV file path input with latest file finder
    csv_finder = RecentFileInput.Finder(app_config.pressed_mix_directory or '', common.find_latest_file, {'.csv'})
    csv_file_path = RecentFileInput.render(
        label='CSV File Path (optional)',
        widget_key='widget_key_csv_file_path',
        default_value=app_config.pressed_mix_directory,
        finder=csv_finder,
        button_label='Find Latest CSV File'
    )

elif function == FUNCTION_EXTRACT:
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

    elif function == FUNCTION_PRESS_MIX:
        # Validate inputs
        if not music_file_path:
            st.error('Music file path is required')
        elif not os.path.exists(music_file_path):
            st.error(f'File not found: {music_file_path}')
        elif not input_path:
            st.error('Playlist path is required')
        elif not os.path.exists(input_path):
            st.error(f'File not found: {input_path}')
        else:
            # Validate file extensions
            music_extension = os.path.splitext(music_file_path)[1]
            if music_extension not in {'.wav', '.aiff', '.aif'}:
                st.error(f'Unsupported music file extension: {music_extension}. Expected .wav, .aiff, or .aif')
            else:
                playlist_extension = os.path.splitext(input_path)[1]
                if playlist_extension not in {'.tsv', '.txt', '.csv'}:
                    st.error(f'Unsupported playlist file extension: {playlist_extension}. Expected .tsv, .txt, or .csv')
                else:
                    try:
                        # Run the function
                        mix = playlist.press_mix(
                            music_file_path=music_file_path,
                            playlist_file_path=input_path,
                            csv_file_path=csv_file_path
                        )

                        # Render results
                        page.render_results_header()
                        st.success('Mix pressed successfully')
                        st.write('**Mix Details**')
                        st.write(f'Date Recorded: {mix.date_recorded}')
                        st.write(f'Music Path: {mix.music_path}')
                        st.write(f'Playlist Path: {mix.playlist_file_path}')

                        # Update config to store the most recent working paths
                        app_config.mix_recording_directory = os.path.dirname(music_file_path)
                        app_config.playlist_directory = os.path.dirname(input_path)
                        if csv_file_path:
                            app_config.pressed_mix_directory = os.path.dirname(csv_file_path)
                        AppConfig.save(app_config)

                    except Exception as e:
                        st.error(f'Error pressing mix: {e}')
