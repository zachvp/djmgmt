'''Music, tags, and playlist operations.'''
import os
import logging
import pandas as pd
import streamlit as st

from djmgmt import music, tags_info, playlist, constants, config, common
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper
from djmgmt.ui.components.recent_file_input import RecentFileInput
from djmgmt.ui.components.progress_panel import ProgressPanel

# Page setup
PageBuilder.set_page_layout('wide')
page = PageBuilder(module_name='music', module_ref=music)
page.initialize_logging()

st.header('music')
app_config = AppConfig.load()

tab_music, tab_tags, tab_playlist = st.tabs(['Music', 'Tags', 'Playlist'])

# ── Music tab ──────────────────────────────────────────────────────────────
with tab_music:
    MUSIC_FUNCTIONS = [
        music.Namespace.FUNCTION_PROCESS,
        music.Namespace.FUNCTION_UPDATE_LIBRARY,
    ]
    music_mapper = FunctionMapper(module=music)
    music_mapper.add_all({
        music.Namespace.FUNCTION_PROCESS:        music.process,
        music.Namespace.FUNCTION_UPDATE_LIBRARY: music.update_library,
    })

    music_fn = PageBuilder.render_function_selector(MUSIC_FUNCTIONS, music_mapper.get_description, 'music_music')
    PageBuilder.render_arguments_header()

    source_path = None
    output_path = None
    client_mirror_path = None
    collection_export_dir_path = None
    full_scan = True

    if music_fn == music.Namespace.FUNCTION_PROCESS:
        source_path = PageBuilder.render_path_input('Source Path', app_config.download_directory, 'Unable to load source path')
        output_path = PageBuilder.render_path_input('Output Path', app_config.library_directory, 'Unable to load output path')
    elif music_fn == music.Namespace.FUNCTION_UPDATE_LIBRARY:
        source_path = PageBuilder.render_path_input('Source Path', app_config.download_directory, 'Unable to load source path')
        output_path = PageBuilder.render_path_input('Library Path', app_config.library_directory, 'Unable to load library path')
        client_mirror_path = PageBuilder.render_path_input('Client Mirror Path', app_config.client_mirror_path, 'Unable to load client mirror path')
        collection_export_dir_path = PageBuilder.render_path_input('Collection Export Directory Path', app_config.collection_directory, 'Unable to load collection directory path')
        full_scan = PageBuilder.render_checkbox_input('Full Scan', default_value=True)

    PageBuilder.render_section_separator()

    if PageBuilder.render_run_button('run_music'):
        if music_fn == music.Namespace.FUNCTION_PROCESS:
            if not source_path or not output_path:
                st.error('Source and output paths are required')
            else:
                try:
                    app_config.download_directory = source_path
                    app_config.library_directory = output_path
                    AppConfig.save(app_config)
                    center = PageBuilder.create_center_context()
                    with center:
                        with st.spinner(f"Processing files from `{source_path}` to `{output_path}`", show_time=True):
                            results = music.process(
                                source=source_path,
                                output=output_path,
                                valid_extensions=constants.EXTENSIONS,
                                prefix_hints=music.PREFIX_HINTS
                            )
                    PageBuilder.render_results_header()
                    message = [
                        '**Success!**',
                        f'- Processed {len(results.processed_files)} files to `{output_path}`',
                        f'- Extracted {results.archives_extracted} archives',
                        f'- Encoded {results.files_encoded} files to standard format',
                        f'- Found {len(results.missing_art_paths)} missing artwork files',
                        f'- Missing artwork info saved to: `{config.MISSING_ART_PATH}`'
                    ]
                    st.success('\n'.join(message))
                    missing_set = set(results.missing_art_paths)
                    df_data = []
                    for source_file, output_file in results.processed_files:
                        status = '⚠ Missing Art' if output_file in missing_set else '✓ Processed'
                        df_data.append({'Source': source_file, 'Output': output_file, 'Status': status})
                    df = pd.DataFrame(df_data)
                    st.dataframe(
                        df,
                        hide_index=True,
                        use_container_width=True,
                        height=min((len(df) + 1) * 35, 800),
                        column_config={
                            'Source': st.column_config.TextColumn('Source', width='large'),
                            'Output': st.column_config.TextColumn('Output', width='large'),
                            'Status': st.column_config.TextColumn('Status', width='small')
                        }
                    )
                except Exception as e:
                    st.error(f"Error processing files:\n{e}")
                    logging.error(f"Error in {music.Namespace.FUNCTION_PROCESS}:\n{e}", exc_info=True)

        elif music_fn == music.Namespace.FUNCTION_UPDATE_LIBRARY:
            if not source_path or not output_path or not client_mirror_path or not collection_export_dir_path:
                st.error('Source path, library path, client mirror path, and collection export path are required')
            else:
                try:
                    app_config.download_directory = source_path
                    app_config.library_directory = output_path
                    app_config.client_mirror_path = client_mirror_path
                    app_config.collection_directory = collection_export_dir_path
                    AppConfig.save(app_config)
                    panel = ProgressPanel(f"Updating library from `{source_path}` to `{output_path}`")
                    try:
                        music.update_library(
                            new_music_dir_path=source_path,
                            library_path=output_path,
                            client_mirror_path=client_mirror_path,
                            collection_export_dir_path=collection_export_dir_path,
                            processed_collection_path=config.COLLECTION_PATH_PROCESSED,
                            merged_collection_path=config.COLLECTION_PATH_MERGED,
                            valid_extensions=constants.EXTENSIONS,
                            prefix_hints=music.PREFIX_HINTS,
                            full_scan=full_scan,
                            bus=panel.bus
                        )
                    except Exception:
                        panel.fail('Library update failed')
                        raise
                    panel.complete(f"Updated library at `{output_path}`")
                    PageBuilder.render_results_header()
                    message = [
                        '**Success!**',
                        f"- Updated library at `{output_path}`",
                        f"- Synced to client mirror at `{client_mirror_path}`",
                        f"- Used `{collection_export_dir_path}` as collection export directory.",
                        f"- Collection saved to: `{config.COLLECTION_PATH_PROCESSED}`",
                        f"- Full scan: `{full_scan}`"
                    ]
                    st.success('\n'.join(message))
                except Exception as e:
                    st.error(f"Error updating library:\n{e}")
                    logging.error(f"Error in {music.Namespace.FUNCTION_UPDATE_LIBRARY}:\n{e}", exc_info=True)

