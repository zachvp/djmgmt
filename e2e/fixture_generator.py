'''
Generates dummy audio and noise fixtures from a JSON manifest for E2E testing.

Reads a manifest JSON file with three sections:
  - music_files: individual audio files to generate with metadata tags
  - archives: ZIP archives whose contents are typed as music, image, app, or doc
  - noise_files: loose non-music files (images, PDFs, DMGs, etc.)

Usage:
    result = generate_from_manifest('fixtures/manifests/dummy-files.json', '/tmp/new_music')
    print(result.expected_music_count)  # tracks that survive the full pipeline
'''

import json
import os
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Any


@dataclass
class GenerateResult:
    '''Counts derived from the manifest for use in test assertions.'''
    # number of music tracks that should survive sweep → process → record
    expected_music_count: int
    # number of archives that should be rejected by sweep
    rejected_archive_count: int
    # number of discrete files/archives that sweep should move (music files + accepted archives)
    expected_swept_count: int
    # archive filenames that sweep should NOT move
    rejected_names: set[str]
    # number of accepted archives (for TestExtract: len(extracted) assertion)
    accepted_archive_count: int
    # total files across all accepted archive contents (for TestExtract: extracted file count assertion)
    expected_archive_file_count: int
    # count of WAV + FLAC files across music_files and accepted archive contents (for TestStandardizeLossless)
    lossless_file_count: int


def generate_from_manifest(manifest_path: str, output_dir: str) -> GenerateResult:
    '''Reads the manifest at manifest_path and generates all files into output_dir.

    Returns a GenerateResult with expected counts for test assertions.
    '''
    with open(manifest_path, encoding='utf-8') as f:
        manifest: dict[str, Any] = json.load(f)

    expected_music = 0
    rejected_archives = 0
    expected_swept = 0
    rejected_names: set[str] = set()
    accepted_archive_count = 0
    expected_archive_file_count = 0
    lossless_file_count = 0
    lossless_extensions = {'.wav', '.flac'}

    for entry in manifest.get('music_files', []):
        path = os.path.join(output_dir, entry['path'])
        _generate_audio_file(path, entry)
        expected_music += 1
        expected_swept += 1
        ext = os.path.splitext(entry['path'])[1].lower()
        if ext in lossless_extensions:
            lossless_file_count += 1

    for entry in manifest.get('archives', []):
        _generate_archive(output_dir, entry)
        if entry.get('expected_accept', True):
            expected_swept += 1
            accepted_archive_count += 1
            for item in entry.get('contents', []):
                expected_archive_file_count += 1
                if item['type'] == 'music':
                    expected_music += 1
                    ext = os.path.splitext(item['path'])[1].lower()
                    if ext in lossless_extensions:
                        lossless_file_count += 1
        else:
            rejected_archives += 1
            rejected_names.add(entry['path'])

    for entry in manifest.get('noise_files', []):
        path = os.path.join(output_dir, entry['path'])
        _generate_noise_file(path)

    return GenerateResult(
        expected_music_count=expected_music,
        rejected_archive_count=rejected_archives,
        expected_swept_count=expected_swept,
        rejected_names=rejected_names,
        accepted_archive_count=accepted_archive_count,
        expected_archive_file_count=expected_archive_file_count,
        lossless_file_count=lossless_file_count,
    )


def _generate_audio_file(path: str, entry: dict[str, Any]) -> None:
    '''Generates a 1-second silent audio file at path with metadata tags from entry.

    Format is inferred from the file extension. Tags.load requires at least
    one of title/artist to be non-None.
    '''
    ext = os.path.splitext(path)[1].lower()
    title = entry.get('title', 'Test Track')
    artist = entry.get('artist', 'Test Artist')

    cmd = [
        'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
        '-t', '1',
        '-metadata', f'title={title}',
        '-metadata', f'artist={artist}',
    ]

    if ext == '.mp3':
        cmd += ['-acodec', 'libmp3lame', '-q:a', '9']
    elif ext == '.flac':
        cmd += ['-c:a', 'flac']
    # aiff and wav use default pcm encoding

    cmd += [path, '-y']
    subprocess.run(cmd, check=True, capture_output=True)


def _generate_archive(output_dir: str, entry: dict[str, Any]) -> None:
    '''Creates a ZIP archive at output_dir/entry["path"] with generated contents.

    Content types:
      music  — 1-second silent audio file with tags
      image  — empty bytes file
      app    — empty bytes file (triggers sweep rejection via .app extension)
      doc    — empty bytes file
    '''
    archive_path = os.path.join(output_dir, entry['path'])
    contents: list[dict[str, Any]] = entry.get('contents', [])

    with tempfile.TemporaryDirectory() as tmp:
        for item in contents:
            item_path = os.path.join(tmp, item['path'])
            if item['type'] == 'music':
                _generate_audio_file(item_path, item)
            else:
                # image, app, doc — empty placeholder bytes
                with open(item_path, 'wb') as f:
                    f.write(b'\x00')

        with zipfile.ZipFile(archive_path, 'w') as zf:
            for item in contents:
                zf.write(os.path.join(tmp, item['path']), arcname=item['path'])


def _generate_noise_file(path: str) -> None:
    '''Writes an empty placeholder file at path (including hidden files like .DS_Store).'''
    with open(path, 'wb') as f:
        f.write(b'\x00')
