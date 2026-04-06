# Spotify Playlist Download — Design

**Date:** 2026-04-05
**Status:** Approved

## Summary

Add Spotify public playlist URL support to TrackFlow's subscription system. Users paste a `open.spotify.com/playlist/...` URL, TrackFlow extracts the track list by scraping the public page, then searches YouTube for each track and downloads via the existing pipeline.

## Approach

**Web scraping (no API credentials).** Spotify public playlist pages embed track metadata in `<script>` tags as JSON. We parse this to extract track names and artists. This matches the Apple Music URL pattern — paste and go, no setup required.

## New Code

### `SpotifyPlaylistSource` (in `downloader/playlist_sync.py`)

- Same interface as `AppleMusicURLSource`
- `source_id`: `"spotify::playlist_url"`
- `get_tracks()`:
  1. Fetch public playlist page via `urllib.request`
  2. Parse embedded JSON from `<script>` tags for track listing
  3. Return `[{id, title, artist}, ...]`
- Tracks have no direct download URL — go through `search_youtube(title, artist)` (existing)

### Config entry (in `downloads_config.json`)

```json
{"type": "spotify", "url": "https://open.spotify.com/playlist/...", "label": "My Playlist"}
```

### UI changes (in `ui/downloads_tab.py`)

- Add "Spotify URL" input field + "+ Subscribe" button in the Subscriptions section
- Same layout pattern as the Apple Music URL field
- Wire into `_build_sources()` to instantiate `SpotifyPlaylistSource`

## What stays the same

- YouTube search fallback (`search_youtube()`)
- Sync state management (`sync_state.json`)
- Download queue, progress, and import flow
- `PlaylistSyncWorker` handles `SpotifyPlaylistSource` like any other source

## Dependencies

None. Uses `urllib.request`, `json`, `re` — all stdlib.

## Risks

- Spotify may change page structure → parser needs updating (same risk as Apple Music scraper)
- Private playlists won't work (public only)
