import streamlit as st
import xml.etree.ElementTree as ET

from djmgmt import genre, constants, common, library
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder
from djmgmt.ui.components.function_selector import FunctionMapper
from djmgmt.ui.components.recent_file_input import RecentFileInput

# Constants
MODULE = 'genre'
FUNCTIONS = [
    genre.Namespace.MODE_LONG,
    genre.Namespace.MODE_SHORT
]

# Function mapping
function_mapper = FunctionMapper(module=genre)
function_mapper.add_all({
    genre.Namespace.MODE_LONG : genre.output_genres_long
})

# Page initialization
PageBuilder.set_page_layout('wide')
page = PageBuilder(module_name=MODULE, module_ref=genre)
page.initialize_logging()
page.render_header_and_overview()
function = page.render_function_selector(FUNCTIONS, function_mapper.get_description, MODULE)

# Function arguments
page.render_arguments_header()

# Load the app config
app_config = AppConfig.load()

# Render collection path input with auto-loading and backup finder
finder = RecentFileInput.Finder(app_config.collection_directory or '', common.find_latest_file, {'.xml'})
collection_path = RecentFileInput.render(
    label='Collection Path',
    widget_key='widget_key_collection_path',
    default_value=app_config.collection_path,
    finder=finder,
    button_label='Find Latest Collection Backup'
)

# Source input
source_input = st.text_input(
    'Source',
    value=genre.Namespace.SOURCE_COLLECTION,
    help=f"Either '{genre.Namespace.SOURCE_COLLECTION}' for the full collection, or a dot-separated playlist path (e.g., 'dynamic.unplayed')."
)

# Separator between Arguments and Run sections
page.render_section_separator()

# Handle Run button
run_clicked = page.render_run_button()
if run_clicked:
    if function == genre.Namespace.MODE_LONG or function == genre.Namespace.MODE_SHORT:
        try:
            tree = ET.parse(collection_path).getroot()
            collection = tree.find(constants.XPATH_COLLECTION)
            assert collection is not None, f"invalid node search for '{constants.XPATH_COLLECTION}'"

            source = genre.resolve_source(tree, source_input)
            playlist_ids = set(library.get_track_ids(source))

            # Run the function
            center = page.create_center_context()
            with center:
                with st.spinner('Generating genre report...', show_time=True):
                    if function == genre.Namespace.MODE_LONG:
                        lines = genre.output_genres_long(playlist_ids, collection)
                    else:
                        lines = genre.output_genres_short(playlist_ids, collection)

            # Render results
            page.render_results_header()
            rows = [{'Genre': g, 'Count': int(c)} for g, c in (line.split('\t') for line in lines)]
            rows.sort(key=lambda r: r['Count'], reverse=True)
            st.dataframe(
                rows,
                hide_index=True,
                width='stretch',
                column_config={
                    'Genre': st.column_config.TextColumn('Genre', width='large'),
                    'Count': st.column_config.NumberColumn('Count', width='small')
                }
            )

            # Update config
            app_config.collection_path = collection_path
            AppConfig.save(app_config)
        except Exception as e:
            st.error(f"Error computing genre report:\n{e}")
            
