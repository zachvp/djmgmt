'''Tests for the UI progress panel, driven through Streamlit's app test harness.

The harness runs a script in-process and exposes the rendered elements, so these tests assert
what the panel actually displays for a given event sequence.

The harness re-executes the script function's source in its own namespace, so each script
function below stands alone: it imports what it uses and receives everything else as kwargs.
'''

import unittest
from importlib.util import find_spec
from typing import Any

from djmgmt import events
from djmgmt.events import Event, ItemProgress, Phase, PhaseCompleted, PhaseStarted

HAS_STREAMLIT = find_spec('streamlit') is not None

ICONS = {'pending': '○', 'active': '⏳', 'complete': '✓', 'failed': '✗'}

TITLE = 'Updating library'
LABEL_COMPLETE = 'Updated library'
LABEL_FAIL     = 'Library update failed'
FINISH_COMPLETE = 'complete'
FINISH_FAIL     = 'fail'


def _panel_script(title: 'str', stages: 'list[str]', events_to_emit: 'list[Event]', finish: 'str',
                  complete_label: 'str', fail_label: 'str') -> None:
    '''Renders a panel, emits the given events, and optionally closes it out.

    Runs as the script body under the Streamlit app test harness.
    '''
    from djmgmt.ui.components.progress_panel import ProgressPanel

    panel = ProgressPanel(title, stages=stages)
    for event in events_to_emit:
        panel.bus.emit(event)
    if finish == 'complete':
        panel.complete(complete_label)
    elif finish == 'fail':
        panel.fail(fail_label)


def _raising_subscriber_script(title: 'str', event: 'Event') -> None:
    '''Renders a panel alongside a subscriber that raises, then emits a single event.'''
    from djmgmt.ui.components.progress_panel import ProgressPanel

    def raising(_: 'Event') -> None:
        raise ValueError('subscriber failure')

    panel = ProgressPanel(title)
    panel.bus.subscribe(raising)
    panel.bus.emit(event)


