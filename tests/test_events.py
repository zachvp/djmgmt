import unittest

from djmgmt import events
from djmgmt.events import Event, EventBus, ItemProgress, Phase, PhaseCompleted, PhaseStarted
from tests.fixtures import EventRecorder


class TestEventBus(unittest.TestCase):
    def test_delivery_order(self) -> None:
        '''Tests that handlers receive every event in subscription order.'''
        first: list[Event] = []
        second: list[Event] = []
        order: list[str] = []

        def handle_first(event: Event) -> None:
            first.append(event)
            order.append('first')

        def handle_second(event: Event) -> None:
            second.append(event)
            order.append('second')

        bus = EventBus()
        bus.subscribe(handle_first)
        bus.subscribe(handle_second)

        started = PhaseStarted(Phase.SYNC, 'detail')
        completed = PhaseCompleted(Phase.SYNC, 'summary')
        bus.emit(started)
        bus.emit(completed)

        self.assertListEqual(first, [started, completed])
        self.assertListEqual(second, [started, completed])
        self.assertListEqual(order, ['first', 'second', 'first', 'second'])

    def test_handler_error_isolation(self) -> None:
        '''Tests that a raising handler leaves delivery to the remaining handlers intact.'''
        received: list[Event] = []

        def raising(event: Event) -> None:
            raise ValueError('handler failure')

        bus = EventBus()
        bus.subscribe(raising)
        bus.subscribe(received.append)

        event = PhaseStarted(Phase.PROCESS)
        with self.assertLogs(level='WARNING'):
            bus.emit(event)

        self.assertListEqual(received, [event])

    def test_emit_optional_bus(self) -> None:
        '''Tests that the module-level emit accepts an absent bus, so reporting stays optional.'''
        recorder = EventRecorder()

        event = PhaseCompleted(Phase.PROCESS, 'summary')
        events.emit(None, event)
        events.emit(recorder.bus, event)

        self.assertListEqual(recorder.events, [event])


class TestItemProgress(unittest.TestCase):
    def test_fraction(self) -> None:
        '''Tests that the completed portion covers the full range of item counts.'''
        self.assertEqual(ItemProgress(Phase.SYNC, 0, 4).fraction, 0.0)
        self.assertEqual(ItemProgress(Phase.SYNC, 1, 4).fraction, 0.25)
        self.assertEqual(ItemProgress(Phase.SYNC, 4, 4).fraction, 1.0)

    def test_fraction_bounds(self) -> None:
        '''Tests that the completed portion stays within 0.0 and 1.0 for edge case counts.'''
        self.assertEqual(ItemProgress(Phase.SYNC, 0, 0).fraction, 0.0)
        self.assertEqual(ItemProgress(Phase.SYNC, 5, 4).fraction, 1.0)


class TestLabel(unittest.TestCase):
    def test_known_phase(self) -> None:
        '''Tests that a known phase maps to its display label.'''
        self.assertEqual(events.label(Phase.SYNC), events.LABELS[Phase.SYNC])

    def test_unknown_phase(self) -> None:
        '''Tests that an unmapped phase displays as its own name.'''
        self.assertEqual(events.label('custom_phase'), 'custom_phase')


if __name__ == '__main__':
    unittest.main()
