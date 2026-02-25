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

# Rekordbox
ATTR_DATE_ADDED     = 'DateAdded'
ATTR_LOCATION       = 'Location'
ATTR_TITLE          = 'Name'
ATTR_ARTIST         = 'Artist'
ATTR_ALBUM          = 'Album'
ATTR_GENRE          = 'Genre'
ATTR_KEY            = 'Tonality'
ATTR_TRACK_KEY      = 'Key'
ATTR_TRACK_ID       = 'TrackID'
ATTR_TOTAL_TIME     = 'TotalTime'
ATTR_AVG_BPM        = 'AverageBpm'
ATTR_TYPE           = 'Type'

# Characters that Rekordbox stores literally (unencoded) in Location URLs.
# Derived from analysis of 3,518 tracks in mac-collection-02-15-2026.xml.
# Note: RFC 3986 unreserved chars (A-Za-z0-9-._~) are always safe by default.
URL_SAFE_CHARS = '()/#$!+,=?'
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
