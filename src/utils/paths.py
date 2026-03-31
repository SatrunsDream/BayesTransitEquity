from pathlib import Path


def find_repo_root() -> Path:
    """Walk parents until `configs/san_diego.yaml` exists (notebook cwd may be repo or subdir)."""
    start = Path.cwd().resolve()
    for d in [start, *start.parents]:
        if (d / "configs" / "san_diego.yaml").exists():
            return d
    raise FileNotFoundError("Could not find configs/san_diego.yaml; run notebooks from the repo root.")
