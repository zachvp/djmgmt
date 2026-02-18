'''
Shared test fixtures for the djmgmt test suite.

Import specific names into each test file rather than using wildcard imports.
'''

# Common mock paths shared across multiple test files
MOCK_INPUT_DIR  = '/mock/input'
MOCK_OUTPUT_DIR = '/mock/output'

# XML fixture: single TRACK node used in library tests
TRACK_XML = '''
    <TRACK
        TrackID="1"
        Name="Test Track"
        Artist="MOCK_ARTIST"
        Album="MOCK_ALBUM"
        DateAdded="2020-02-03"
        Location="file://localhost/Users/user/Music/DJ/MOCK_FILE.aiff">
    </TRACK>
'''.strip()

# XML fixture: minimal COLLECTION wrapping one TRACK
COLLECTION_XML = f'''
    <?xml version="1.0" encoding="UTF-8"?>
    <COLLECTION Entries="1">
    {TRACK_XML}
    </COLLECTION>
'''.strip()

# XML fixture: empty DJ_PLAYLISTS document used as a template base
XML_BASE = f'''
<?xml version="1.0" encoding="UTF-8"?>

<DJ_PLAYLISTS Version="1.0.0">
    <PRODUCT Name="rekordbox" Version="6.8.5" Company="AlphaTheta"/>
    <COLLECTION Entries="0">

    </COLLECTION>
    <PLAYLISTS>
        <NODE Type="0" Name="ROOT" Count="2">
            <NODE Name="CUE Analysis Playlist" Type="1" KeyType="0" Entries="0"/>
            <NODE Name="_pruned" Type="1" KeyType="0" Entries="0"/>
        </NODE>
    </PLAYLISTS>
</DJ_PLAYLISTS>
'''.strip()


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