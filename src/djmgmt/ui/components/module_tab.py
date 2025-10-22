"""Reusable component for rendering module functionality tabs."""
import streamlit as st
from typing import Callable, Any


def render_module_tab(
    module_name: str,
    functions: dict[str, Callable],
    input_collectors: dict[str, Callable[[], dict[str, Any]]],
    executors: dict[str, Callable[[dict[str, Any]], None]],
    descriptions: dict[str, str] | None = None
) -> None:
    """
    Render a tab for a djmgmt module with function selection and execution.

    Args:
        module_name: Display name of the module
        functions: Dict mapping function names to callable functions
        input_collectors: Dict mapping function names to functions that collect inputs
                         Each collector returns a dict of parameters for the function
        executors: Dict mapping function names to execution handlers
                  Each executor receives the collected parameters and executes the function
        descriptions: Optional dict mapping function names to descriptions
    """
    st.header(module_name)

    if descriptions and "__module__" in descriptions:
        with st.expander("Module Info", expanded=True):
            st.write(descriptions["__module__"])

    function_name = st.selectbox(
        "Function",
        options=list(functions.keys()),
        format_func=lambda x: f"{x} - {descriptions.get(x, '')}" if descriptions else x
    )

    # Collect inputs specific to selected function
    params: dict[str, Any] = {}
    if function_name in input_collectors:
        params = input_collectors[function_name]()

    # Execute on button click
    if st.button("Run"):
        if function_name in executors:
            executors[function_name](params)
        else:
            st.error(f"No executor defined for {function_name}")
