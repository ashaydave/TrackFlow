# Spotify Playlist Download — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Spotify public playlist URL support to TrackFlow's subscription system — users paste a URL, TrackFlow scrapes the track list and downloads each track via YouTube.

**Architecture:** New `SpotifyPlaylistSource` class in `playlist_sync.py` following the same interface as `AppleMusicURLSource`. Tracks are extracted by scraping embedded JSON from the public playlist page, then each track goes through the existing `search_youtube()` pipeline. UI adds a Spotify URL input field in the Subscriptions tab.

**Tech Stack:** `urllib.request`, `json`, `re` (all stdlib). No new dependencies.

---

### Task 1: SpotifyPlaylistSource — scrape track list

**Files:**
- Modify: `downloader/playlist_sync.py` (add class after `AppleMusicURLSource`, around line 516)

**Step 1: Add `SpotifyPlaylistSource` class**

Insert after the `AppleMusicURLSource` class (after line 515) and before `detect_apple_music_xml()`:

```python
class SpotifyPlaylistSource:
    """
    Fetches the track list from a public Spotify playlist URL.

    Scrapes the public playlist page for embedded JSON track data.
    For each track found, PlaylistSyncWorker will call search_youtube()
    to locate a matching YouTube video for download.

    Parameters
    ----------
    url   : Full https://open.spotify.com/playlist/... URL
    label : Human-readable name shown in the Queue source column
    """

    def __init__(self, url: str, label: str = ""):
        self.url = url
        self.label = label or "Spotify"
        self.source_id = f"spotify::{url}"
        self.last_error: str | None = None

    def get_tracks(self) -> list[dict]:
        """
        Returns list of dicts: {id, title, artist}.
        Scrapes the public playlist page for embedded track metadata.
        Sets self.last_error if scraping fails.
        """
        import re
        import json
        import urllib.request

        self.last_error = None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            req = urllib.request.Request(self.url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                page = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            self.last_error = f"Could not fetch Spotify playlist page: {exc}"
            return []

        # Strategy 1: Spotify embeds JSON-LD with MusicPlaylist schema
        for raw in re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            page, re.DOTALL,
        ):
            try:
                data = json.loads(raw)
                tracks = self._parse_ld(data)
                if tracks:
                    return tracks
            except Exception:
                continue

        # Strategy 2: Look for Spotify's __NEXT_DATA__ or similar embedded JSON
        # Spotify uses Next.js — track data is often in the hydration blob
        for pattern in [
            r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r'Spotify\.Entity\s*=\s*({.*?});',
        ]:
            m = re.search(pattern, page, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    tracks = self._extract_tracks_from_json(data)
                    if tracks:
                        return tracks
                except Exception:
                    continue

        # Strategy 3: Broad hunt for track-like objects in any <script> tag
        for raw in re.findall(r'<script[^>]*>(.*?)</script>', page, re.DOTALL):
            if '"track"' not in raw and '"name"' not in raw:
                continue
            # Find JSON objects within the script content
            for json_match in re.finditer(r'\{["\']@type["\'].*?\}(?=\s*[,;\]<])', raw, re.DOTALL):
                try:
                    data = json.loads(json_match.group(0))
                    tracks = self._parse_ld(data)
                    if tracks:
                        return tracks
                except Exception:
                    continue

        # Strategy 4: Use yt-dlp as last resort (it has some Spotify support)
        try:
            opts = {"quiet": True, "extract_flat": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False) or {}
            entries = info.get("entries") or []
            result = []
            for e in entries:
                title = (e.get("title") or "").strip()
                if title:
                    artist = (
                        e.get("artist") or e.get("creator")
                        or e.get("uploader") or ""
                    ).strip()
                    result.append({
                        "id": e.get("id") or f"{title}::{artist}",
                        "title": title,
                        "artist": artist,
                    })
            if result:
                return result
        except Exception:
            pass

        self.last_error = (
            "Could not extract tracks — check that the playlist is public."
        )
        return []

    @staticmethod
    def _parse_ld(data: dict) -> list[dict]:
        """Parse JSON-LD MusicPlaylist / MusicRecording schema."""
        if isinstance(data, list):
            for item in data:
                result = SpotifyPlaylistSource._parse_ld(item)
                if result:
                    return result
            return []

        # Direct MusicPlaylist with track list
        tracks_data = data.get("track", data.get("tracks", []))
        if isinstance(tracks_data, dict):
            tracks_data = tracks_data.get("itemListElement", [])

        tracks = []
        for item in tracks_data:
            # Handle itemListElement wrapper
            if "item" in item:
                item = item["item"]
            name = (item.get("name") or "").strip()
            if not name:
                continue
            by_artist = item.get("byArtist", item.get("artist", {}))
            if isinstance(by_artist, dict):
                artist = by_artist.get("name", "")
            elif isinstance(by_artist, list) and by_artist:
                artist = by_artist[0].get("name", "")
            elif isinstance(by_artist, str):
                artist = by_artist
            else:
                artist = ""
            tracks.append({
                "id": item.get("id") or f"{name}::{artist}",
                "title": name,
                "artist": artist.strip(),
            })
        return tracks

    @staticmethod
    def _extract_tracks_from_json(obj, _depth: int = 0) -> list[dict]:
        """Recursively hunt for track-like objects in arbitrary JSON."""
        if _depth > 12 or not obj:
            return []
        if isinstance(obj, dict):
            name = obj.get("name") or obj.get("title") or ""
            if (isinstance(name, str) and name
                    and any(k in obj for k in (
                        "artists", "duration_ms", "track_number",
                        "disc_number", "uri", "is_playable",
                    ))):
                artists = obj.get("artists", [])
                if isinstance(artists, list) and artists:
                    artist = artists[0].get("name", "")
                else:
                    artist = obj.get("artist", "")
                    if isinstance(artist, dict):
                        artist = artist.get("name", "")
                return [{
                    "id": obj.get("id") or obj.get("uri") or f"{name}::{artist}",
                    "title": name,
                    "artist": str(artist).strip(),
                }]
            results: list[dict] = []
            for v in obj.values():
                results.extend(
                    SpotifyPlaylistSource._extract_tracks_from_json(v, _depth + 1))
            return results
        if isinstance(obj, list):
            results = []
            for item in obj:
                results.extend(
                    SpotifyPlaylistSource._extract_tracks_from_json(item, _depth + 1))
            return results
        return []
```

