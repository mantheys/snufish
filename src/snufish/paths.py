"""Repository locations. The root is found from the working directory
upwards (the directory holding ``benchmarks/``), or set with ``SNUFISH_ROOT``."""

import os
from pathlib import Path


def repo_root(root=None):
    if root is not None:
        return Path(root)
    if "SNUFISH_ROOT" in os.environ:
        return Path(os.environ["SNUFISH_ROOT"])
    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        if (directory / "benchmarks").is_dir() and (directory / "contributions").is_dir():
            return directory
    raise FileNotFoundError("no SNUfish repository found (set SNUFISH_ROOT)")


def benchmarks_dir(root=None):
    return repo_root(root) / "benchmarks"


def contributions_dir(root=None):
    return repo_root(root) / "contributions"


def build_dir(root=None):
    return repo_root(root) / "build" / "data"
