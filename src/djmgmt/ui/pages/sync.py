import streamlit as st
import pandas as pd
import logging

from djmgmt import sync, library, common
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper
from djmgmt.ui.components.recent_file_input import RecentFileInput

# Constants
MODULE = 'sync'
FUNCTION_PREVIEW = 'preview_sync'
FUNCTION_PLAYLIST = 'run_playlist'
FUNCTIONS = [FUNCTION_PREVIEW, FUNCTION_PLAYLIST]

# Function mapping
function_mapper = FunctionMapper(module=sync)
function_mapper.add(FUNCTION_PREVIEW, sync.preview_sync)
function_mapper.add(FUNCTION_PLAYLIST, sync.run_playlist)

# Page initialization
PageBuilder.set_page_layout('wide')
page = PageBuilder(module_name=MODULE, module_ref=sync)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, function_mapper.get_description, MODULE)

# Function arguments
page.render_arguments_header()

# Load app config
app_config = AppConfig.load()

# Render collection path input with latest backup finder
collection_finder = RecentFileInput.Finder(
    app_config.collection_directory or '',
    common.find_latest_file,
    {'.xml'}
)
collection_path = RecentFileInput.render(
    label='Collection Path',
    widget_key='widget_key_sync_preview_collection',
    default_value=app_config.collection_path,
    finder=collection_finder,
    button_label='Find Latest Collection Backup'
)

# Function-specific arguments
library_path = ''
client_mirror_path = ''
playlist_dot_path = ''
dry_run = False

if function == FUNCTION_PREVIEW:
    library_path = page.render_path_input('Library Path', app_config.library_directory, 'Unable to load library path')
    client_mirror_path = page.render_path_input('Client Mirror Path', app_config.client_mirror_directory, 'Unable to load client mirror path')
elif function == FUNCTION_PLAYLIST:
    playlist_dot_path = page.render_path_input('Playlist Dot Path', 'dynamic.unplayed', 'Unable to load playlist path')

# Separator between Arguments and Run sections
page.render_section_separator()

# Handle Run button
run_clicked = page.render_run_button()
if run_clicked:
    if function == FUNCTION_PREVIEW:
        if not collection_path or not library_path or not client_mirror_path:
            st.error('All paths are required')
        else:
            try:
                # Load collection and run preview
                center = page.create_center_context()
                with center:
                    with st.spinner('Analyzing sync differences...'):
                        collection = library.load_collection(collection_path)
                        preview_tracks = sync.preview_sync(collection, client_mirror_path, library_path)

                # Display results
                page.render_results_header()

                if not preview_tracks:
                    st.success('No tracks to sync - library is up to date!')
                else:
                    st.success(f'Found {len(preview_tracks)} tracks to sync')

                    # Convert to dataframe with color coding
                    df_data = []
                    for track in preview_tracks:
                        df_data.append({
                            'Title'  : track.metadata.title,
                            'Artist' : track.metadata.artist,
                            'Album'  : track.metadata.album,
                            'Path'   : track.metadata.path,
                            'Type'   : '🆕 New' if track.change_type == 'new' else '✏️ Changed'
                        })

                    df = pd.DataFrame(df_data)

                    # Display with styled dataframe
                    st.dataframe(
                        df,
                        hide_index=True,
                        width='stretch',
                        height=min((len(df) + 1) * 35, 800),
                        column_config={
                            'Title'  : st.column_config.TextColumn('Title', width='medium'),
                            'Artist' : st.column_config.TextColumn('Artist', width='medium'),
                            'Album'  : st.column_config.TextColumn('Album', width='medium'),
                            'Path'   : st.column_config.TextColumn('Path', width='large'),
                            'Type'   : st.column_config.TextColumn('Change Type', width='small')
                        }
                    )

                    # Show summary counts
                    new_count = sum(1 for t in preview_tracks if t.change_type == 'new')
                    changed_count = sum(1 for t in preview_tracks if t.change_type == 'changed')
                    st.info(f'**Summary:** {new_count} new tracks, {changed_count} changed tracks')

                # Update config
                app_config.collection_path = collection_path
                app_config.library_directory = library_path
                app_config.client_mirror_directory = client_mirror_path
                AppConfig.save(app_config)

            except Exception as e:
                st.error(f'Error previewing sync: {e}')
                logging.error(f'Error in {FUNCTION_PREVIEW}: {e}', exc_info=True)

    elif function == FUNCTION_PLAYLIST:
        if not collection_path or not playlist_dot_path:
            st.error('Collection Path and Playlist Path are required')
        else:
            try:
                center = page.create_center_context()
                with center:
                    with st.spinner('Syncing playlist...'):
                        result = sync.run_playlist(collection_path, playlist_dot_path, dry_run=dry_run)

                page.render_results_header()

                if result is None:
                    st.error('Playlist sync failed - check logs for details')
                else:
                    local_path, rsync_path = result
                    st.success('Playlist synced successfully')
                    st.write(f'**Local:** `{local_path}`')
                    st.write(f'**Rsync implied path:** `{rsync_path}`')

                # Update config
                app_config.collection_path = collection_path
                AppConfig.save(app_config)

            except Exception as e:
                st.error(f'Error syncing playlist: {e}')
                logging.error(f'Error in {FUNCTION_PLAYLIST}: {e}', exc_info=True)
