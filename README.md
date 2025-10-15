# Next steps
## Development
* sync music to flash drive from beginning to "06/14/2025"
* Retain order of 'mixtapes' playlists in dynamic.played
* Watch RB export path folder to update dynamic.unplayed playlist
* Re-sync outdated files: live test
* Discover played _pruned tracks: read RB XML to determine played tracks in archive playlists
* Check if existing playlist has any previously played tracks
* Read Rekordbox DB for unassigned Tags in _pruned
* Use GitHub for project management

## Codebase improvement
* Ensure that all non-python files are properly included in python package (e.g. "state/collection-template.xml")
* Tests: use `assertListEqual` rather than `assertEqual`

## Manual library goals
* Convert WAV files to AIFF
* Backup SoundCloud mixes locally: create local mirror of all uploaded signature mixes
    Add cover image, encode to MP3
    Use mix URL -> recording filename as possible hint