**Step 2: Update module docstring**

Update line 1-17 to include Spotify:

```python
"""
Playlist sync: detects new tracks in subscribed YouTube playlists,
Apple Music / iTunes XML playlists, and Spotify playlists,
and queues them for download.

Sources
-------
- YouTubePlaylistSource    — uses yt-dlp extract_flat to list a playlist
- AppleMusicSource         — parses Apple Music for Windows / iTunes XML via stdlib plistlib
- AppleMusicURLSource      — scrapes public Apple Music playlist pages
- SpotifyPlaylistSource    — scrapes public Spotify playlist pages

For Apple Music / Shazam / Spotify tracks (no YouTube URL), search_youtube()
tries 3 query variants and returns the first match.

State persistence
-----------------
Sync state is stored in get_data_dir() / 'sync_state.json' as:
  { source_id: [id_or_title, ...] }
"""
```

**Step 3: Commit**

```bash
git add downloader/playlist_sync.py
git commit -m "feat: add SpotifyPlaylistSource for public playlist scraping"
```

---

### Task 2: Wire SpotifyPlaylistSource into _build_sources

**Files:**
- Modify: `ui/downloads_tab.py:966-980` (`_build_sources` method)
- Modify: `ui/downloads_tab.py` (import at top)

**Step 1: Add import**

Find the existing import block (around line 22-25 where `YouTubePlaylistSource`, `AppleMusicSource`, `AppleMusicURLSource` are imported). Add `SpotifyPlaylistSource` to the import:

```python
from downloader.playlist_sync import (
    YouTubePlaylistSource,
    AppleMusicSource,
    AppleMusicURLSource,
    SpotifyPlaylistSource,
    ...
)
```

**Step 2: Add spotify case to `_build_sources`**

In the `_build_sources` method (line 966), add after the `apple_music_url` elif (line 979):

```python
            elif sub.get("type") == "spotify":
                src = SpotifyPlaylistSource(sub["url"], sub.get("label", sub["url"]))
                sources.append(src)
```

**Step 3: Commit**

```bash
git add ui/downloads_tab.py
git commit -m "feat: wire SpotifyPlaylistSource into build_sources"
```

---

### Task 3: Add Spotify URL input in Subscriptions UI

**Files:**
- Modify: `ui/downloads_tab.py` (Subscriptions tab layout, around line 258)

**Step 1: Add Spotify group box after the Apple Music group**

Find where `am_group` is added to the layout (look for `lay.addWidget(am_group)`) and add a Spotify group after it:

```python
        # ── Spotify ───────────────────────────────────────────────────
        sp_group = QGroupBox("Spotify")
        sp_lay   = QVBoxLayout(sp_group)
        sp_lay.setSpacing(6)

        sp_url_row = QHBoxLayout()
        sp_url_row.addWidget(QLabel("Playlist URL:"))
        self._sp_url_edit = QLineEdit()
        self._sp_url_edit.setPlaceholderText(
            "Paste a open.spotify.com/playlist/... URL and press Enter…")
        self._sp_url_edit.returnPressed.connect(self._on_add_spotify_url)
        sp_url_row.addWidget(self._sp_url_edit, stretch=1)
        btn_sp_add = QPushButton("+ Add")
        btn_sp_add.setFixedWidth(72)
        btn_sp_add.clicked.connect(self._on_add_spotify_url)
        sp_url_row.addWidget(btn_sp_add)
        sp_lay.addLayout(sp_url_row)

        self._sp_table = QTableWidget(0, 2)
        self._sp_table.setHorizontalHeaderLabels(["Playlist", ""])
        self._sp_table.horizontalHeader().setSectionResizeMode(
            0, self._sp_table.horizontalHeader().ResizeMode.Stretch)
        self._sp_table.horizontalHeader().setSectionResizeMode(
            1, self._sp_table.horizontalHeader().ResizeMode.ResizeToContents)
        self._sp_table.verticalHeader().setVisible(False)
        self._sp_table.setMaximumHeight(100)
        sp_lay.addWidget(self._sp_table)
        lay.addWidget(sp_group)
```

