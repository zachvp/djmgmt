"""Main Streamlit application for djmgmt toolkit."""
import streamlit as st
from djmgmt.ui.utils import config

# Main UI
st.title("djmgmt Tools")

# Display Config
st.write('### Config')
st.dataframe(config.load().to_dict())

st.write('---')

# Call to action
st.write('''
         #### 👈  Choose a module from the left sidebar.
''')