@unittest.skipUnless(HAS_STREAMLIT, 'streamlit is available for UI rendering tests')
class TestProgressPanel(unittest.TestCase):
    def render(self, events_to_emit: list[Event], finish: str = '', stages: list[str] | None = None) -> Any:
        '''Runs the panel script under the app test harness and returns the finished app.'''
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_function(
            _panel_script,
            default_timeout=30,
            kwargs={
                'title': TITLE,
                'stages': stages or [],
                'events_to_emit': events_to_emit,
                'finish': finish,
                'complete_label': LABEL_COMPLETE,
                'fail_label': LABEL_FAIL,
            },
        ).run()
        self.assertFalse(app.exception, f"panel raised while rendering: {app.exception}")
        return app

    def test_initial_title(self) -> None:
        '''Tests that the panel opens with the caller's title.'''
        app = self.render([])
        self.assertEqual(app.status[0].label, TITLE)

    def test_phase_start_sets_label(self) -> None:
        '''Tests that a starting phase becomes the status label, with its detail.'''
        app = self.render([PhaseStarted(Phase.PROCESS, '/downloads')])
        self.assertEqual(app.status[0].label, f"{events.label(Phase.PROCESS)} — /downloads")

    def test_phase_start_without_detail(self) -> None:
        '''Tests that a phase carrying no detail displays its label alone.'''
        app = self.render([PhaseStarted(Phase.SYNC)])
        self.assertEqual(app.status[0].label, events.label(Phase.SYNC))

    def test_completed_phases_accumulate(self) -> None:
        '''Tests that finished phases build a feed, in order, with their summaries.'''
        app = self.render([
            PhaseCompleted(Phase.PROCESS, 'processed 12 files'),
            PhaseCompleted(Phase.RECORD_COLLECTION, 'recorded 12 tracks'),
        ])

        feed = app.markdown[0].value
        self.assertIn(events.label(Phase.PROCESS), feed)
        self.assertIn('processed 12 files', feed)
        self.assertIn(events.label(Phase.RECORD_COLLECTION), feed)
        self.assertIn('recorded 12 tracks', feed)
        self.assertLess(feed.index('processed 12 files'), feed.index('recorded 12 tracks'))

    def test_stages_listed_pending(self) -> None:
        '''Tests that every stage appears as pending before any event arrives, in order.'''
        app = self.render([], stages=events.UPDATE_LIBRARY_PHASES)

        feed = app.markdown[0].value
        positions = [feed.index(f"{ICONS['pending']} **{events.label(phase)}**") for phase in events.UPDATE_LIBRARY_PHASES]
        self.assertListEqual(positions, sorted(positions))

    def test_stage_statuses_track_events(self) -> None:
        '''Tests that finished, active, and upcoming stages display side by side.'''
        app = self.render([
            PhaseStarted(Phase.PROCESS, '/downloads'),
            PhaseCompleted(Phase.PROCESS, 'processed 0 files'),
            PhaseStarted(Phase.RECORD_COLLECTION),
            PhaseCompleted(Phase.RECORD_COLLECTION, '40 new tracks, 3521 updated tracks'),
            PhaseStarted(Phase.BUILD_MAPPINGS),
            PhaseCompleted(Phase.BUILD_MAPPINGS, 'built 121 mappings'),
            PhaseStarted(Phase.SYNC, '121 mappings'),
        ], stages=events.UPDATE_LIBRARY_PHASES)

        feed = app.markdown[0].value
        self.assertIn(f"{ICONS['complete']} **{events.label(Phase.PROCESS)}**: processed 0 files", feed)
        self.assertIn(f"{ICONS['complete']} **{events.label(Phase.RECORD_COLLECTION)}**: 40 new tracks, 3521 updated tracks", feed)
        self.assertIn(f"{ICONS['active']} **{events.label(Phase.SYNC)}**: 121 mappings", feed)

    def test_fail_marks_active_stage(self) -> None:
        '''Tests that a failure flags the running stage and leaves later stages pending.'''
        app = self.render([
            PhaseCompleted(Phase.PROCESS, 'processed 12 files'),
            PhaseStarted(Phase.RECORD_COLLECTION),
        ], finish=FINISH_FAIL, stages=events.UPDATE_LIBRARY_PHASES)

        feed = app.markdown[0].value
        self.assertIn(f"{ICONS['failed']} **{events.label(Phase.RECORD_COLLECTION)}**", feed)
        self.assertIn(f"{ICONS['pending']} **{events.label(Phase.SYNC)}**", feed)

    def test_item_progress_renders_bar(self) -> None:
        '''Tests that item progress renders a bar at the completed portion of the phase.'''
        app = self.render([
            PhaseStarted(Phase.SYNC, '40 mappings'),
            ItemProgress(Phase.SYNC, 10, 40, '2025/05 may/20'),
        ])

        bars = app.get('progress')
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].value, 25)

    def test_progress_clears_on_phase_completion(self) -> None:
        '''Tests that a finished phase clears its bar, leaving the next phase to open a fresh one.'''
        app = self.render([
            PhaseStarted(Phase.SYNC, '40 mappings'),
            ItemProgress(Phase.SYNC, 10, 40),
            PhaseCompleted(Phase.SYNC, 'synced 2 batches'),
        ])

        self.assertEqual(len(app.get('progress')), 0)
        self.assertIn('synced 2 batches', app.markdown[0].value)

    def test_complete_closes_panel(self) -> None:
        '''Tests that completion marks the status complete with the final label.'''
        app = self.render([PhaseCompleted(Phase.PROCESS, 'processed 12 files')], finish=FINISH_COMPLETE)

        self.assertEqual(app.status[0].label, LABEL_COMPLETE)
        self.assertEqual(app.status[0].state, 'complete')

    def test_fail_retains_phase_feed(self) -> None:
        '''Tests that a failure marks the status as an error while the finished phases stay visible.'''
        app = self.render([
            PhaseCompleted(Phase.PROCESS, 'processed 12 files'),
            PhaseStarted(Phase.SYNC, '40 mappings'),
        ], finish=FINISH_FAIL)

        self.assertEqual(app.status[0].label, LABEL_FAIL)
        self.assertEqual(app.status[0].state, 'error')
        self.assertIn('processed 12 files', app.markdown[0].value)

    def test_subscriber_error_isolation(self) -> None:
        '''Tests that a failing subscriber leaves the panel rendering the remaining events.'''
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_function(
            _raising_subscriber_script,
            default_timeout=30,
            kwargs={'title': TITLE, 'event': PhaseCompleted(Phase.PROCESS, 'processed 12 files')},
        ).run()

        self.assertFalse(app.exception, f"panel raised while rendering: {app.exception}")
        self.assertIn('processed 12 files', app.markdown[0].value)


if __name__ == '__main__':
    unittest.main()
