# extract info from rekordbox playlist export

'''
Format
    Tab-separated
    Fields depend on rekordbox view settings, here is an example line format
        "#   Track Title BPM Artist  Genre   Date Added  Time    Key DJ Play Count"
'''

import argparse
import os
import csv
import re
import logging
import xml.etree.ElementTree as ET
from typing import Callable
from dataclasses import dataclass, fields, asdict

from . import common
from . import library


# data
@dataclass
class Mix:
    '''Represents a DJ mix with all associated file paths and metadata.'''
    date_recorded: str              # ISO date (YYYY-MM-DD)
    original_file_path: str                 # Path to original WAV recording
    playlist_file_path: str         # Path to Rekordbox playlist TSV export
    soundcloud_url: str = ''        # Full Soundcloud track URL
    title: str = ''                 # Human-readable mix title
    cover_image_path: str = ''      # Path to local cover image
    transcoded_file_path: str = ''  # Path to MP3 in output directory

# constants
# CSV file for structured mix data
MIXES_CSV_FILE_PATH = '/Users/zachvp/Music/mixtapes/mixes.csv'

# CSV column headers (must match Mix dataclass field order)
MIXES_CSV_HEADERS = [f.name for f in fields(Mix)]

WINDOWS_MIX = 'WindowsMix'

# command support
class Namespace(argparse.Namespace):
    # required
    function: str

    # optional (alphabetical)
    artist: bool
    cover_image_path: str
    csv_file_path: str
    genre: bool
    music_file_path: str
    number: bool
    playlist_file_path: str
    soundcloud_url: str
    title: bool
    transcoded_file_path: str
    
    # function constants
    FUNCTION_EXTRACT_PLAYLIST = 'extract'
    FUNCTION_PRESS_MIXTAPE = 'press'
    
    FUNCTIONS = {FUNCTION_EXTRACT_PLAYLIST, FUNCTION_PRESS_MIXTAPE}

def parse_args(valid_functions: set[str], argv: list[str]) -> Namespace:
    parser = argparse.ArgumentParser(description="Output each track from a rekordbox-exported playlist.\
        If no options are provided, all fields will exist in the ouptut.")
    # Required: function only
    parser.add_argument('function', type=str,
                       help=f"Function to run. One of: {', '.join(sorted(valid_functions))}")
    
    # Optional: all function parameters (alphabetical)
    parser.add_argument('--artist', '-a', action='store_true',
                        help='Include the artist in the extract output.')
    parser.add_argument('--cover-image-path', '-c', type=str,
                       help='The path to the mix cover image.')
    parser.add_argument('--csv-file-path', '-d', type=str,
                       help='The path to CSV file.')
    parser.add_argument('--genre', '-g', action='store_true',
                        help='Include the genre in the output.')
    parser.add_argument('--music-file-path', '-m', type=str,
                       help='The path to the mix music file.')
    parser.add_argument('--number', '-n', action='store_true',
                        help='Include the track number in the extract output.')
    parser.add_argument('--playlist-file-path', '-p', type=str,
                       help='The path to the mix playlist file.')
    parser.add_argument('--soundcloud-url', '-s', type=str,
                       help='The mix Soundcloud URL.')
    parser.add_argument('--title', '-t', action='store_true',
                        help='Include the title in the extract output.')
    parser.add_argument('--transcoded-file-path', '-x', type=str,
                       help='The transcoded mix file path.')

    args = parser.parse_args(argv, namespace=Namespace())
    
    # Normalize paths (only if not None)
    common.normalize_arg_paths(args, ['cover_image_path',
                                      'csv_file_path',
                                      'music_file_path',
                                      'playlist_file_path',
                                      'transcoded_file_path'])

    # validate function
    if args.function not in valid_functions:
        parser.error(f"invalid function '{args.function}'\n"
                     f"expect one of: {', '.join(sorted(valid_functions))}")

    # function-specific validation
    _validate_function_args(parser, args)

    return args

def _validate_function_args(parser: argparse.ArgumentParser, args: Namespace) -> None:
    '''Validate function-specific required arguments.'''
    
    # required for all functions
    if not args.playlist_file_path:
        parser.error(f"'{args.function}' requires --playlist-file-path")
    
    # mix press requires specific args
    if args.function == Namespace.FUNCTION_PRESS_MIXTAPE:
        if not args.music_file_path:
            parser.error(f"'{args.function}' requires --music-file-path")
        if not args.playlist_file_path:
            parser.error(f"'{args.function}' requires --playlist-file-path")

