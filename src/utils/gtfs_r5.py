"""GTFS helpers for Conveyal R5 / r5py (Java) compatibility."""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pandas as pd

__all__ = [
    "collapse_feed_info_dataframe",
    "ensure_single_feed_info_in_gtfs_zip",
    "refresh_r5py_gtfs_cache_copy",
    "r5py_cache_dir",
]


def collapse_feed_info_dataframe(fi: pd.DataFrame | None) -> pd.DataFrame | None:
    """R5 allows at most one feed_info row; merged feeds often have one per agency."""
    if fi is None or fi.empty:
        return None
    if len(fi) == 1:
        return fi.copy()

    def cs(v: object) -> str:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        s = str(v).strip()
        return "" if s.lower() == "nan" else s

    names: list[str] = []
    if "feed_publisher_name" in fi.columns:
        for v in fi["feed_publisher_name"]:
            t = cs(v)
            if t:
                names.append(t)
    publisher = " + ".join(dict.fromkeys(names)) if names else "merged_gtfs"

    url = ""
    if "feed_publisher_url" in fi.columns:
        url = next((cs(v) for v in fi["feed_publisher_url"] if cs(v)), "")

    lang = "en"
    if "feed_lang" in fi.columns:
        lang = next((cs(v) for v in fi["feed_lang"] if cs(v)), "en")

    starts: list[str] = []
    ends: list[str] = []
    if "feed_start_date" in fi.columns:
        for v in fi["feed_start_date"]:
            s = cs(v)
            if len(s) == 8 and s.isdigit():
                starts.append(s)
    if "feed_end_date" in fi.columns:
        for v in fi["feed_end_date"]:
            s = cs(v)
            if len(s) == 8 and s.isdigit():
                ends.append(s)
    feed_start = min(starts) if starts else ""
    feed_end = max(ends) if ends else ""

    vers = [cs(v) for v in fi["feed_version"]] if "feed_version" in fi.columns else []
    vers = [v for v in vers if v]
    feed_ver = "merged|" + "|".join(dict.fromkeys(vers)) if vers else "merged"
    if len(feed_ver) > 255:
        feed_ver = feed_ver[:252] + "..."

    one: dict[str, str] = {
        "feed_publisher_name": publisher,
        "feed_publisher_url": url,
        "feed_lang": lang,
        "feed_start_date": feed_start,
        "feed_end_date": feed_end,
        "feed_version": feed_ver,
    }
    for col in ("feed_contact_email", "feed_contact_url"):
        if col in fi.columns:
            one[col] = next((cs(v) for v in fi[col] if cs(v)), "")
    for col in fi.columns:
        if col not in one:
            one[col] = next((cs(v) for v in fi[col] if cs(v)), "")
    return pd.DataFrame([one])


def ensure_single_feed_info_in_gtfs_zip(zip_path: Path) -> bool:
    """
    If feed_info.txt has more than one row, collapse in-place inside the zip.
    Returns True if the zip was modified.
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zin:
        try:
            raw = zin.read("feed_info.txt")
        except KeyError:
            return False
        entries = {info.filename: zin.read(info.filename) for info in zin.infolist()}

    fi = pd.read_csv(io.BytesIO(raw), dtype=str)
    if len(fi) <= 1:
        return False
    collapsed = collapse_feed_info_dataframe(fi)
    if collapsed is None or collapsed.empty:
        return False
    new_csv = collapsed.to_csv(index=False, lineterminator="\n").encode("utf-8")
    entries["feed_info.txt"] = new_csv

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name in sorted(entries.keys()):
            zout.writestr(name, entries[name])
    return True


def r5py_cache_dir() -> Path:
    """Same directory as r5py.util.Config().CACHE_DIR (without importing r5py — avoids JVM)."""
    import os

    if "HOME" not in os.environ:
        os.environ["HOME"] = "."
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    if base:
        root = Path(base)
    else:
        root = Path(os.environ["HOME"]) / ".cache"
    d = root / "r5py"
    d.mkdir(parents=True, exist_ok=True)
    return d


def refresh_r5py_gtfs_cache_copy(source_zip: Path) -> None:
    """
    r5py WorkingCopy copies each GTFS basename into CACHE_DIR only if missing; it never
    refreshes. Java then reads the stale copy. Overwrite that copy from the repo path
    before TransportNetwork(...).
    """
    source_zip = Path(source_zip).resolve()
    dest = r5py_cache_dir() / source_zip.name
    shutil.copy2(source_zip, dest)