# ── Tags tab ───────────────────────────────────────────────────────────────
with tab_tags:
    TAGS_FUNCTIONS = [
        tags_info.Namespace.FUNCTION_LOG_DUPLICATES,
        tags_info.Namespace.FUNCTION_COMPARE,
    ]
    tags_mapper = FunctionMapper(module=tags_info)
    tags_mapper.add_all({
        tags_info.Namespace.FUNCTION_LOG_DUPLICATES: tags_info.log_duplicates,
        tags_info.Namespace.FUNCTION_COMPARE:        tags_info.compare_tags_with_diff,
    })

    tags_fn = PageBuilder.render_function_selector(TAGS_FUNCTIONS, tags_mapper.get_description, 'music_tags')
    PageBuilder.render_arguments_header()

    tags_input_path = PageBuilder.render_path_input('Input Path', app_config.library_directory, 'Unable to load input path')
    comparison = None
    if tags_fn == tags_info.Namespace.FUNCTION_COMPARE:
        comparison = st.text_input('Comparison Path', value=app_config.client_mirror_path or '')

    PageBuilder.render_section_separator()

    if PageBuilder.render_run_button('run_tags'):
        if tags_fn == tags_info.Namespace.FUNCTION_LOG_DUPLICATES:
            app_config.library_directory = tags_input_path
            AppConfig.save(app_config)
            center = PageBuilder.create_center_context()
            with center:
                with st.spinner('Finding duplicate tracks...', show_time=True):
                    duplicates = tags_info.log_duplicates(tags_input_path)
            PageBuilder.render_results_header()
            st.dataframe(sorted(duplicates), width='stretch', column_config={'value': 'Duplicate Track Paths'})
        elif tags_fn == tags_info.Namespace.FUNCTION_COMPARE and comparison:
            app_config.library_directory = tags_input_path
            app_config.client_mirror_path = comparison
            AppConfig.save(app_config)
            center = PageBuilder.create_center_context()
            with center:
                with st.spinner('Comparing track metadata...', show_time=True):
                    results = tags_info.compare_tags_with_diff(tags_input_path, comparison)
            PageBuilder.render_results_header()
            st.write(f'Found {len(results)} changes')
            df_data = []
            for source_p, compare_p, diff in results:
                df_data.append({'Input Path': source_p, 'Comparison Path': compare_p, 'Differences': str(diff)})
            df = pd.DataFrame(df_data)
            st.dataframe(
                df,
                hide_index=True,
                width='stretch',
                column_config={
                    'Input Path':      st.column_config.TextColumn('Input Path', width='large'),
                    'Comparison Path': st.column_config.TextColumn('Comparison Path', width='large'),
                    'Differences':     st.column_config.TextColumn('Differences', width='medium')
                }
            )

