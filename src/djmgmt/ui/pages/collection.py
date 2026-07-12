'''Library, sync, and genre operations.'''
import logging
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st

from djmgmt import library, sync, genre, config, constants, common
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper
from djmgmt.ui.components.recent_file_input import RecentFileInput

# Page setup
PageBuilder.set_page_layout('wide')
page = PageBuilder(module_name='collection', module_ref=library)
page.initialize_logging()

st.header('collection')
app_config = AppConfig.load()

# Shared collection path (all tabs require it)
collection_finder = RecentFileInput.Finder(
    app_config.collection_directory or '',
    common.find_latest_file,
    {'.xml'}
)
collection_path = RecentFileInput.render(
    label='Collection Path',
    widget_key='widget_key_collection_path',
    default_value=app_config.collection_path,
    finder=collection_finder,
    button_label='Find Latest Collection Backup'
)

PageBuilder.render_section_separator()

tab_library, tab_sync, tab_genre = st.tabs(['Library', 'Sync', 'Genre'])

# ── Library tab ────────────────────────────────────────────────────────────
with tab_library:
    LIBRARY_FUNCTIONS = [library.Namespace.FUNCTION_RECORD_DYNAMIC]
    library_mapper = FunctionMapper(module=library)
    library_mapper.add_all({
        library.Namespace.FUNCTION_RECORD_DYNAMIC: library.record_dynamic_tracks,
    })

    library_fn = PageBuilder.render_function_selector(LIBRARY_FUNCTIONS, library_mapper.get_description, 'collection_library')
    PageBuilder.render_arguments_header()

    output_path = st.text_input('Output Path', value=config.COLLECTION_PATH_DYNAMIC)

    PageBuilder.render_section_separator()

    if PageBuilder.render_run_button('run_library'):
        if library_fn == library.Namespace.FUNCTION_RECORD_DYNAMIC:
            if not output_path:
                st.error('Output path is required for this function')
            else:
                try:
                    input_collection = library.load_collection(collection_path)
                    played_tracks    = library.get_played_tracks(input_collection)
                    unplayed_tracks  = library.get_unplayed_tracks(input_collection)
                    library.record_dynamic_tracks(collection_path, output_path)
                    PageBuilder.render_results_header()
                    st.write(f'- Played tracks: {len(played_tracks)}')
                    st.write(f'- Unplayed tracks: {len(unplayed_tracks)}')
                    st.success(f'Successfully recorded dynamic tracks to `{output_path}`')
                    app_config.collection_path = collection_path
                    AppConfig.save(app_config)
                except Exception as e:
                    st.error(f'Error recording dynamic tracks:\n{e}')
                    logging.error(f'Error in FUNCTION_RECORD_DYNAMIC: {e}', exc_info=True)