# helpers
def extract_tsv(path: str, fields: list[int]) -> list[str]:
    output = []

    with open(path, 'r', encoding=common.get_encoding(path)) as file:
        rows = file.readlines()
        for row in rows:
            line = row.split('\t')
            output_line = ''
            for f in fields:
                output_line += f"{line[f]}\t"
            output_line = output_line.strip()
            if len(output_line) > 0:
                output.append(output_line)
    return output

def extract_csv(path: str, fields: list[int]) -> list[str]:
    output = []

    with open(path, 'r', encoding=common.get_encoding(path)) as file:
        rows = csv.reader(file)
        for row in rows:
            output_line = ''
            for f in fields:
                output_line += f"{row[f]}\t"
            output_line = output_line.strip()
            if len(output_line) > 0:
                output.append(output_line)
    return output

def find_column(path: str, name: str) -> int:
    '''Locate the index of a column by name in a file's header row.

    Args:
        path: Path to the file to read.
        name: Name of the column to find.
    '''
    # Helper functionality and data
    normalize: Callable[[str], str] = lambda s: s.replace(' ', '_')
    headers = {
        '#',
        'Track Title',
        'Genre',
        'Artist',
        'Key',
        'BPM',
        'Time',
        'Date Added',
        'DJ Play Count'
    }
    options = { header : normalize(header) for header in headers }
    columns_processed = []
    
    # Primary search loop
    with open(path, 'r', encoding=common.get_encoding(path)) as file:
        # Core mutable data
        columns = file.readline().split()
        multiword = ''
        
        # Process columns to handle multi-word header names
        for c in columns:
            if c in options:
                columns_processed.append(options[c])
                multiword = ''
            else: 
                multiword += f"{c} "
                if multiword.strip() in options:
                    columns_processed.append(options[multiword.strip()])
                    multiword = ''
    
    # Check for the search column
    search_column = normalize(name)
    try:
        return columns_processed.index(search_column)
    except ValueError:
        print(f"error: unable to find name: '{name}' in path '{path}'")
    return -1

