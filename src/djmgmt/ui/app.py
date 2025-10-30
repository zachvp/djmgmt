"""Main Streamlit application for djmgmt toolkit."""
import streamlit as st
from djmgmt.ui.utils.config import AppConfig
from djmgmt.ui.utils.page_base import PageBuilder

# Constants
CONFIG_KEY_LABEL   = 'Setting'
CONFIG_VALUE_LAEBL = 'Value'

# Streamlit view setup
st.set_page_config(layout="wide")

# Main UI
st.title("djmgmt Tools")

# Display and Edit Config
st.write('### Config')

current_config = AppConfig.load()

# Convert to list of dicts to define column headings (sorted alphabetically by key)
config_data = [{CONFIG_KEY_LABEL : k, CONFIG_VALUE_LAEBL : v} for k, v in sorted(current_config.to_dict().items())]

# Create editable dataframe for config values with custom column headings
edited_data = st.data_editor(
    config_data,
    column_config={
        CONFIG_KEY_LABEL   : st.column_config.TextColumn(CONFIG_KEY_LABEL, disabled=True),
        CONFIG_VALUE_LAEBL : st.column_config.TextColumn(CONFIG_VALUE_LAEBL)
    },
    hide_index=True,
    num_rows='fixed',
)

# Save button
center = PageBuilder.create_center_context()
with center:
    if st.button('Save Config', type='primary', width='stretch'):
        try:
            # Convert back to dict
            edited_config = {row[CONFIG_KEY_LABEL]: row[CONFIG_VALUE_LAEBL] for row in edited_data}

            # Create new config with edited values
            new_config = AppConfig(edited_config)

            # Save to disk
            AppConfig.save(new_config)
            st.success('Configuration saved successfully!')
            st.rerun()
        except Exception as e:
            st.error(f'Failed to save configuration: {e}')

PageBuilder.render_section_separator()

# Call to action
st.write('#### 👈  Choose a module from the left sidebar.')