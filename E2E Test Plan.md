# End-to-End Test Plan

## Overview

This plan describes a Docker-based end-to-end testing environment that fully simulates the djmgmt workflow: audio file processing, library management, and uploading to Navidrome.

## Docker Image Definition

### Files to Copy

- **rsync daemon config** - Configuration for rsync daemon service
- **requirements.txt** - Python dependencies
- **dummy music files**
  - One file per extension/file type (.mp3, .wav, .aiff, .flac)
  - Some with cover art, others missing
- **manifest** - Metadata catalog for dummy music files
  - Cover art status
  - Tag metadata (title, artist, album, etc) based on current library music files
- **library.xml** - Use latest actual Rekordbox library export
- **template.xml** - XML template for collection generation
- **sync_state.txt** - Sync state persistence file

### Install Dependencies

- Install ffmpeg
- Install rsync
- Install python
- Install pip dependencies

### Spin Up Services

- Start rsync daemon
- Start Navidrome container

## Test Container Execution

### Create Test Fixtures

- Clone dummy music files and match metadata to populate paths based on library.xml
- Populate downloads folder
  - Music files to sweep
  - Random noise files to test filtering

### Run Tests

- E2E: `music.update_library()`

### Assert Expectations

- Check client mirror path files: should match library.xml
- Check rsync daemon destination files: should match client mirror path
- Check dynamic processed-xml file
- Check sync_state.txt
