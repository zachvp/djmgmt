'''Typed, in-process event bus for reporting operation progress to callers.

Long-running operations accept an optional `EventBus` and emit structured events as
they advance through their phases. Callers subscribe to render progress; the event
types form the progress contract, independent of the logging output.

Example:
    >>> bus = EventBus()
    >>> bus.subscribe(lambda event: print(event))
    >>> music.update_library(..., events=bus)
'''

import logging
from dataclasses import dataclass
from typing import Callable, Union

# region Phases

class Phase:
    '''Identifiers for the phases of a long-running operation.'''

    PROCESS           = 'process'
    RECORD_COLLECTION = 'record_collection'
    BUILD_MAPPINGS    = 'build_mappings'
    SYNC              = 'sync'

LABELS: dict[str, str] = {
    Phase.PROCESS:           'Processing new files',
    Phase.RECORD_COLLECTION: 'Recording collection',
    Phase.BUILD_MAPPINGS:    'Building sync mappings',
    Phase.SYNC:              'Syncing to media server',
}
'''Human-readable label for each phase, suitable for display.'''

UPDATE_LIBRARY_PHASES: list[str] = [
    Phase.PROCESS,
    Phase.RECORD_COLLECTION,
    Phase.BUILD_MAPPINGS,
    Phase.SYNC,
]
'''Phases of `music.update_library`, in execution order.'''

def label(phase: str) -> str:
    '''Returns the display label for the given phase, defaulting to the phase name.'''
    return LABELS.get(phase, phase)

# endregion

# region Events

@dataclass(frozen=True)
class PhaseStarted:
    '''A phase has begun.

    Args:
        phase: Phase identifier, one of the `Phase` constants
        detail: Context for the phase start, e.g. the source path
    '''
    phase: str
    detail: str = ''

@dataclass(frozen=True)
class ItemProgress:
    '''Progress within a phase that processes a known number of items.

    Args:
        phase: Phase identifier, one of the `Phase` constants
        index: Count of items completed so far
        total: Total item count for the phase
        detail: Context for the current position, e.g. the active date context
    '''
    phase: str
    index: int
    total: int
    detail: str = ''

    @property
    def fraction(self) -> float:
        '''Completed portion of the phase, in the range 0.0 to 1.0.'''
        if self.total > 0:
            return min(max(self.index / self.total, 0.0), 1.0)
        return 0.0

@dataclass(frozen=True)
class PhaseCompleted:
    '''A phase has finished.

    Args:
        phase: Phase identifier, one of the `Phase` constants
        summary: Outcome of the phase, e.g. counts of the work performed
    '''
    phase: str
    summary: str = ''

Event = Union[PhaseStarted, ItemProgress, PhaseCompleted]
'''Any event an operation emits.'''

Handler = Callable[[Event], None]
'''A subscriber that receives emitted events.'''

# endregion

# region Bus

class EventBus:
    '''Delivers events to subscribed handlers in subscription order.

    Handlers are held with strong references for the lifetime of the bus, so short-lived
    callables such as lambdas and bound methods stay subscribed. An exception raised by a
    handler is logged and the remaining handlers still receive the event, keeping the
    emitting operation independent of its subscribers.
    '''

    def __init__(self) -> None:
        self.handlers: list[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        '''Registers a handler to receive subsequent events.'''
        self.handlers.append(handler)

    def emit(self, event: Event) -> None:
        '''Delivers the event to every subscribed handler.'''
        for handler in self.handlers:
            try:
                handler(event)
            except Exception as e:
                logging.warning(f"event handler raised for {event}: {e}", exc_info=True)

def emit(bus: 'EventBus | None', event: Event) -> None:
    '''Emits the event when a bus is present, so callers may treat progress reporting as optional.'''
    if bus is not None:
        bus.emit(event)

# endregion
