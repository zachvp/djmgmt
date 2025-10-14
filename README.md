# Next steps
## Development
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
1. Convert WAV files to AIFF
2. Refactor genres: Move House/Techno to Techno/
3. Backup SoundCloud mixes locally: create local mirror of all uploaded signature mixes
    Add cover image, encode to MP3
    Use mix URL -> recording filename as possible hint