# Clear Library Feature Design

**Date:** 2026-02-24

## Goal

Add a "Clear" button to the library toolbar that resets the track list to its initial empty state, without deleting cached analysis data.

## Placement

A "Clear" button in the library toolbar row, next to "Load Folder" and "Load Track" buttons. Discoverable since it's alongside the other library management controls.

## Behavior (`_clear_library()`)

1. Stop audio playback (`audio_player.stop()`)
2. Stop any active loop (`audio_player.stop_loop()` if in LOOP_PLAYING)
3. Cancel running analysis threads (batch or single)
4. Clear `track_table` (`setRowCount(0)`)
5. Reset `library_files = []` and `_row_map = {}`
6. Reset `current_track = None`
7. Clear waveform display
8. Reset loop state (`_loop_a`, `_loop_b`, `_loop_active`, clear waveform loop overlay)
9. Reset hot cue display (visual only -- saved cues persist on disk)
10. Clear similarity results table
11. Clear detail panel text
12. Disable analysis/player controls (return to initial app state)

## What it does NOT do

- Delete cache files (re-loading same folder stays instant)
- Delete playlists (independent collections)
- Delete hot cues from disk (per-track, loaded on demand)

## Implementation

Single task: Add "Clear" QPushButton to toolbar row + `_clear_library()` method in `main_window.py`.
