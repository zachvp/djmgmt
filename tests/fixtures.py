'''
Shared test fixtures for the djmgmt test suite.

Import specific names into each test file rather than using wildcard imports.
'''

from djmgmt.events import Event, EventBus, ItemProgress, PhaseCompleted, PhaseStarted

# Common mock paths shared across multiple test files
MOCK_INPUT_DIR  = '/mock/input'
MOCK_OUTPUT_DIR = '/mock/output'


class EventRecorder:
    '''Collects the events an operation emits, for assertions on progress reporting.

    Subscribes to its own bus, so a test passes `recorder.bus` to the operation under test
    and then queries the recorded events by kind.

    Example:
        recorder = EventRecorder()
        music.update_library(..., bus=recorder.bus)
        assert recorder.completed_phases() == [Phase.PROCESS, Phase.SYNC]
    '''

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.bus = EventBus()
        self.bus.subscribe(self.events.append)

    def started(self) -> list[PhaseStarted]:
        '''Returns the phase start events, in emission order.'''
        return [e for e in self.events if isinstance(e, PhaseStarted)]

    def completed(self) -> list[PhaseCompleted]:
        '''Returns the phase completion events, in emission order.'''
        return [e for e in self.events if isinstance(e, PhaseCompleted)]

    def progress(self, phase: str | None = None) -> list[ItemProgress]:
        '''Returns the item progress events, limited to the given phase when one is supplied.'''
        items = [e for e in self.events if isinstance(e, ItemProgress)]
        if phase is not None:
            items = [e for e in items if e.phase == phase]
        return items

    def sequence(self) -> list[tuple[type, str]]:
        '''Returns each event as an (event type, phase) pair, for asserting the full emission order.'''
        return [(type(e), e.phase) for e in self.events]

    def started_phases(self) -> list[str]:
        '''Returns the phases that reported a start, in order.'''
        return [e.phase for e in self.started()]

    def completed_phases(self) -> list[str]:
        '''Returns the phases that reported completion, in order.'''
        return [e.phase for e in self.completed()]

def _create_track_xml(index: int) -> str:
    '''Creates a TRACK XML element string with indexed attributes.'''
    return f'''
        <TRACK
            TrackID="{index}"
            Name="Test Track {index}"
            Artist="MOCK_ARTIST_{index}"
            Album="MOCK_ALBUM_{index}"
            DateAdded="2020-02-03"
            Location="file://localhost/Users/user/Music/DJ/MOCK_FILE_{index}.aiff">
        </TRACK>
    '''.strip()


def _build_collection_xml(tracks: list[str]) -> str:
    '''Builds a COLLECTION XML string wrapping the given track XML strings.'''
    track_content = '\n    '.join(tracks)
    return f'<COLLECTION Entries="{len(tracks)}">\n    {track_content}\n</COLLECTION>'


def _build_dj_playlists_xml(tracks: list[str], pruned_keys: list[str]) -> str:
    '''Builds a DJ_PLAYLISTS XML string with PRODUCT, COLLECTION,
    and PLAYLISTS/ROOT/CUE Analysis/_pruned structure.
    '''
    track_content  = '\n'.join(tracks)
    pruned_content = '\n'.join(f'<TRACK Key="{k}"/>' for k in pruned_keys)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
                <DJ_PLAYLISTS Version="1.0.0">
                    <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
                    <COLLECTION Entries="{len(tracks)}">
                        {track_content}
                    </COLLECTION>
                    <PLAYLISTS>
                        <NODE Type="0" Name="ROOT" Count="2">
                            <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
                            <NODE Name="_pruned" Type="1" KeyType="0" Entries="{len(pruned_keys)}">
                                {pruned_content}
                            </NODE>
                        </NODE>
                    </PLAYLISTS>
                </DJ_PLAYLISTS>'''.strip()


# XML fixture: empty DJ_PLAYLISTS document used as a template base
XML_BASE = _build_dj_playlists_xml([], [])

# XML fixture: single TRACK node used in library tests
TRACK_XML = _create_track_xml(1)

# XML fixture: minimal COLLECTION wrapping one TRACK
COLLECTION_XML = _build_collection_xml([_create_track_xml(1)])

# XML fixture: empty COLLECTION element
COLLECTION_XML_EMPTY = _build_collection_xml([])
