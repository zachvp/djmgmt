from __future__ import annotations
import mutagen
import logging
import io
import imagehash
from PIL import Image
from typing import Optional

import mutagen.flac
import mutagen.id3

class Tags:
    def __init__(self,
                 artist          : Optional[str]=None,
                 album           : Optional[str]=None,
                 title           : Optional[str]=None,
                 genre           : Optional[str]=None,
                 key             : Optional[str]=None,
                 cover_image     : Optional[Image.Image] = None):
        self.artist = artist
        self.album = album
        self.title = title
        self.genre = genre
        self.key = key
        self.cover_image = cover_image
    
    def __str__(self) -> str:
        output = {
            'artist'      : self.artist,
            'album'       : self.album,
            'title'       : self.title,
            'genre'       : self.genre,
            'key'         : self.key
        }
        return str(output)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Tags):
            return False
        
        # DBG
        if self.artist != other.artist:
            logging.warning('no match: artist')
        if self.album != other.album:
            logging.warning('no match: album')
        if self.title != other.title:
            logging.warning('no match: title')
        if self.genre != other.genre:
            logging.warning('no match: genre')
        if self.key != other.key:
            logging.warning('no match: key')
        if not self._eq_cover_image(other, 5):
            logging.warning('no match: cover image')
        
        return all([self.artist == other.artist,
                    self.album  == other.album,
                    self.title  == other.title,
                    self.genre  == other.genre,
                    self.key    == other.key,
                    self._eq_cover_image(other, 5)])
    
    def __hash__(self) -> int:
        return hash((
            self.artist,
            self.album,
            self.title,
            self.genre,
            self.key,
            self._hash_cover_image()
        ))
    
    def _hash_cover_image(self) -> Optional[imagehash.ImageHash]:
        '''Computes and returns a perceptual hash for the cover image using imagehash.
        Raises a ValueError and logs an error if hash generation fails.
        '''
        # unable to hash None value, so gracefully return
        if self.cover_image is None:
            return None
        
        try:
            # attempt to return the perceptual hash of the cover image
            return imagehash.phash(self.cover_image)
        except Exception as e:
            # handle and log any errors
            logging.error(f"Error generating perceptual hash:\n{e}")
            raise ValueError(f"Error generating perceptual hash: {e}")
    
    def _eq_cover_image(self, other: Tags, threshold: int = 0) -> bool:
        '''Compares the perceptual hash of this instance's cover image to that of another Tags instance.
        Returns True if the images are similar according to the inclusive threshold, else False.
        '''
        try:
            hash_self = self._hash_cover_image()
            hash_other = other._hash_cover_image()
        except ValueError as e:
            # log the hash error
            logging.error(f"Error comparing cover images due to hash generation failure:\n{e}.")
            raise
        
        # handle None hashes: return True if both hashes are None
        if hash_self is None or hash_other is None:
            return hash_self is None and hash_other is None
        
        # compute the difference to judge similarity
        difference = hash_self - hash_other
        return difference <= threshold
    
    def basic_identifier(self) -> str:
        title = self.title if self.title else 'none'
        artist = self.artist if self.artist else 'none'
        
        return f"{artist} - {title}".strip().lower()
    
    @classmethod
    def get_track_key(cls, track: mutagen.FileType, options: set[str]) -> Optional[str]:
        '''Tries to find a key present in the given track based on the given options.'''
        try:
            for o in options:
                if o in track:
                    return o
        except ValueError as error:
            logging.error(f"unable to find key for track: {error}")
            return None

        return None

    @classmethod
    def extract_tag_value(cls, track: mutagen.FileType, tag_keys: set[str]) -> Optional[str]:
        key = cls.get_track_key(track, tag_keys)
        value = None
        if key and track[key]:
            value = track[key]
            value = value[0] if isinstance(value, list) else value
            value = str(value)
        return value

    @classmethod
    def extract_cover_image(cls, track: mutagen.FileType) -> Optional[Image.Image]:
        image: Optional[Image.Image] = None
        data = None
        
        # extract image for files with ID3 tags (MP3, AIFF, WAV)
        for tag in track.tags.values(): # type: ignore
            if isinstance(tag, mutagen.id3.APIC) and tag.type == mutagen.id3.PictureType.COVER_FRONT: # type: ignore
                data = tag.data # type: ignore
        
        # extract image for FLAC files
        if data is None and isinstance(track, mutagen.flac.FLAC):
            if track.pictures:
                for picture in track.pictures:
                    if picture.type == mutagen.id3.PictureType.COVER_FRONT:
                        data = picture.data
        
        # load the image data
        if data:     
            try:
                # attempt image verification, which will raise an exception if it fails
                image = Image.open(io.BytesIO(data))
                image.verify()
                
                # re-open the image to refresh the file pointer to a valid state
                image = Image.open(io.BytesIO(data))
            except Exception as e:
                # image may be invalid, so set to None
                image = None
                logging.warning(f"Invalid image data:\n{e}")
        
        return image

    @classmethod
    def load(cls, path: str) -> Optional[Tags]:
        # define possible tag keys
        artist_keys    = {'TPE1', 'TPE2', 'TPE4', '©ART', 'Author', 'artist', 'TOPE'}
        album_keys     = {'TALB', 'TOAL', 'album'}
        title_keys     = {'TIT2', '©nam', 'Title', 'title'}
        genre_keys     = {'TCON', 'genre'}
        music_key_keys = {'TKEY', 'initialkey', 'key'}

        # load track tags, check for errors
        try:
            track = mutagen.File(path)
        except mutagen.MutagenError as e:
            logging.error(f"mutagen.MutagenError:\n{e}\npath: '{path}'")
            return None
        if track is None or track.tags is None:
            logging.error(f"unable to read '{path}'")
            return None

        # extract tag values
        title       = cls.extract_tag_value(track, title_keys)
        artist      = cls.extract_tag_value(track, artist_keys)
        album       = cls.extract_tag_value(track, album_keys)
        genre       = cls.extract_tag_value(track, genre_keys)
        key         = cls.extract_tag_value(track, music_key_keys)
        cover_image = cls.extract_cover_image(track)
        
        # failure if title and artist not present
        if title is None and artist is None:
            logging.error(f"unable to find title and artist tags for '{path}'")
            return None
        
        # log warning if critical tags are absent
        if artist is None or title is None:
            logging.warning(f"missing title or artist for '{path}'")

        return cls(artist, album, title, genre, key, cover_image)

