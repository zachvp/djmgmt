'''Live progress display driven by operation events.'''

import streamlit as st

from djmgmt import events
from djmgmt.events import Event, EventBus, ItemProgress, PhaseCompleted, PhaseStarted


class ProgressPanel:
    '''Renders operation progress from an `EventBus` into an expandable status container.

    Subscribes to the bus and updates in place as events arrive: the status label tracks the
    active phase, a progress bar tracks item counts within a phase, and completed phases
    accumulate in a feed with their summaries.

    Because the operation runs on the Streamlit script thread, each event repaints the panel
    as it is emitted.

    Example:
        panel = ProgressPanel('Updating library')
        music.update_library(..., bus=panel.bus)
        panel.complete('Library updated')
    '''

    ICON_ACTIVE   = '⏳'
    ICON_COMPLETE = '✓'

    def __init__(self, title: str, expanded: bool = True):
        '''Creates the status container and an event bus wired to this panel.

        Args:
            title: Initial status label, shown until the first phase begins
            expanded: Whether the status container starts expanded
        '''
        self.title = title
        self.completed: list[str] = []
        self.status = st.status(title, expanded=expanded)
        with self.status:
            self.feed = st.empty()
            self.bar = st.empty()

        self.bus = EventBus()
        self.bus.subscribe(self.handle)

    def handle(self, event: Event) -> None:
        '''Applies a single event to the display.'''
        if isinstance(event, PhaseStarted):
            label = events.label(event.phase)
            self.status.update(label=f"{label}{f' — {event.detail}' if event.detail else ''}")
            self.bar.empty()
        elif isinstance(event, ItemProgress):
            text = f"{event.index} of {event.total}"
            if event.detail:
                text = f"{text} — {event.detail}"
            self.bar.progress(event.fraction, text=text)
        elif isinstance(event, PhaseCompleted):
            label = events.label(event.phase)
            self.completed.append(f"{self.ICON_COMPLETE} **{label}**{f': {event.summary}' if event.summary else ''}")
            self.feed.markdown('\n\n'.join(self.completed))
            self.bar.empty()

    def complete(self, label: str) -> None:
        '''Marks the operation as finished successfully.'''
        self.bar.empty()
        self.status.update(label=label, state='complete', expanded=False)

    def fail(self, label: str) -> None:
        '''Marks the operation as finished with an error, keeping the phase feed visible.'''
        self.bar.empty()
        self.status.update(label=label, state='error', expanded=True)
