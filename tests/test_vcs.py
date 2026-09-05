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


def test_tree_sha_ignores_an_untracked_pycache_with_no_gitignore(tmp_path):
    """The git branch's twin of the fallback bug: a freshly-scaffolded repo
    may have no .gitignore yet, so an untracked __pycache__/ left behind by a
    validator's own pytest subprocess shows up in `git status --porcelain` as
    `?? __pycache__/`. That must not count as tree content, or the QA
    validator's own test run would invalidate the developer's prior sign-off.
    """
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _commit(tmp_path, "init")

    before = tree_sha(tmp_path)
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "a.cpython-311.pyc").write_bytes(b"\x00\x01")
    after = tree_sha(tmp_path)

    assert before == after


def test_tree_sha_still_detects_a_real_edit_alongside_an_untracked_pycache(tmp_path):
    """The exclusion above must not blunt genuine staleness detection."""
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _commit(tmp_path, "init")

    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"\x00\x01")
    before = tree_sha(tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n")  # a real, tracked edit
    after = tree_sha(tmp_path)

    assert before != after
