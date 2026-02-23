# Loop UX Redesign — Design Doc

**Date:** 2026-02-22
**Status:** Approved

## Problem

The loop row has three issues:
1. `A` / `B` labels are cryptic — `IN` / `OUT` is universally understood
2. Three required clicks (IN → OUT → LOOP) to start looping — OUT press should auto-start
3. `?` help button and bar-snap buttons are visually invisible against the dark background

## Approved Approach: Option A — OUT Toggles the Loop

### OUT button new contract

| State when OUT is pressed | Result |
|---|---|
| Loop is active (`_loop_active = True`) | Stop loop, clear `_loop_b`, button goes unlit |
| IN set, not looping, `pos > _loop_a` | Set `_loop_b = pos`, set `_loop_active = True`, button turns green |
| IN set, not looping, `pos <= _loop_a` | Show "Loop OUT must be after IN" |
| IN not set | Show "Set loop IN point first" |

### ⟳ LOOP button role (unchanged logic, reduced importance)

Kept as:
- Visual status indicator (green = looping)
- Target for `L` keyboard shortcut
- Still enabled only when both IN + OUT are set (as before)

Users no longer *need* to press it — pressing OUT handles everything.

## Button size / label changes

| Button | Old label | Old width | New label | New width |
|---|---|---|---|---|
| IN | `A` | 32 px | `IN` | 44 px |
| OUT | `B` | 32 px | `OUT` | 44 px |
| Bar snaps ×5 | ½ 1 2 4 8 | 28 px | ½ 1 2 4 8 | 34 px |

## Color coding

- **IN button**: amber `rgba(255,185,0,140)` border when set
- **OUT button**: green `rgba(0,220,100,160)` when looping, unlit otherwise
- **⟳ LOOP**: green when `_loop_active`; grey/disabled when IN+OUT not both set

## `?` Help button

Add `QPushButton#btn_help` CSS rule in `styles.py`:
```css
QPushButton#btn_help {
    background-color: rgba(0, 136, 255, 60);
    border-color: #0088ff;
    color: #00ccff;
    font-weight: 700;
    font-size: 15px;
}
QPushButton#btn_help:hover {
    background-color: rgba(0, 204, 255, 120);
    border-color: #00ccff;
}
```

Give `btn_help.setObjectName("btn_help")` in `_build_toolbar()`.

## Bar snap buttons

Apply inline style on construction:
```python
btn.setStyleSheet(
    "QPushButton { background-color: #111830; border-color: #223355; }"
    "QPushButton:hover { background-color: #1a2a50; border-color: #0088ff; }"
)
```

## Files changed

- `ui/main_window.py` — `_build_toolbar`, `_build_loop_row`, `_set_loop_b`, `_set_loop_a`, `_refresh_loop_buttons`, `HelpDialog` shortcut description for O key
- `ui/styles.py` — add `QPushButton#btn_help` rule

## No new tests needed

Logic change is small and fully covered by the import smoke test. Bar-snap and loop snap tests already pass.
