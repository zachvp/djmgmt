"""Main Streamlit application for djmgmt toolkit."""
import streamlit as st
import logging
import os
from djmgmt.tags_info import log_duplicates, compare_tags
from djmgmt import common
from djmgmt import constants

# Helpers
def create_log_path(module_name: str) -> str:
    relative_path = f"src/djmgmt/{module_name}.py"
    return str(constants.PROJECT_ROOT.joinpath(relative_path))

# Main UI
st.title("djmgmt Tools")

# Module selection
module = st.sidebar.selectbox(
    "Module",
    ["tags_info", "library", "sync", "encode", "music"]
)

st.header(f"{module}")

# For MVP, start with tags_info as proof of concept
if module == "tags_info":
    function = st.selectbox("Function", [
        "log_duplicates",
        "write_identifiers",
        "compare"
    ])

    input_path = st.text_input("Input Path", value=os.path.expanduser("~/Music"))

    comparison = None
    if function == "compare":
        comparison = st.text_input("Comparison Path")

    output = st.text_input("Output File (optional)")

    if st.button("Run"):
        if function == "log_duplicates":
            # Configure logging before running function
            log_path = create_log_path(module)
            common.configure_log(level=logging.DEBUG, path=str(log_path))
            log_duplicates(input_path)
            st.success(f"Done - check {log_path}")
        elif function == "compare" and comparison:
            results = compare_tags(input_path, comparison)
            st.write(f"Found {len(results)} changes")
            st.dataframe(results)
else:
    st.info(f"Module '{module}' UI coming soon...")
