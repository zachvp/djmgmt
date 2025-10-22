"""Main Streamlit application for djmgmt toolkit."""
import streamlit as st
import logging
import os
from typing import Any, Callable
from djmgmt.tags_info import log_duplicates, compare_tags
from djmgmt import common
from djmgmt import constants
from djmgmt.ui.components.module_tab import render_module_tab


# Helpers
def create_file_path(module_name: str) -> str:
    relative_path = f"src/djmgmt/{module_name}.py"
    return str(constants.PROJECT_ROOT.joinpath(relative_path))


# tags_info module configuration
def tags_info_input_collectors() -> dict[str, Any]:
    """Define input collectors for each tags_info function."""

    def collect_log_duplicates_inputs() -> dict[str, Any]:
        input_path = st.text_input("Input Path", value=os.path.expanduser("~/Music"))
        return {"input_path": input_path}

    def collect_write_identifiers_inputs() -> dict[str, Any]:
        input_path = st.text_input("Input Path", value=os.path.expanduser("~/Music"))
        output = st.text_input("Output File (optional)")
        return {"input_path": input_path, "output": output}

    def collect_compare_inputs() -> dict[str, Any]:
        input_path = st.text_input("Input Path", value=os.path.expanduser("~/Music"))
        comparison = st.text_input("Comparison Path")
        output = st.text_input("Output File (optional)")
        return {"input_path": input_path, "comparison": comparison, "output": output}

    return {
        "log_duplicates": collect_log_duplicates_inputs,
        "write_identifiers": collect_write_identifiers_inputs,
        "compare": collect_compare_inputs
    }


def tags_info_executors():
    """Define executors for each tags_info function."""

    def execute_log_duplicates(params: dict[str, Any]) -> None:
        file_path = create_file_path("tags_info")
        log_path = common.configure_log(level=logging.DEBUG, path=file_path)
        log_duplicates(params["input_path"])
        st.success(f"Done - check {log_path}")

    def execute_write_identifiers(params: dict[str, Any]) -> None:
        st.info("write_identifiers not yet implemented in UI")

    def execute_compare(params: dict[str, Any]) -> None:
        if not params.get("comparison"):
            st.error("Comparison path is required")
            return
        results = compare_tags(params["input_path"], params["comparison"])
        st.write(f"Found {len(results)} changes")
        st.dataframe(results)

    return {
        "log_duplicates": execute_log_duplicates,
        "write_identifiers": execute_write_identifiers,
        "compare": execute_compare
    }


# Main UI
st.title("djmgmt Tools")

# Module selection
module = st.sidebar.selectbox(
    "Module",
    ["tags_info", "library", "sync", "encode", "music"]
)

# Render appropriate module
if module == "tags_info":
    render_module_tab(
        module_name="tags_info",
        functions={
            "log_duplicates": log_duplicates,
            "write_identifiers": lambda: None,  # Placeholder
            "compare": compare_tags
        },
        input_collectors=tags_info_input_collectors(),
        executors=tags_info_executors(),
        descriptions={
            "__module__": "Uses audio file metadata to determine duplicates",
            "log_duplicates": "Find duplicate tracks by artist+title",
            "write_identifiers": "Write track identifiers to file",
            "compare": "Compare tags between two directories"
        }
    )
else:
    st.header(f"{module}")
    st.info(f"Module '{module}' UI coming soon...")
