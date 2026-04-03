"""Repo root + executable discovery for BayesTransitEquity."""
from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def find_repo_root() -> Path:
    """Walk parents until `configs/san_diego.yaml` exists (notebook cwd may be repo or subdir)."""
    start = Path.cwd().resolve()
    for d in [start, *start.parents]:
        if (d / "configs" / "san_diego.yaml").exists():
            return d
    raise FileNotFoundError(
        "Could not find configs/san_diego.yaml; run notebooks from the repo root."
    )


def find_osmium_executable() -> str | None:
    """
    Locate the osmium CLI executable and return a subprocess-safe invocation string.

    Root cause of the Windows '.EXE' bug
    ------------------------------------
    osmium-tool's internal argument parser (strip_extensions in osmium's source)
    only strips lowercase '.exe' / '.cmd' / '.bat' from argv[0] when deciding
    whether it was invoked as the multi-command dispatcher ("osmium") or as a
    single-command alias ("osmium-extract", etc.).

    On Windows, Conda installs the binary as ``osmium.EXE`` (uppercase extension).
    When subprocess passes the full path as argv[0], osmium sees:
        argv[0] = "C:\\...\\osmium.EXE"
        basename → "osmium.EXE"
        strip_extensions("osmium.EXE") → "osmium.EXE"  # .EXE not stripped!
        program_name = "osmium.EXE"  ≠  "osmium"

    osmium then treats "osmium.EXE" as a subcommand alias, fails to find it, and
    prints "Unknown command or option 'osmium.EXE'. Try 'osmium help'."

    Fix
    ---
    On Windows, prefer calling osmium by its bare name ("osmium") when it is
    resolvable via PATH.  subprocess will still find and launch the correct
    binary, but argv[0] will be "osmium" and osmium's parser will work correctly.

    When the bare name is not on PATH (e.g. user installed into a non-default
    prefix), we fall back to the full path but normalise the suffix to lowercase
    so strip_extensions("osmium.exe") → "osmium" succeeds.
    """

    # ── 1. Explicit override via environment variable ─────────────────────────
    env_exe = os.environ.get("OSMIUM_EXE", "").strip()
    if env_exe:
        p = Path(env_exe)
        if p.is_file():
            return _safe_osmium_path(p)
        # env var set but file not found — don't silently fall through
        return None

    # ── 2. shutil.which resolves "osmium" on PATH ──────────────────────────────
    found = shutil.which("osmium")
    if found:
        # On Windows, return the bare name so argv[0]="osmium" (no .EXE suffix).
        if platform.system() == "Windows":
            return "osmium"
        return found

    # ── 3. Conda environment prefix locations ─────────────────────────────────
    conda_prefix = os.environ.get("CONDA_PREFIX", "").strip()
    if conda_prefix:
        candidates = [
            Path(conda_prefix) / "Library" / "bin" / "osmium.exe",
            Path(conda_prefix) / "Library" / "bin" / "osmium",
            Path(conda_prefix) / "bin" / "osmium",
            Path(conda_prefix) / "Scripts" / "osmium.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return _safe_osmium_path(candidate)

    # ── 4. Common system / WSL locations (Linux / macOS) ─────────────────────
    for name in ("osmium", "osmium-tool"):
        w = shutil.which(name)
        if w:
            return _safe_osmium_path(Path(w))

    return None


def _safe_osmium_path(path: Path) -> str:
    """
    Return a subprocess-safe string for the osmium executable.

    On Windows, normalise the file extension to lowercase so that
    osmium's strip_extensions() correctly reduces "osmium.exe" → "osmium"
    and enters multi-command dispatch mode.  (Windows filesystems are
    case-insensitive, so the lowercase path still resolves to the same file.)
    """
    if platform.system() == "Windows" and path.suffix:
        return str(path.parent / (path.stem + path.suffix.lower()))
    return str(path)