# DEV - Investigation
relevant_keys = {'genre', 'beatgrid', 'TENC', 'TOAL', 'TCOM', 'TDRC', 'USLT::eng', 'initialkey', 'TIT1', 'TCOP', 'TBPM', 'TOPE', 'cuepoints', 'TDRL', 'TSSE', 'TDEN', 'TPOS', 'WPUB', 'TSRC', 'artist', 'energy', 'TPE1', 'album', 'WOAF', 'TFLT', 'TDTG', 'key', 'metadata_block_picture', 'TCMP', 'TCON', 'PCNT', 'TALB', 'TDOR', 'comment', 'title', 'TPE2', 'TPE4', 'energylevel', 'TPUB', 'tracknumber', 'TLEN', 'TIT2'}

def dev_determine_relevant_keys(track: mutagen.FileType) -> set[str]:
    # -- dev: determine possibly relevant keys
    # print(track.keys())
    # ignore = { 'GEOB', 'COMM', 'UFID', 'APIC', 'metadata_block', 'TCMP', 'TENC' }
    ignore = {}
    relevant_keys: set[str] = set()
    for k in track:
        skip = False
        for nope in ignore:
            if k.startswith(nope) or k == nope:
                skip = True
                break
        if skip or len(k) > 64:
            continue

        relevant_keys.add(k)
    return relevant_keys

def dev_extract_tags(track: mutagen.FileType, relevant_keys: set[str]) -> dict[str, set[str]]:
    output : dict[str, set[str]] = {}
    for k in relevant_keys:
        if track is not None and k in track:
            if len(str(track[k])) < 64:
                # assume garbage otherwise
                line = f"{track[k]}"
                if k not in output:
                    # print_output.append(f"{k} : {track[k]}")
                    output[k] = {line}
                else:
                    output[k].add(line)
    return output

def dev_inspect_tags(path: str) -> None:
    try:
        track = mutagen.File(path)
    except mutagen.MutagenError as e:
        logging.error(f"mutagen.MutagenError:\n{e}\npath: '{path}'")
        return None
    assert track is not None, "track not loaded"
    print(dev_extract_tags(track, dev_determine_relevant_keys(track)))