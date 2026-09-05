"""The acceptance test that matters: a full governed build, driven the way a
calling agent drives it, surviving a total loss of in-memory state."""
import textwrap
from charter.mcp_server import Handlers
import json


def _seed(repo):
    (repo / "app.py").write_text("def login(u):\n    return f\"SELECT {u}\"\n")
    # An empty root conftest.py puts the repo root on sys.path, so the seeded
    # test can `import app`. Without it pytest exits 2 on a collection error
    # and the validator rejects the submission for the wrong reason.
    (repo / "conftest.py").write_text("")
    (repo / "tests").mkdir()
    # An f-string substitutes its value, so checking for a literal "{" (as an
    # earlier draft of this fixture did) can never fail regardless of whether
    # login() is vulnerable -- it isn't a real regression test for the SQL
    # injection defect. Assert instead that a malicious payload does not
    # survive verbatim into the constructed query, which genuinely fails
    # against today's raw string interpolation.
    (repo / "tests" / "test_login.py").write_text(textwrap.dedent("""
        def test_login_is_parameterised():
            from app import login
            payload = "x' OR '1'='1"
            assert payload not in login(payload)
    """))


def test_a_full_governed_build_reaches_done(tmp_path):
    """The v2 flow: the developer works in the main session, the reviewing
    roles sign off from their own. Two Handlers means two connection ids,
    which is what the independence gate is checking."""
    _seed(tmp_path)
    main = Handlers(tmp_path)          # where the code gets written
    review = Handlers(tmp_path)        # a separate charter session
    assert main.connection_id != review.connection_id

    main.init(idea="harden the login path", methodology="scrum")

    # RED: QA proves the defect exists before anyone fixes it.
    assert json.loads(review.next())["assignment"]["role"] == "qa"
    assert json.loads(review.submit("qa", {
        "kind": "failing_test", "test_path": "tests/test_login.py",
        "test_name": "test_login_is_parameterised", "defect_id": "D-1"}))["accepted"]

    # GREEN: the developer answers it, in the main session.
    assert json.loads(main.next())["assignment"]["role"] == "developer"
    assert json.loads(main.submit("developer", {
        "kind": "change_summary", "files": ["app.py"],
        "decision_ref": "D-1", "summary": "login query built from raw input"}))["accepted"]

    assert json.loads(review.next())["assignment"]["role"] == "appsec"
    assert json.loads(review.submit("appsec", {
        "kind": "threat_entry", "cwe_id": "CWE-89",
        "attack_path": "login() interpolates the username straight into SQL, so "
                       "a crafted username changes the query.",
        "affected_files": ["app.py"]}))["accepted"]

    assert json.loads(review.next())["kind"] == "done"


def test_one_session_playing_every_role_is_refused(tmp_path):
    """v1's whole gap: one agent writing, reviewing and approving its own work.

    This is the assertion v2 exists for -- it passed silently in v1.
    """
    _seed(tmp_path)
    solo = Handlers(tmp_path)
    solo.init(idea="harden the login path", methodology="scrum")

    solo.next()
    assert json.loads(solo.submit("qa", {
        "kind": "failing_test", "test_path": "tests/test_login.py",
        "test_name": "test_login_is_parameterised", "defect_id": "D-1"}))["accepted"]

    solo.next()
    assert json.loads(solo.submit("developer", {
        "kind": "change_summary", "files": ["app.py"],
        "decision_ref": "D-1", "summary": "login query built from raw input"}))["accepted"]

    # appsec now reviews the developer's work from the SAME process
    solo.next()
    result = json.loads(solo.submit("appsec", {
        "kind": "threat_entry", "cwe_id": "CWE-89",
        "attack_path": "login() interpolates the username straight into SQL, so "
                       "a crafted username changes the query.",
        "affected_files": ["app.py"]}))
    assert not result["accepted"]
    assert "same process" in result["reason"]
    assert "appsec" not in json.loads(solo.status())["signed_off"]


def test_the_build_survives_losing_every_bit_of_memory(tmp_path):
    _seed(tmp_path)
    Handlers(tmp_path).init(idea="harden the login path", methodology="scrum")

    warm = Handlers(tmp_path)
    warm.next()
    warm.submit("qa", {"kind": "failing_test", "test_path": "tests/test_login.py",
                       "test_name": "test_login_is_parameterised",
                       "defect_id": "D-1"})
    del warm

    cold = Handlers(tmp_path)               # brand-new object, nothing shared
    assert json.loads(cold.next())["assignment"]["role"] == "developer"
    assert json.loads(cold.status())["signed_off"] == ["qa"]