**Step 2: Commit**

```bash
git add ui/downloads_tab.py
git commit -m "feat: add Spotify URL input group in Subscriptions UI"
```

---

### Task 4: Add Spotify subscription handler + table management

**Files:**
- Modify: `ui/downloads_tab.py` (add `_on_add_spotify_url`, update `_refresh_subscription_tables`, update `_remove_subscription`)

**Step 1: Add `_on_add_spotify_url` method**

Add near the other subscription handlers (after `_on_quick_add_am_url`, around line 788):

```python
    def _on_add_spotify_url(self) -> None:
        """Add a Spotify playlist URL subscription."""
        url = self._sp_url_edit.text().strip()
        if not url:
            return
        if "open.spotify.com/playlist" not in url:
            QMessageBox.warning(
                self, "Invalid URL",
                "Please paste a Spotify playlist URL.\n"
                "Example: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
            return
        # Ask for a friendly label
        label, ok = QInputDialog.getText(
            self, "Playlist Label",
            "Name for this playlist (shown in the queue Source column):",
            text=url.rstrip("/").split("/")[-1][:20] if "/" in url else "Spotify")
        if not ok:
            return
        label = label.strip() or url
        subs = self._config.setdefault("subscriptions", [])
        if any(s.get("url") == url for s in subs):
            QMessageBox.information(self, "Already Added", "This playlist is already subscribed.")
            return
        subs.append({"type": "spotify", "url": url, "label": label})
        self._save_config()
        self._sp_url_edit.clear()
        self._refresh_subscription_tables()
```

**Step 2: Add `_add_sp_row` method**

Add near `_add_am_row` (around line 944):

```python
    def _add_sp_row(self, display: str, url: str, tooltip: str = "") -> None:
        """Add a row to the Spotify subscription table."""
        row = self._sp_table.rowCount()
        self._sp_table.insertRow(row)
        item = QTableWidgetItem(display)
        if tooltip:
            item.setToolTip(tooltip)
        self._sp_table.setItem(row, 0, item)
        btn_rm = self._make_remove_btn()
        btn_rm.clicked.connect(lambda: self._remove_subscription("spotify", url))
        self._sp_table.setCellWidget(row, 1, btn_rm)
```

**Step 3: Update `_refresh_subscription_tables`**

In `_refresh_subscription_tables` (line 886), add `self._sp_table.setRowCount(0)` after the existing table resets, and add a spotify case in the loop:

```python
    def _refresh_subscription_tables(self) -> None:
        """Repopulate all subscription tables from config."""
        self._yt_table.setRowCount(0)
        self._am_table.setRowCount(0)
        self._sp_table.setRowCount(0)
        for sub in self._config.get("subscriptions", []):
            if sub.get("type") == "youtube":
                self._add_yt_row(sub["url"], sub.get("label", sub["url"]))
            elif sub.get("type") == "apple_music":
                self._add_am_row(sub["playlist"])
            elif sub.get("type") == "apple_music_url":
                self._add_am_row(
                    sub.get("label", sub["url"]),
                    key=sub["url"],
                    sub_type="apple_music_url",
                    tooltip=sub["url"],
                )
            elif sub.get("type") == "spotify":
                self._add_sp_row(
                    sub.get("label", sub["url"]),
                    url=sub["url"],
                    tooltip=sub["url"],
                )
```

**Step 4: Update `_remove_subscription`**

In `_remove_subscription` (line 946), add a spotify case:

```python
        elif sub_type == "spotify":
            self._config["subscriptions"] = [
                s for s in subs
                if not (s.get("type") == "spotify" and s.get("url") == key)
            ]
```

**Step 5: Commit**

```bash
git add ui/downloads_tab.py
git commit -m "feat: Spotify subscription handler, table row, refresh, and removal"
```

---

### Task 5: Test end-to-end and commit

**Step 1: Run the app from terminal**

```bash
conda run -n dj-analyzer --no-capture-output python main.py
```

**Step 2: Manual verification checklist**

1. Open Downloads tab → Subscriptions
2. Verify Spotify group box appears with URL field and "+ Add" button
3. Paste a public Spotify playlist URL (e.g. `https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M`)
4. Click "+ Add" → label dialog appears → confirm
5. Verify playlist appears in the Spotify table with "✕ Remove" button
6. Click "🔄 Sync Now" → verify tracks appear in the Queue tab
7. Click "✕ Remove" on the Spotify subscription → verify it's removed
8. Try an invalid URL → verify warning dialog appears

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete Spotify playlist subscription support"
```
