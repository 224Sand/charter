"""Minimal git access.

Only what the gates need: an identifier for the current working tree, so a
sign-off can be tied to the state it actually reviewed.
"""
import hashlib
import subprocess
from pathlib import Path


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
            payload = head.stdout.strip() + dirty.stdout
            return hashlib.sha256(payload.encode()).hexdigest()[:12]
    except (OSError, subprocess.SubprocessError):
        pass

    digest = hashlib.sha256()
    for path in sorted(Path(repo).rglob("*")):
        if path.is_file() and ".charter" not in path.parts and ".git" not in path.parts:
            digest.update(path.name.encode())
            digest.update(str(path.stat().st_mtime_ns).encode())
    return digest.hexdigest()[:12]
