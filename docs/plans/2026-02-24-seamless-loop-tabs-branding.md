# Seamless Loop, Tab Border Fix & TrackFlow Branding — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix loop pops via pygame.Sound-based looping, connect the Playlists/Similar tab border to its content pane, and add the TrackFlow logo + name to the toolbar's right edge.

**Architecture:**
- Loop: add `LOOP_PLAYING` state to `AudioPlayer`; when loop B is set while playing, decode A→B into a `pygame.Sound` played with `loops=-1`; main_window stops polling for loop boundary since the Sound loops natively.
- Tabs: one CSS rule change in `styles.py`.
- Branding: logo QLabel + text QLabel added after `addStretch()` in `_build_toolbar()`.

**Tech Stack:** PyQt6, pygame 2.x, soundfile, soxr, numpy

---

## Task 1 — Tab Border CSS Fix

**Files:**
- Modify: `ui/styles.py` (QTabWidget section, ~line 307)

**Step 1: Update pane and selected-tab CSS**

Replace the current two rules:
```css
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: #1a1a2e;
    color: #aaaaaa;
    padding: 4px 14px;
    border: 1px solid #223355;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
}
QTabBar::tab:selected {
    background: #111830;
    color: #00ccff;
    border-color: #0088ff;
}
```

With:
```css
QTabWidget::pane {
    border: 1px solid #223355;
    border-top: none;
    border-radius: 0 0 4px 4px;
}
QTabBar::tab {
    background: #1a1a2e;
    color: #aaaaaa;
    padding: 4px 14px;
    border: 1px solid #223355;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
}
QTabBar::tab:selected {
    background: #111830;
    color: #00ccff;
    border-color: #0088ff;
    margin-bottom: -1px;
    padding-bottom: 5px;
}
```

The key changes:
- `::pane` gets `border: 1px solid #223355; border-top: none` — draws the box below the tabs
- `tab:selected` gets `margin-bottom: -1px; padding-bottom: 5px` — extends the selected tab down 1px to merge into the pane border

**Step 2: Run app and verify tabs look visually connected**

No automated test needed — visual check only.

**Step 3: Commit**
```bash
git add ui/styles.py
git commit -m "fix: connect tab bar to pane border visually"
```

---

## Task 2 — TrackFlow Branding in Toolbar

**Files:**
- Modify: `ui/main_window.py` — `_build_toolbar()` method (~line 443–481)

**Step 1: Locate the toolbar stretch and replace it**

Current end of `_build_toolbar()`:
```python
        btn_help.clicked.connect(self._show_help)
        lay.addWidget(btn_help)

        lay.addStretch()
        ...
        return lay
```

The `addStretch()` currently comes AFTER `btn_help` but pushes nothing to the right since it's last. Move the stretch BEFORE the branding block so it acts as a spacer.

**Step 2: Add branding after the stretch**

Replace the current `lay.addStretch()` with:
```python
        lay.addStretch()

        # ── TrackFlow branding (right side) ───────────────────────────
        from paths import get_assets_dir
        _logo_path = get_assets_dir() / "logo_32.png"
        lbl_logo = QLabel()
        if _logo_path.exists():
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(str(_logo_path))
            lbl_logo.setPixmap(pix.scaled(
                24, 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        lbl_logo.setFixedSize(28, 32)
        lay.addWidget(lbl_logo)

        lbl_brand = QLabel("TrackFlow")
        lbl_brand.setObjectName("brand_label")
        lay.addWidget(lbl_brand)
```

**Step 3: Add brand_label style to styles.py**

Append inside the stylesheet string (before the closing `"""`):
```css
/* ─── Toolbar branding ──────────────────────────────────── */
QLabel#brand_label {
    color: #00ccff;
    font-size: 15px;
    font-weight: bold;
    letter-spacing: 1px;
    padding-right: 6px;
}
```

**Step 4: Run app and verify logo + "TrackFlow" appear on far right of toolbar**

**Step 5: Commit**
```bash
git add ui/main_window.py ui/styles.py
git commit -m "feat: add TrackFlow logo and name to toolbar right side"
```

---

## Task 3 — Seamless Sound-Based Looping

### 3a — Extend AudioPlayer with LOOP_PLAYING state

**Files:**
- Modify: `ui/audio_player.py`

**Step 1: Add LOOP_PLAYING to PlayerState enum**

```python
class PlayerState(Enum):
    STOPPED     = auto()
    PLAYING     = auto()
    PAUSED      = auto()
    LOOP_PLAYING = auto()
```

**Step 2: Add loop sound instance variables to `__init__`**

After `self._paused_at_seconds: float = 0.0`, add:
```python
        self._loop_sound: object | None = None        # pygame.mixer.Sound
        self._loop_sound_a_secs: float  = 0.0
        self._loop_sound_dur: float     = 0.0
        self._loop_sound_wall: float    = 0.0
```

