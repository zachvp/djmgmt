#!/usr/bin/env bash
# Generate dummy audio fixtures for E2E testing.
# Requires ffmpeg. Run this once before starting the Docker environment.

set -euo pipefail

MUSIC_DIR="$(dirname "$0")/fixtures/music"

echo "Generating fixture audio files in $MUSIC_DIR..."

# 1-second silent MP3
ffmpeg -f lavfi -i anullsrc=r=44100:cl=stereo -t 1 -q:a 9 -acodec libmp3lame \
    "$MUSIC_DIR/track1.mp3" -y

# 1-second silent AIFF
ffmpeg -f lavfi -i anullsrc=r=44100:cl=stereo -t 1 \
    "$MUSIC_DIR/track2.aiff" -y

echo "Done. Files written to $MUSIC_DIR"
