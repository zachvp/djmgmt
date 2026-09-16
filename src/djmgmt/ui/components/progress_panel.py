'''Live progress display driven by operation events.'''

from dataclasses import dataclass

import streamlit as st

from djmgmt import events
from djmgmt.events import Event, EventBus, ItemProgress, PhaseCompleted, PhaseStarted


@dataclass
class StageState:
    '''Display state of one phase in the panel's stage checklist.'''
    phase: str
    status: str = 'pending'
    text: str = ''


class ProgressPanel:
    '''Renders operation progress from an `EventBus` into an expandable status container.

    Subscribes to the bus and updates in place as events arrive. The panel lists every stage
    of the operation as a checklist, so the whole pipeline is visible at once: stages still to
    run, the active stage with its detail, and finished stages with their summaries. The status
    label tracks the active phase, and a progress bar tracks item counts within a phase.

    Because the operation runs on the Streamlit script thread, each event repaints the panel
    as it is emitted.

    Example:
        panel = ProgressPanel('Updating library', stages=events.UPDATE_LIBRARY_PHASES)
        music.update_library(..., bus=panel.bus)
        panel.complete('Library updated')
    '''

    PENDING  = 'pending'
    ACTIVE   = 'active'
    COMPLETE = 'complete'
    FAILED   = 'failed'

    ICONS = {
        PENDING:  '○',
        ACTIVE:   '⏳',
        COMPLETE: '✓',
        FAILED:   '✗',
    }

    def __init__(self, title: str, stages: list[str] | None = None, expanded: bool = True):
        '''Creates the status container and an event bus wired to this panel.

        Args:
            title: Initial status label, shown until the first phase begins
            stages: Phases the operation runs, in order, listed as pending from the start.
                A phase emitted outside this list joins the checklist when it first appears.
            expanded: Whether the status container starts expanded
        '''
        self.title = title
        self.stages: list[StageState] = [StageState(phase) for phase in stages or []]
        self.status = st.status(title, expanded=expanded)
        with self.status:
            self.feed = st.empty()
            self.bar = st.empty()

        self.bus = EventBus()
        self.bus.subscribe(self.handle)
        self.render()

    def stage(self, phase: str) -> StageState:
        '''Returns the checklist entry for the phase, appending one for a phase not yet listed.'''
        for stage in self.stages:
            if stage.phase == phase:
                return stage
        stage = StageState(phase)
        self.stages.append(stage)
        return stage

    def render(self) -> None:
        '''Repaints the stage checklist.'''
        if not self.stages:
            self.feed.empty()
            return
        lines = []
        for stage in self.stages:
            line = f"{self.ICONS[stage.status]} **{events.label(stage.phase)}**"
            if stage.text:
                line = f"{line}: {stage.text}"
            lines.append(line)
        self.feed.markdown('\n\n'.join(lines))

    def handle(self, event: Event) -> None:
        '''Applies a single event to the display.'''
        if isinstance(event, PhaseStarted):
            label = events.label(event.phase)
            self.status.update(label=f"{label}{f' — {event.detail}' if event.detail else ''}")
            stage = self.stage(event.phase)
            stage.status, stage.text = self.ACTIVE, event.detail
            self.bar.empty()
            self.render()
        elif isinstance(event, ItemProgress):
            text = f"{event.index} of {event.total}"
            if event.detail:
                text = f"{text} — {event.detail}"
            self.bar.progress(event.fraction, text=text)
        elif isinstance(event, PhaseCompleted):
            stage = self.stage(event.phase)
            stage.status, stage.text = self.COMPLETE, event.summary
            self.bar.empty()
            self.render()

    def complete(self, label: str) -> None:
        '''Marks the operation as finished successfully, keeping the stage checklist visible.'''
        self.bar.empty()
        self.status.update(label=label, state='complete', expanded=True)

    def fail(self, label: str) -> None:
        '''Marks the operation as finished with an error, flagging the stage that was running.'''
        for stage in self.stages:
            if stage.status == self.ACTIVE:
                stage.status = self.FAILED
        self.render()
        self.bar.empty()
        self.status.update(label=label, state='error', expanded=True)
