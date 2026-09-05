"""Tests for the git-aware branch of charter.vcs.tree_sha.

pytest's `tmp_path` is never itself inside a git repository, so a test that
merely calls `tree_sha(tmp_path)` exercises only the mtime-hashing fallback.
These tests deliberately `git init` inside `tmp_path` first, so the real
`git rev-parse` / `git status --porcelain` branch runs -- that branch is what
makes a sign-off's staleness real, since it is the one the loop actually hits
inside an ordinary checkout.
"""
import subprocess
from pathlib import Path

from charter.vcs import tree_sha


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                    cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)


def test_tree_sha_is_stable_with_no_changes(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _commit(tmp_path, "init")

    assert tree_sha(tmp_path) == tree_sha(tmp_path)


def test_tree_sha_changes_on_an_uncommitted_edit(tmp_path):
    """The load-bearing property: a sign-off must go stale the moment code
    moves, whether or not anyone committed."""
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _commit(tmp_path, "init")

    before = tree_sha(tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n")  # edited, NOT committed
    after = tree_sha(tmp_path)

    assert before != after


def test_tree_sha_changes_after_committing_the_edit(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _commit(tmp_path, "init")

    dirty = tree_sha(tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n")
    _commit(tmp_path, "edit")
    committed = tree_sha(tmp_path)

    assert committed != dirty