# ── Sync tab ───────────────────────────────────────────────────────────────
with tab_sync:
    FUNC_PREVIEW  = 'preview_sync'
    FUNC_PLAYLIST = 'run_playlist'
    SYNC_FUNCTIONS = [FUNC_PREVIEW, FUNC_PLAYLIST]

    sync_mapper = FunctionMapper(module=sync)
    sync_mapper.add_all({
        FUNC_PREVIEW:  sync.preview_sync,
        FUNC_PLAYLIST: sync.run_playlist,
    })

    sync_fn = PageBuilder.render_function_selector(SYNC_FUNCTIONS, sync_mapper.get_description, 'collection_sync')
    PageBuilder.render_arguments_header()

    library_path       = ''
    client_mirror_path = ''
    playlist_dot_path  = ''

    if sync_fn == FUNC_PREVIEW:
        library_path       = PageBuilder.render_path_input('Library Path', app_config.library_directory, 'Unable to load library path')
        client_mirror_path = PageBuilder.render_path_input('Client Mirror Path', app_config.client_mirror_path, 'Unable to load client mirror path')
    elif sync_fn == FUNC_PLAYLIST:
        playlist_dot_path = PageBuilder.render_path_input('Playlist Dot Path', 'dynamic.unplayed', 'Unable to load playlist path')

    PageBuilder.render_section_separator()

    if PageBuilder.render_run_button('run_sync'):
        if sync_fn == FUNC_PREVIEW:
            if not collection_path or not library_path or not client_mirror_path:
                st.error('All paths are required')
            else:
                try:
                    center = PageBuilder.create_center_context()
                    with center:
                        with st.spinner('Analyzing sync differences...'):
                            col = library.load_collection(collection_path)
                            preview_tracks = sync.preview_sync(col, client_mirror_path, library_path)
                    PageBuilder.render_results_header()
                    if not preview_tracks:
                        st.success('No tracks to sync - library is up to date!')
                    else:
                        st.success(f'Found {len(preview_tracks)} tracks to sync')
                        df_data = []
                        for track in preview_tracks:
                            df_data.append({
                                'Title':  track.metadata.title,
                                'Artist': track.metadata.artist,
                                'Album':  track.metadata.album,
                                'Path':   track.metadata.path,
                                'Type':   '🆕 New' if track.change_type == 'new' else '✏️ Changed'
                            })
                        df = pd.DataFrame(df_data)
                        st.dataframe(
                            df,
                            hide_index=True,
                            width='stretch',
                            height=min((len(df) + 1) * 35, 800),
                            column_config={
                                'Title':  st.column_config.TextColumn('Title', width='medium'),
                                'Artist': st.column_config.TextColumn('Artist', width='medium'),
                                'Album':  st.column_config.TextColumn('Album', width='medium'),
                                'Path':   st.column_config.TextColumn('Path', width='large'),
                                'Type':   st.column_config.TextColumn('Change Type', width='small')
                            }
                        )
                        new_count     = sum(1 for t in preview_tracks if t.change_type == 'new')
                        changed_count = sum(1 for t in preview_tracks if t.change_type == 'changed')
                        st.info(f'**Summary:** {new_count} new tracks, {changed_count} changed tracks')
                    app_config.collection_path         = collection_path
                    app_config.library_directory       = library_path
                    app_config.client_mirror_path = client_mirror_path
                    AppConfig.save(app_config)
                except Exception as e:
                    st.error(f'Error previewing sync: {e}')
                    logging.error(f'Error in {FUNC_PREVIEW}: {e}', exc_info=True)

        elif sync_fn == FUNC_PLAYLIST:
            if not collection_path or not playlist_dot_path:
                st.error('Collection Path and Playlist Dot Path are required')
            else:
                try:
                    center = PageBuilder.create_center_context()
                    with center:
                        with st.spinner('Syncing playlist...'):
                            result = sync.run_playlist(collection_path, playlist_dot_path, dry_run=False)
                    PageBuilder.render_results_header()
                    if result is None:
                        st.error('Playlist sync failed - check logs for details')
                    else:
                        local_path, rsync_path = result
                        st.success('Playlist synced successfully')
                        st.write(f'**Local:** `{local_path}`')
                        st.write(f'**Rsync implied path:** `{rsync_path}`')
                    app_config.collection_path = collection_path
                    AppConfig.save(app_config)
                except Exception as e:
                    st.error(f'Error syncing playlist: {e}')
                    logging.error(f'Error in {FUNC_PLAYLIST}: {e}', exc_info=True)

# ── Genre tab ──────────────────────────────────────────────────────────────
with tab_genre:
    GENRE_FUNCTIONS = [genre.Namespace.MODE_LONG, genre.Namespace.MODE_SHORT]
    genre_mapper = FunctionMapper(module=genre)
    genre_mapper.add_all({
        genre.Namespace.MODE_LONG:  genre.output_genres_long,
        genre.Namespace.MODE_SHORT: genre.output_genres_short,
    })

    genre_fn = PageBuilder.render_function_selector(GENRE_FUNCTIONS, genre_mapper.get_description, 'collection_genre')
    PageBuilder.render_arguments_header()

    source_input = st.text_input(
        'Source',
        value=genre.Namespace.SOURCE_COLLECTION,
        help=f"Either '{genre.Namespace.SOURCE_COLLECTION}' for the full collection, or a dot-separated playlist path (e.g., 'dynamic.unplayed')."
    )

    PageBuilder.render_section_separator()

    if PageBuilder.render_run_button('run_genre'):
        try:
            tree       = ET.parse(collection_path).getroot()
            collection = tree.find(constants.XPATH_COLLECTION)
            assert collection is not None, f"invalid node search for '{constants.XPATH_COLLECTION}'"
            source       = genre.resolve_source(tree, source_input)
            playlist_ids = set(library.get_track_ids(source))
            with PageBuilder.create_center_context():
                with st.spinner('Generating genre report...', show_time=True):
                    if genre_fn == genre.Namespace.MODE_LONG:
                        genres = genre.output_genres_long(playlist_ids, collection)
                    else:
                        genres = genre.output_genres_short(playlist_ids, collection)
            PageBuilder.render_results_header()
            rows = [{'Genre': g, 'Count': count} for g, count in genres.items()]
            rows.sort(key=lambda r: r['Count'], reverse=True)
            rows.append({'Genre': 'Total', 'Count': sum(r['Count'] for r in rows)})
            st.dataframe(
                rows,
                hide_index=True,
                width='stretch',
                column_config={
                    'Genre': st.column_config.TextColumn('Genre', width='large'),
                    'Count': st.column_config.NumberColumn('Count', width='small')
                }
            )
            app_config.collection_path = collection_path
            AppConfig.save(app_config)
        except Exception as e:
            st.error(f'Error computing genre report:\n{e}')
