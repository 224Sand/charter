"""Minimal git access.

Only what the gates need: an identifier for the current working tree, so a
sign-off can be tied to the state it actually reviewed.
"""
import hashlib
import subprocess
from pathlib import Path

# Directories whose contents are build/tooling side effects, not tree content:
# ".charter" is charter's own state, ".git" is version control metadata, and
# "__pycache__" / ".pytest_cache" are written by the *validators themselves*
# (validate_failing_test shells out to pytest against the repo) -- without
# this exclusion, running the QA validator would silently invalidate the
# developer's sign-off on the very same tree, whether tree_sha is reading
# `git status --porcelain` (an untracked __pycache__/ is real, uncommitted
# tree state as far as git is concerned) or hashing mtimes directly outside
# a git repository. Single source of truth for both branches below.
_EXCLUDED_DIRS = {".charter", ".git", "__pycache__", ".pytest_cache"}


def _filter_excluded_status(porcelain_output: str) -> str:
    """Drop `git status --porcelain` lines for excluded paths.

    Keeps the git branch and the non-git fallback agreeing on what counts as
    tree content -- see _EXCLUDED_DIRS.
    """
    kept = []
    for line in porcelain_output.splitlines(keepends=True):
        path = line[3:].rstrip("\r\n")
        if " -> " in path:  # rename/copy: "old -> new"; the new path is what
            path = path.split(" -> ", 1)[1]  # the working tree now contains.
        if _EXCLUDED_DIRS.intersection(Path(path).parts):
            continue
        kept.append(line)
    return "".join(kept)


def tree_sha(repo: Path) -> str:
    """Identify the current working tree.

    Uses `git status --porcelain` plus HEAD so that uncommitted edits change
    the identifier -- a sign-off must go stale when the code moves, whether or
    not anyone committed. Falls back to hashing tracked file mtimes outside a
    git repository so charter still works on a plain directory.
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo,
            capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo,
            capture_output=True, text=True, timeout=10)
        if head.returncode == 0:
            payload = head.stdout.strip() + _filter_excluded_status(dirty.stdout)
            return hashlib.sha256(payload.encode()).hexdigest()[:12]
    except (OSError, subprocess.SubprocessError):
        pass

    digest = hashlib.sha256()
    for path in sorted(Path(repo).rglob("*")):
        if path.is_file() and not _EXCLUDED_DIRS.intersection(path.parts):
            digest.update(path.name.encode())
            digest.update(str(path.stat().st_mtime_ns).encode())
    return digest.hexdigest()[:12]
