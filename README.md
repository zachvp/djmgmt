# Next steps
## Development
* Re-sync outdated files: live test (use "brian gibson - thumper - head intro.mp3" as test case)
* install djmgmt as global command (so python -m isn't required)
* Retain order of 'mixtapes' playlists in dynamic.played
* Read Rekordbox DB for unassigned Tags in _pruned
* Check if existing playlist has any previously played tracks

## Backburner
* Use GitHub for project management

## Codebase improvement
* Ensure that all non-python files are properly included in python package (e.g. "state/collection-template.xml")
* Tests: use `assertListEqual` rather than `assertEqual`

## Manual library goals
* Convert WAV files to AIFF
* Backup SoundCloud mixes locally: create local mirror of all uploaded signature mixes
    Add cover image, encode to MP3
    Use mix URL -> recording filename as possible hint