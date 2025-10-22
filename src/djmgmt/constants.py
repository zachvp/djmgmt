# project data
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent

# placeholders for missing file metadata
UNKNOWN_ARTIST = 'UNKNOWN_ARTIST'
UNKNOWN_ALBUM = 'UNKNOWN_ALBUM'

# mappings
MAPPING_MONTH = {
    1  : 'january',
    2  : 'february',
    3  : 'march',
    4  : 'april',
    5  : 'may',
    6  : 'june',
    7  : 'july',
    8  : 'august',
    9  : 'september',
    10 : 'october',
    11 : 'november',
    12 : 'december',
}

# delimiters
FILE_OPERATION_DELIMITER = '->'

# corevega server
COREVEGA_HOST = 'corevega.local'
COREVEGA_USER = 'zachvp'

RSYNC_PORT = '12000'
RSYNC_PROTOCOL = 'rsync://'
RSYNC_MODULE_NAVIDROME = 'navidrome'
RSYNC_URL = f"{RSYNC_PROTOCOL}{COREVEGA_USER}@{COREVEGA_HOST}:{RSYNC_PORT}"

# Rekordbox
ATTR_DATE_ADDED = 'DateAdded'
ATTR_PATH       = 'Location'
ATTR_TITLE      = 'Name'
ATTR_ARTIST     = 'Artist'
ATTR_ALBUM      = 'Album'
ATTR_GENRE      = 'Genre'
ATTR_KEY        = 'Tonality'
ATTR_TRACK_KEY  = 'Key'
ATTR_TRACK_ID   = 'TrackID'
ATTR_TOTAL_TIME = 'TotalTime'
ATTR_AVG_BPM    = 'AverageBpm'
ATTR_TYPE       = 'Type'

REKORDBOX_ROOT   = 'file://localhost'
XPATH_COLLECTION = './/COLLECTION'

## xml references
TAG_TRACK = 'TRACK'
TAG_NODE  = 'NODE'

_playlist_node = lambda x: f'./PLAYLISTS//NODE[@Name="{x}"]'
XPATH_PLAYLISTS  = _playlist_node('ROOT')
XPATH_PRUNED     = _playlist_node('_pruned')
XPATH_MIXTAPES   = _playlist_node('mixtapes')
XPATH_ARCHIVE    = _playlist_node('archive')
XPATH_UNPLAYED   = _playlist_node('unplayed')
XPATH_PLAYED     = _playlist_node('played')

# file information
EXTENSIONS = {'.mp3', '.wav', '.aif', '.aiff', '.flac'}

# state paths
COLLECTION_PATH          = os.path.join(PROJECT_ROOT, 'state', 'processed-collection.xml')
DYNAMIC_COLLECTION_PATH  = os.path.join(PROJECT_ROOT, 'state', 'dynamic-collection.xml')
COLLECTION_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, 'state', 'collection-template.xml')
MISSING_ART_PATH         = os.path.join(PROJECT_ROOT, 'state', 'missing-art.txt')

print(PROJECT_ROOT)