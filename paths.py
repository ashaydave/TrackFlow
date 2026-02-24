r"""
paths.py — Centralised path resolution for TrackFlow.

In dev mode  : data/ and assets/ are relative to this file.
In frozen exe: data/ redirects to %APPDATA%\TrackFlow\
               assets/ resolves via sys._MEIPASS (bundle root).
"""
import os
import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def get_data_dir() -> Path:
    if _is_frozen():
        base = Path(os.environ.get("APPDATA", Path.home())) / "TrackFlow"
    else:
        base = Path(__file__).parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_cache_dir() -> Path:
    d = get_data_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_assets_dir() -> Path:
    if _is_frozen():
        return Path(sys._MEIPASS) / "assets"      # type: ignore[attr-defined]
    return Path(__file__).parent / "assets"
