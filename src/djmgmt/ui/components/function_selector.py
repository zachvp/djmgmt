'''Reusable function selection component for module pages.'''

from typing import Any, Callable
from types import ModuleType


class FunctionMapper:
    '''Maps function names to their implementations and descriptions.

    Provides a cleaner alternative to if/elif chains for mapping
    function constants to actual function objects.

    Example:
        mapper = FunctionMapper(module=library)
        mapper.add(library.Namespace.FUNCTION_RECORD_DYNAMIC, library.record_dynamic_tracks)

        description = mapper.get_description(library.Namespace.FUNCTION_RECORD_DYNAMIC)
        func = mapper.get_function(library.Namespace.FUNCTION_RECORD_DYNAMIC)
    '''

    def __init__(self, module: ModuleType):
        '''Initialize the function mapper.

        Args:
            module: Reference to the module containing the functions
        '''
        self.module = module
        self._function_map: dict[str, Callable[..., Any]] = {}

    def add(self, function_name: str, function_impl: Callable[..., Any]) -> None:
        '''Register a function name to implementation mapping.

        Args:
            function_name: The function name constant (e.g., Namespace.FUNCTION_LOG_DUPLICATES)
            function_impl: The actual function implementation
        '''
        self._function_map[function_name] = function_impl

    def add_all(self, mappings: dict[str, Callable[..., Any]]) -> None:
        '''Register multiple function mappings at once.

        Args:
            mappings: Dictionary of function_name -> function_impl
        '''
        self._function_map.update(mappings)

    def get_description(self, function_name: str) -> str:
        '''Get the docstring description for a function.

        Args:
            function_name: The function name constant

        Returns:
            The function's docstring, or 'Description missing' if not found
        '''
        if function_name in self._function_map:
            func = self._function_map[function_name]
            return func.__doc__ or 'Description missing'
        return 'Description missing'

    def get_function(self, function_name: str) -> Callable[..., Any] | None:
        '''Get the function implementation for a function name.

        Args:
            function_name: The function name constant

        Returns:
            The function implementation, or None if not found
        '''
        return self._function_map.get(function_name)

    def has_function(self, function_name: str) -> bool:
        '''Check if a function name is registered.

        Args:
            function_name: The function name constant

        Returns:
            True if the function is registered, False otherwise
        '''
        return function_name in self._function_map