**Step 3: Update `_current_seconds` to handle LOOP_PLAYING**

```python
    def _current_seconds(self) -> float:
        if self.state == PlayerState.PAUSED:
            return self._paused_at_seconds
        if self.state == PlayerState.PLAYING:
            return time.time() - self._play_start_time
        if self.state == PlayerState.LOOP_PLAYING:
            elapsed = time.time() - self._loop_sound_wall
            return self._loop_sound_a_secs + (elapsed % max(self._loop_sound_dur, 1e-9))
        return 0.0
```

**Step 4: Update `_tick` to handle LOOP_PLAYING**

```python
    def _tick(self) -> None:
        if self.state == PlayerState.LOOP_PLAYING:
            self.position_changed.emit(self.get_position())
            return
        if self.state != PlayerState.PLAYING:
            return
        if not pygame.mixer.music.get_busy():
            self.stop()
            self.playback_finished.emit()
            return
        self.position_changed.emit(self.get_position())
```

**Step 5: Update `stop()` to also stop loop sound**

Add to the start of `stop()`:
```python
    def stop(self) -> None:
        if self._loop_sound is not None:
            try:
                self._loop_sound.stop()
            except Exception:
                pass
            self._loop_sound = None
        try:
            pygame.mixer.music.stop()
        ...
```

**Step 6: Update `pause()` to handle LOOP_PLAYING**

Add before the existing `if self.state != PlayerState.PLAYING` guard:
```python
    def pause(self) -> None:
        if self.state == PlayerState.LOOP_PLAYING:
            self._paused_at_seconds = self._current_seconds()
            if self._loop_sound is not None:
                try:
                    self._loop_sound.stop()
                except Exception:
                    pass
                self._loop_sound = None
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass
            self.state = PlayerState.PAUSED
            self._timer.stop()
            return
        if self.state != PlayerState.PLAYING:
            return
        ...
```

**Step 7: Update `set_volume()` to sync loop sound volume**

```python
    def set_volume(self, volume: float) -> None:
        try:
            v = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(v)
            if self._loop_sound is not None:
                self._loop_sound.set_volume(v)
        except Exception:
            pass
```

**Step 8: Add `start_loop()` method**

```python
    def start_loop(self, file_path: str, a_secs: float, b_secs: float) -> bool:
        """
        Decode the [a_secs, b_secs] region of file_path into a pygame.Sound
        and play it with loops=-1 for gap-free looping.
        Returns True on success, False on failure (caller should fall back to seek-based loop).
        """
        import numpy as np
        import soundfile as sf
        import soxr

        try:
            info = sf.info(str(file_path))
            sr_native = info.samplerate
            frame_a = int(a_secs * sr_native)
            frame_b = min(int(b_secs * sr_native), info.frames)
            n_frames = max(1, frame_b - frame_a)

            data, _ = sf.read(
                str(file_path),
                start=frame_a,
                frames=n_frames,
                dtype='int16',
                always_2d=True,
            )

            # Mixer expects 44100 Hz; resample if source differs
            mixer_sr = 44100
            if sr_native != mixer_sr:
                data_f = data.astype(np.float32) / 32768.0
                left  = soxr.resample(data_f[:, 0], sr_native, mixer_sr, quality='HQ')
                right = soxr.resample(data_f[:, 1] if data_f.shape[1] > 1 else data_f[:, 0],
                                      sr_native, mixer_sr, quality='HQ')
                data_f = np.column_stack([left, right])
                data = np.clip(data_f * 32768.0, -32768, 32767).astype(np.int16)

            # Ensure stereo (mixer initialised with channels=2)
            if data.shape[1] == 1:
                data = np.column_stack([data[:, 0], data[:, 0]])

            # Must be C-contiguous for pygame.sndarray
            data = np.ascontiguousarray(data)

            sound = pygame.sndarray.make_sound(data)
            sound.set_volume(pygame.mixer.music.get_volume())

            # Stop any existing loop sound, pause music stream
            if self._loop_sound is not None:
                self._loop_sound.stop()
            pygame.mixer.music.pause()

            self._loop_sound          = sound
            self._loop_sound_a_secs   = a_secs
            self._loop_sound_dur      = (frame_b - frame_a) / mixer_sr
            self._loop_sound_wall     = time.time()

            sound.play(loops=-1)

            self.state = PlayerState.LOOP_PLAYING
            self._timer.start()
            return True

        except Exception as e:
            print(f"AudioPlayer.start_loop error: {e}")
            return False
```

**Step 9: Add `stop_loop()` method**

