# Fresh Sync Runbook

Full clean-slate re-sync of the music library to Navidrome on the Raspberry Pi (corevega.local).

## Prerequisites

- SSH access to `zachvp@corevega.local`
- Latest Rekordbox collection XML exported to `~/Library/CloudStorage/OneDrive-Personal/Backups/rekordbox/collections/`
- Code changes on `sync-simplify-paths` branch merged/ready

### 1. Document current state

Note these values before starting so you can verify after re-sync:

```bash
# Track count on Pi
ssh zachvp@corevega.local "find /media/zachvp/SOL/music -name '*.mp3' | wc -l"

# Track count in local client mirror
find /Users/zachvp/Music/corevega -name '*.mp3' | wc -l
```

### 2. Back up Navidrome database (optional)

Only needed if you want to preserve play counts, ratings, or playlists.

```bash
# Find the Navidrome container name
ssh zachvp@corevega.local "docker ps --format '{{.Names}}' | grep -i navidrome"

# Back up the database (replace <container> with actual name)
ssh zachvp@corevega.local "docker exec <container> sqlite3 /data/navidrome.db '.backup /data/navidrome_backup.db'"
```

## Execution

### 3. Clear local client mirror

Remove all date-structured music files from the Mac mirror directory. These will be regenerated during sync.

```bash
rm -rf /Users/zachvp/Music/corevega/20*
```

### 4. Clear sync state

Delete the sync state file so all date contexts are treated as unprocessed. The file path is `state/sync_state.txt` relative to the project root.

```bash
rm -f state/sync_state.txt
```

### 5. Stop Navidrome on Pi

```bash
# Find container name if you don't know it
ssh zachvp@corevega.local "docker ps --format '{{.Names}}' | grep -i navidrome"

# Stop it (replace <container> with actual name)
ssh zachvp@corevega.local "docker stop <container>"
```

### 6. Clear remote music files

```bash
ssh zachvp@corevega.local "rm -rf /media/zachvp/SOL/music/20*"
```

### 7. Start Navidrome

```bash
ssh zachvp@corevega.local "docker start <container>"
```

### 8. Run full sync

Use the sync module directly. No `--end-date` means all date contexts will be synced.

```bash
python3 -m djmgmt.sync sync \
    --input ~/Library/CloudStorage/OneDrive-Personal/Backups/rekordbox/collections/<latest-collection>.xml \
    --output /Users/zachvp/Music/corevega \
    --scan-mode full \
    --sync-mode remote
```

This will:
1. Generate date-structured file mappings from the `_pruned` playlist (flat paths, no artist/album subdirs)
2. Encode lossless files to 320kbps MP3 in the client mirror (`/Users/zachvp/Music/corevega`)
3. Rsync encoded files to `rsync://zachvp@corevega.local:12000/navidrome`
4. Trigger a Navidrome library scan via the Subsonic API

**Tip**: Do a dry run first to verify mappings look correct:
```bash
python3 -m djmgmt.sync sync \
    --input ~/Library/CloudStorage/OneDrive-Personal/Backups/rekordbox/collections/<latest-collection>.xml \
    --output /Users/zachvp/Music/corevega \
    --scan-mode full \
    --sync-mode remote \
    --dry-run
```

## Verification

### 9. Check file counts

```bash
# Remote file count
ssh zachvp@corevega.local "find /media/zachvp/SOL/music -name '*.mp3' | wc -l"

# Local mirror file count
find /Users/zachvp/Music/corevega -name '*.mp3' | wc -l
```

Both counts should match each other and be close to the number of tracks in the `_pruned` playlist.

### 10. Verify Navidrome scan

- Open Navidrome web UI
- Check that the track count matches the file count from step 9
- Spot-check a few tracks for correct metadata (artist, album, cover art)
- Verify playback works

### 11. Check sync state

After a successful sync, the sync state file should contain the latest date context:

```bash
cat state/sync_state.txt
```