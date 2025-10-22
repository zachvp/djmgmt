"""Main Streamlit application for djmgmt toolkit."""
import streamlit as st
import logging
from djmgmt.tags_info import log_duplicates, compare_tags
from djmgmt import common
import os

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
            common.configure_log(level=logging.DEBUG, path='/Users/zachvp/developer/djmgmt/src/djmgmt/tags_info.py')
            log_duplicates(input_path)
            st.success("Done - check src/djmgmt/logs/tags_info.log")
        elif function == "compare" and comparison:
            results = compare_tags(input_path, comparison)
            st.write(f"Found {len(results)} changes")
            st.dataframe(results)
else:
    st.info(f"Module '{module}' UI coming soon...")
