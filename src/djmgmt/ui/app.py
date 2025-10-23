"""Main Streamlit application for djmgmt toolkit."""
import streamlit as st
from djmgmt.ui.utils import config

# Main UI
st.title("djmgmt Tools")

# Display and Edit Config
st.write('### Config')

current_config = config.load()

# Create editable dataframe
edited_data = st.data_editor(
    current_config.to_dict(),
    width='stretch',
    hide_index=False,
    num_rows='fixed',
)

# Save button
if st.button('Save Config', type='primary'):
    try:
        # Create new config with edited values
        new_config = config.Config(edited_data)

        # Save to disk
        config.save(new_config)
        st.success('Configuration saved successfully!')
        st.rerun()
    except Exception as e:
        st.error(f'Failed to save configuration: {e}')

st.write('---')

# Call to action
st.write('''
         #### 👈  Choose a module from the left sidebar.
''')