import unittest

'''
Plan
    Define Dockerfile for test image
        Copy files
            rsync daemon config
            requirements.txt
            dummy music files
                one per extension/file type
                some with cover art, others missing
            manifest
                dummy music files
                    cover art status
                    tag metadata
            library.xml
                use latest actual RB library export
            template.xml
            sync_state.txt
        Install dependencies
            Install ffmpeg
            Install rsync
            Install python
            Install pip dependencies
        Spin up dependencies
            Start rsync daemon
            Start subsonic wire mock
    
    Run docker container
        Create test fixtures
            Clone dummy music files to populate paths in library.xml
            Populate downloads folder
                Music files to sweep
                Random noise files to test filtering
            
        Run tests
            E2E: music.update_library()

        Assert expectations
            Check client mirror path files: should match library.xml
            Check rsync daemon destination files: should match client mirror path
            Check dynamic processed-xml file
            Check sync_state.txt
'''

class UpdateLibrary(unittest.TestCase):
    def test_success(self):
        # call update library
        # input: XML collection
        pass