# ── Playlist tab ───────────────────────────────────────────────────────────
with tab_playlist:
    FUNC_EXTRACT   = 'extract'
    FUNC_PRESS_MIX = 'press_mix'
    PLAYLIST_FUNCTIONS = [FUNC_EXTRACT, FUNC_PRESS_MIX]

    playlist_mapper = FunctionMapper(module=playlist)
    playlist_mapper.add_all({
        FUNC_EXTRACT:   playlist.extract,
        FUNC_PRESS_MIX: playlist.press_mix,
    })

    playlist_fn = PageBuilder.render_function_selector(PLAYLIST_FUNCTIONS, playlist_mapper.get_description, 'music_playlist')
    PageBuilder.render_arguments_header()

    playlist_finder = RecentFileInput.Finder(app_config.playlist_directory or '', common.find_latest_file, {'.tsv', '.txt', '.csv'})
    playlist_input_path = RecentFileInput.render(
        label='Playlist Path',
        widget_key='widget_key_playlist_path',
        default_value=app_config.playlist_directory,
        finder=playlist_finder,
        button_label='Find Latest Playlist File'
    )

    music_file_path = ''
    csv_file_path   = ''
    include_number  = False
    include_title   = True
    include_artist  = True
    include_genre   = False

    if playlist_fn == FUNC_PRESS_MIX:
        music_finder = RecentFileInput.Finder(app_config.mix_recording_directory or '', common.find_latest_file, {'.wav', '.aiff', '.aif'})
        music_file_path = RecentFileInput.render(
            label='Music File Path',
            widget_key='widget_key_music_file_path',
            default_value=app_config.mix_recording_directory,
            finder=music_finder,
            button_label='Find Latest Music File'
        )
        csv_finder = RecentFileInput.Finder(app_config.pressed_mix_directory or '', common.find_latest_file, {'.csv'})
        csv_file_path = RecentFileInput.render(
            label='CSV File Path (optional)',
            widget_key='widget_key_csv_file_path',
            default_value=app_config.pressed_mix_directory,
            finder=csv_finder,
            button_label='Find Latest CSV File'
        )
    elif playlist_fn == FUNC_EXTRACT:
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

    PageBuilder.render_section_separator()

    if PageBuilder.render_run_button('run_playlist'):
        if playlist_fn == FUNC_EXTRACT:
            if not playlist_input_path:
                st.error('Playlist path is required')
            elif not os.path.exists(playlist_input_path):
                st.error(f'File not found: {playlist_input_path}')
            else:
                ext = os.path.splitext(playlist_input_path)[1]
                if ext not in {'.tsv', '.txt', '.csv'}:
                    st.error(f'Unsupported file extension: {ext}. Expected .tsv, .txt, or .csv')
                else:
                    try:
                        app_config.playlist_directory = os.path.dirname(playlist_input_path)
                        AppConfig.save(app_config)
                        results = playlist.extract(playlist_input_path, include_number, include_title, include_artist, include_genre)
                        column_names = []
                        if include_number:
                            column_names.append('Number')
                        if include_title:
                            column_names.append('Title')
                        if include_artist:
                            column_names.append('Artist')
                        if include_genre:
                            column_names.append('Genre')
                        if not column_names:
                            column_names = ['Number', 'Title', 'Artist', 'Genre']
                        rows = [line.split('\t') for line in results[1:]]
                        df = pd.DataFrame(rows, columns=column_names)
                        PageBuilder.render_results_header()
                        st.success(f'Extracted {len(results)} tracks')
                        st.dataframe(df, hide_index=True, width='stretch', height=min((len(df) + 1) * 35, 800))
                    except Exception as e:
                        st.error(f'Error extracting playlist data: {e}')

        elif playlist_fn == FUNC_PRESS_MIX:
            if not music_file_path:
                st.error('Music file path is required')
            elif not os.path.exists(music_file_path):
                st.error(f'File not found: {music_file_path}')
            elif not playlist_input_path:
                st.error('Playlist path is required')
            elif not os.path.exists(playlist_input_path):
                st.error(f'File not found: {playlist_input_path}')
            else:
                music_ext    = os.path.splitext(music_file_path)[1]
                playlist_ext = os.path.splitext(playlist_input_path)[1]
                if music_ext not in {'.wav', '.aiff', '.aif'}:
                    st.error(f'Unsupported music file extension: {music_ext}. Expected .wav, .aiff, or .aif')
                elif playlist_ext not in {'.tsv', '.txt', '.csv'}:
                    st.error(f'Unsupported playlist file extension: {playlist_ext}. Expected .tsv, .txt, or .csv')
                else:
                    try:
                        app_config.playlist_directory = os.path.dirname(playlist_input_path)
                        app_config.mix_recording_directory = os.path.dirname(music_file_path)
                        if csv_file_path:
                            app_config.pressed_mix_directory = os.path.dirname(csv_file_path)
                        AppConfig.save(app_config)
                        mix = playlist.press_mix(
                            music_file_path=music_file_path,
                            playlist_file_path=playlist_input_path,
                            csv_file_path=csv_file_path
                        )
                        PageBuilder.render_results_header()
                        st.success('Mix pressed successfully')
                        st.write('**Mix Details**')
                        st.write(f'Date Recorded: {mix.date_recorded}')
                        st.write(f'Music Path: {mix.original_file_path}')
                        st.write(f'Playlist Path: {mix.playlist_file_path}')
                    except Exception as e:
                        st.error(f'Error pressing mix: {e}')
