import textwrap
from charter.contracts.models import FailingTest, ChangeSummary
from charter.contracts.validators import validate_failing_test, validate
from charter.kernel.models import ArtifactKind


def _write(repo, name, body):
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body))
    return p


def test_a_genuinely_failing_test_is_accepted(tmp_path):
    _write(tmp_path, "tests/test_bug.py", """
        def test_reproduces():
            assert 1 == 2
    """)
    art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                      test_name="test_reproduces", defect_id="D-004")
    assert validate_failing_test(art, tmp_path).accepted


def test_a_passing_test_is_rejected_as_evidence(tmp_path):
    _write(tmp_path, "tests/test_bug.py", """
        def test_reproduces():
            assert 1 == 1
    """)
    art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                      test_name="test_reproduces", defect_id="D-004")
    result = validate_failing_test(art, tmp_path)
    assert not result.accepted
    assert "passes" in result.reason


def test_a_missing_test_file_is_rejected(tmp_path):
    art = FailingTest(kind="failing_test", test_path="tests/nope.py",
                      test_name="test_x", defect_id="D-004")
    result = validate_failing_test(art, tmp_path)
    assert not result.accepted
    assert "does not exist" in result.reason


def test_a_missing_test_name_is_rejected(tmp_path):
    _write(tmp_path, "tests/test_bug.py", """
        def test_other():
            assert 1 == 2
    """)
    art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                      test_name="test_absent", defect_id="D-004")
    result = validate_failing_test(art, tmp_path)
    assert not result.accepted
    assert "collected no test" in result.reason


def test_a_syntax_error_in_the_test_file_is_rejected_with_an_accurate_reason(tmp_path):
    _write(tmp_path, "tests/test_bug.py", """
        def test_reproduces(:
            assert 1 == 1
    """)
    art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                      test_name="test_reproduces", defect_id="D-004")
    result = validate_failing_test(art, tmp_path)
    assert not result.accepted
    # Not the name-typo message -- the file itself never imported, so
    # "check the test name" would be false.
    assert "collected no test" not in result.reason
    assert "did not import cleanly" in result.reason
    assert "SyntaxError" in result.reason


def test_a_failing_import_in_the_test_file_is_rejected_with_an_accurate_reason(tmp_path):
    _write(tmp_path, "tests/test_bug.py", """
        import nonexistent_module_charter_evidence_check

        def test_reproduces():
            assert 1 == 1
    """)
    art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                      test_name="test_reproduces", defect_id="D-004")
    result = validate_failing_test(art, tmp_path)
    assert not result.accepted
    assert "collected no test" not in result.reason
    assert "did not import cleanly" in result.reason
    assert "nonexistent_module_charter_evidence_check" in result.reason


def test_dispatch_rejects_an_artifact_of_the_wrong_kind(tmp_path):
    art = ChangeSummary(kind="change_summary", files=["a.py"],
                        decision_ref="D-1", summary="x")
    result = validate(ArtifactKind.FAILING_TEST, art, tmp_path)
    assert not result.accepted
    assert "expects a failing_test" in result.reason


def test_a_missing_pytest_is_rejected_not_accepted_as_a_failure(tmp_path, monkeypatch):
    """pytest absent from the interpreter must never read as 'the test failed'.

    `python -m pytest` exits 1 when pytest is not installed -- the same code a
    genuinely failing test produces. Trusting it would accept any submission as
    evidence on an interpreter without pytest, which is exactly how charter is
    installed by `uvx`. Not running is not the same as failing.
    """
    import charter.contracts.validators as v

    _write(tmp_path, "tests/test_bug.py", """
        def test_reproduces():
            assert 1 == 2
    """)
    bare = tmp_path / "bare_python"
    bare.write_text("#!/bin/sh\necho 'No module named pytest' >&2\nexit 1\n")
    bare.chmod(0o755)
    monkeypatch.setattr(v.sys, "executable", str(bare))

    art = FailingTest(kind="failing_test", test_path="tests/test_bug.py",
                      test_name="test_reproduces", defect_id="D-004")
    result = v.validate_failing_test(art, tmp_path)
    assert not result.accepted, "a missing pytest must never count as evidence"
    assert "pytest" in result.reason.lower()