def extract_date_from_filename(filepath: str) -> str | None:
    '''
    Extract recording date from filename.

    Matches patterns like "REC-2022-06-08" in filenames.

    Args:
        filepath: Path to audio file

    Returns:
        ISO date string (YYYY-MM-DD) or None if not found
    '''
    filename = os.path.splitext(os.path.basename(filepath))[0]
    match = re.search(r'REC-(\d{4}-\d{2}-\d{2})', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def load_mixes_csv(csv_file_path: str=MIXES_CSV_FILE_PATH) -> list[Mix]:
    '''
    Load all mixes from CSV file.

    Returns:
        List of Mix objects
    '''
    mixes = []

    if not os.path.exists(csv_file_path):
        return mixes

    try:
        with open(csv_file_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mix = Mix(**row)
                mixes.append(mix)

        logging.info(f"Loaded {len(mixes)} mixes from CSV")
        return mixes
    except Exception as e:
        logging.error(f"Error loading mixes CSV: {e}")
        raise


def save_mix_to_csv(mix: Mix, csv_file_path: str=MIXES_CSV_FILE_PATH) -> None:
    '''
    Append or update a mix entry in the CSV file.

    If a mix with the same soundcloud_url exists, it will be updated.
    Otherwise, the mix will be appended. Uses soundcloud_url as the unique
    identifier since multiple mixes can share the same original_file_path
    (e.g., WindowsMix entries).

    Args:
        mix: Mix object to save
    '''
    # load existing mixes
    mixes = load_mixes_csv(csv_file_path=csv_file_path)
    
    # create file if it doesn't exist
    if not mixes:
        try:
            with open(csv_file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=MIXES_CSV_HEADERS)
                writer.writeheader()
        except Exception as e:
            logging.error(f"Error saving mix to CSV: {e}")
            raise

    # check if mix already exists
    existing_index = None
    for i, existing in enumerate(mixes):
        # try non-windows mix music path
        if existing.original_file_path != WINDOWS_MIX and existing.original_file_path == mix.original_file_path:
            existing_index = i
            break
        # fall back to Soundcloud URL
        if existing.soundcloud_url and existing.soundcloud_url == mix.soundcloud_url:
            existing_index = i
            break

    if existing_index is not None:
        mixes[existing_index] = mix
        logging.info(f"Updated mix: {mix.original_file_path}")
    else:
        mixes.append(mix)
        logging.info(f"Added mix: {mix.original_file_path}")

    # Write all mixes back to CSV
    try:
        with open(csv_file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=MIXES_CSV_HEADERS)
            writer.writeheader()
            for m in mixes:
                writer.writerow(asdict(m))
    except Exception as e:
        logging.error(f"Error saving mix to CSV: {e}")
        raise


# primary functions
def extract(input_path: str,
            include_number: bool,
            include_title: bool,
            include_artist: bool,
            include_genre: bool) -> list[str]:
    '''Extract and format track information from a rekordbox playlist export file.

    Args:
        input_path: Path to the playlist file (TSV, TXT, or CSV format).
        include_number: Include track number in output.
        include_title: Include track title in output.
        include_artist: Include artist in output.
        include_genre: Include genre in output.
    '''
    number = find_column(input_path, '#')
    title  = find_column(input_path, 'Track Title')
    artist = find_column(input_path, 'Artist')
    genre  = find_column(input_path, 'Genre')

    fields: list[int] = []
    if include_number:
        fields.append(number)
    if include_title:
        fields.append(title)
    if include_artist:
        fields.append(artist)
    if include_genre:
        fields.append(genre)

    # if no options are provided, assume all fields for output
    if len(fields) < 1:
        fields = [number, title, artist, genre]

    extension = os.path.splitext(input_path)[1]

    if extension in {'.tsv', '.txt'}:
        extracted = extract_tsv(input_path, fields)
    elif extension == '.csv':
        extracted = extract_csv(input_path, fields)
    else:
        raise ValueError(f"Unsupported extension: {extension}")

    return extracted

def press_mix(music_file_path: str,
              playlist_file_path: str,
              soundcloud_url: str = '',
              cover_image_path: str = '',
              transcoded_file_path: str = '',
              csv_file_path: str = '') -> Mix:
    '''
    Record a new mix entry to the CSV file.

    Extracts the recording date from the filename if possible.

    Args:
        music_file_path: Path to original WAV recording
        playlist_file_path: Path to Rekordbox playlist TSV export
        soundcloud_url: Optional Soundcloud track URL
        cover_image_path: Optional path to local cover image
        transcoded_file_path: Optional path to transcoded MP3
    '''
    from datetime import datetime
    
    # Extract date from filename
    date_recorded = extract_date_from_filename(music_file_path)

    if not date_recorded:
        logging.warning(f"Could not extract date from filename: {music_file_path}")
        # Use today's date as fallback
        date_recorded = datetime.now().strftime('%Y-%m-%d')
        logging.info(f"Using today's date as fallback: {date_recorded}")

    mix = Mix(
        date_recorded=date_recorded,
        original_file_path=music_file_path,
        playlist_file_path=playlist_file_path,
        soundcloud_url=soundcloud_url,
        cover_image_path=cover_image_path,
        transcoded_file_path=transcoded_file_path
    )

    save_mix_to_csv(mix, csv_file_path=csv_file_path)
    return mix

# M3U8 generation for Navidrome sync
def _find_playlist_node(root: ET.Element, playlist_path: str) -> ET.Element | None:
    '''Find a playlist node by hierarchical path (e.g., "dynamic.unplayed").

    Args:
        root: XML root element
        playlist_path: Dot-separated playlist path (e.g., "dynamic.unplayed")

    Returns:
        Playlist NODE element or None if not found
    '''
    # navigate to PLAYLISTS root
    playlists_root = root.find('./PLAYLISTS/NODE[@Name="ROOT"]')
    if playlists_root is None:
        logging.error('Unable to find PLAYLISTS/ROOT in XML')
        return None

    # traverse the playlist path hierarchy
    current = playlists_root
    parts = playlist_path.split('.')

    for part in parts:
        # find child NODE with matching Name attribute
        found = None
        for child in current:
            if child.tag == 'NODE' and child.get('Name') == part:
                found = child
                break

        if found is None:
            logging.error(f"Unable to find playlist node: '{part}' in path '{playlist_path}'")
            return None

        current = found

    return current


def _build_navidrome_path(metadata: library.TrackMetadata, target_base: str) -> str | None:
    '''Build Navidrome path from track metadata using date-structured format.

    Args:
        metadata: TrackMetadata object with track information
        target_base: Base path for Navidrome (e.g., "/media/SOL/music")

    Returns:
        Full Navidrome path or None if path cannot be built
    '''
    from datetime import datetime
    from . import library
    from . import constants

    if not metadata.date_added:
        logging.warning(f"Track '{metadata.title}' missing DateAdded")
        return None

    # build date-based path
    date_path = library.date_path(metadata.date_added, constants.MAPPING_MONTH)

    # determine sanitization method based on when file was organized
    # files organized before 2025-12-01 used no sanitization (filesystem handled special chars)
    # files organized after 2025-12-01 use clean_dirname_fat32
    # Note: using conservative cutoff since DateAdded != organization date
    date_added = datetime.fromisoformat(metadata.date_added)
    sanitization_cutoff = datetime(2025, 12, 1)

    if date_added < sanitization_cutoff:
        # old files: minimal sanitization
        # exFAT allows most chars; slashes create nested directories
        # Remove all colons and strip leading/trailing whitespace
        artist_safe = metadata.artist.replace(':', '').strip()
        album_safe = metadata.album.replace(':', '').strip()

        # handle empty artist/album
        if not artist_safe:
            artist_safe = constants.UNKNOWN_ARTIST
        if not album_safe:
            album_safe = constants.UNKNOWN_ALBUM
    else:
        # new files: use clean_dirname_fat32 sanitization
        artist_safe = common.clean_dirname_fat32(metadata.artist)
        album_safe = common.clean_dirname_fat32(metadata.album)

    # get filename from original path and change extension to .mp3
    filename = os.path.basename(metadata.path)
    name, ext = os.path.splitext(filename)

    # transform extension to mp3 for lossless and AAC formats
    if ext.lower() in {'.aif', '.aiff', '.wav', '.flac', '.m4a'}:
        filename = f"{name}.mp3"

    # construct full Navidrome path
    navidrome_path = f"{target_base}/{date_path}/{artist_safe}/{album_safe}/{filename}"

    return navidrome_path


def generate_m3u8_from_collection(
    collection_path: str,
    playlist_path: str,
    output_path: str,
    target_base: str = '/media/SOL/music'
) -> list[str]:
    '''Generate M3U8 playlist from Rekordbox XML collection for Navidrome.

    Args:
        collection_path: Path to Rekordbox XML collection file
        playlist_path: Dot-separated playlist path (e.g., "dynamic.unplayed")
        output_path: Where to write the M3U8 file
        target_base: Base path for Navidrome Docker container (default: /media/SOL/music)

    Returns:
        List of track paths included in playlist (empty list on error)
    '''
    import xml.etree.ElementTree as ET
    from . import library

    try:
        # parse XML collection
        tree = ET.parse(collection_path)
        root = tree.getroot()

        # find collection and playlist nodes
        collection = root.find('.//COLLECTION')
        if collection is None:
            logging.error('Unable to find COLLECTION in XML')
            return []

        playlist_node = _find_playlist_node(root, playlist_path)
        if playlist_node is None:
            return []

        # extract track IDs from playlist
        track_elements = playlist_node.findall('TRACK')
        track_ids: list[str] = []
        for track in track_elements:
            track_id = track.get('Key')
            if track_id is not None:
                track_ids.append(track_id)
        logging.info(f"Found {len(track_ids)} tracks in playlist '{playlist_path}'")

        # transform each track
        playlist_name = playlist_path.replace('.', '_')
        m3u8_lines = ['#EXTM3U', f"#PLAYLIST:{playlist_name}"]
        track_paths = []
        skipped = 0

        for track_id in track_ids:
            # get track metadata using library function
            metadata = library.extract_track_metadata_by_id(collection, track_id)
            if metadata is None:
                skipped += 1
                continue

            # build Navidrome path
            navidrome_path = _build_navidrome_path(metadata, target_base)
            if navidrome_path is None:
                skipped += 1
                continue

            # add EXTINF metadata line
            m3u8_lines.append(f"#EXTINF:{metadata.total_time},{metadata.artist} - {metadata.title}")
            m3u8_lines.append(navidrome_path)
            track_paths.append(navidrome_path)

        # write M3U8 file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u8_lines))

        logging.info(f"Generated M3U8 with {len(track_paths)} tracks at: {output_path}")
        if skipped > 0:
            logging.warning(f"Skipped {skipped} tracks due to errors")

        return track_paths

    except Exception as e:
        logging.error(f"Error generating M3U8: {e}")
        return []


# main
if __name__ == '__main__':
    import sys
    
    # log config
    common.configure_log_module(__file__)
    
    args = parse_args(Namespace.FUNCTIONS, sys.argv[1:])
    
    if args.function == Namespace.FUNCTION_EXTRACT_PLAYLIST:
        result = extract(args.function, args.number, args.title, args.artist, args.genre)
        print('\n'.join(result))
    elif args.function == Namespace.FUNCTION_PRESS_MIXTAPE:
        press_mix(args.music_file_path,
                  args.playlist_file_path,
                  soundcloud_url=args.soundcloud_url,
                  cover_image_path=args.cover_image_path,
                  transcoded_file_path=args.transcoded_file_path,
                  csv_file_path=args.csv_file_path)