```python
    def stop_loop(self) -> None:
        """Stop the Sound loop and resume music from current logical position."""
        if self._loop_sound is None:
            return
        current_secs = self._current_seconds()
        try:
            self._loop_sound.stop()
        except Exception:
            pass
        self._loop_sound = None

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=current_secs)
            self._play_start_time    = time.time() - current_secs
            self._paused_at_seconds  = current_secs
            self.state = PlayerState.PLAYING
            self._timer.start()
        except Exception as e:
            print(f"AudioPlayer.stop_loop resume error: {e}")
            self.state = PlayerState.PLAYING
```

**Step 10: Update `is_playing` property**

```python
    @property
    def is_playing(self) -> bool:
        return self.state in (PlayerState.PLAYING, PlayerState.LOOP_PLAYING)
```

**Step 11: Commit**
```bash
git add ui/audio_player.py
git commit -m "feat: add LOOP_PLAYING state and start_loop/stop_loop to AudioPlayer"
```

---

### 3b — Wire seamless loop in MainWindow

**Files:**
- Modify: `ui/main_window.py`

**Step 1: Remove the seek-on-loop-boundary check from `_on_position_changed`**

Current code block to remove:
```python
        if (self._loop_active
                and self._loop_a is not None
                and self._loop_b is not None
                and pos >= self._loop_b):
            self.audio_player.seek(self._loop_a)
            return
```

Delete those 5 lines entirely. The Sound handles the loop natively now.

**Step 2: Update `_set_loop_b` to start Sound loop immediately**

Current `_set_loop_b` ends with:
```python
        self._loop_b = pos
        self._loop_active = True
        self._refresh_loop_buttons()
        self._refresh_waveform_overlays()
```

After `self._refresh_waveform_overlays()`, add:
```python
        # Start gapless Sound-based loop if playing
        if self.audio_player.is_playing and self.current_track:
            a_secs = self._loop_a * self.audio_player.duration
            b_secs = self._loop_b * self.audio_player.duration
            ok = self.audio_player.start_loop(
                self.current_track['file_path'], a_secs, b_secs
            )
            if not ok:
                self._status.showMessage("Loop active (seek-based — Sound init failed)")
```

**Step 3: Update `_toggle_loop` to start/stop Sound loop**

Current `_toggle_loop`:
```python
    def _toggle_loop(self) -> None:
        if self._loop_a is None or self._loop_b is None:
            return
        self._loop_active = not self._loop_active
        self._refresh_loop_buttons()
```

Replace with:
```python
    def _toggle_loop(self) -> None:
        if self._loop_a is None or self._loop_b is None:
            return
        self._loop_active = not self._loop_active
        self._refresh_loop_buttons()
        self._refresh_waveform_overlays()
        if self._loop_active and self.audio_player.is_playing and self.current_track:
            a_secs = self._loop_a * self.audio_player.duration
            b_secs = self._loop_b * self.audio_player.duration
            self.audio_player.start_loop(
                self.current_track['file_path'], a_secs, b_secs
            )
        elif not self._loop_active:
            self.audio_player.stop_loop()
```

**Step 4: Update `_set_loop_b` second-press (stop loop case)**

In `_set_loop_b`, the early-return path for "second press while looping":
```python
        if self._loop_active and self._loop_b is not None:
            self._loop_b = None
            self._loop_active = False
            self._refresh_loop_buttons()
            self._refresh_waveform_overlays()
            return
```

Add `self.audio_player.stop_loop()` before the `return`:
```python
        if self._loop_active and self._loop_b is not None:
            self._loop_b = None
            self._loop_active = False
            self._refresh_loop_buttons()
            self._refresh_waveform_overlays()
            self.audio_player.stop_loop()
            return
```

**Step 5: Stop loop sound on track change**

In `_on_track_selected` (or wherever the track is changed / stopped), ensure any active loop sound is cleared:

Find the block that resets loop state on track load (around line 1365–1370):
```python
        self._loop_b = None
        self._loop_active = False
        self._refresh_loop_buttons()
```

Add before it:
```python
        self.audio_player.stop_loop()
```

**Step 6: Commit**
```bash
git add ui/main_window.py
git commit -m "feat: wire seamless Sound-based loop in MainWindow"
```

---

## Task 4 — Final verification & push

**Step 1: Run the app, load a track, set a loop, verify no pop**

Manual test checklist:
- [ ] I → O → loop plays with no pop/silence
- [ ] O again → loop stops, music resumes normally
- [ ] L → toggles loop on/off cleanly
- [ ] Play/Pause while looping → pauses cleanly, resume restarts music
- [ ] Snap buttons (½, 1, 2, 4, 8 bars) → loop snaps and restarts Sound
- [ ] Load different track → loop sound cleared
- [ ] Tabs visually connected to pane border
- [ ] TrackFlow logo + name on far right of toolbar

**Step 2: Push to GitHub**
```bash
git push origin main
```
