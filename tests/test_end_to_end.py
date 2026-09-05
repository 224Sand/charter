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
    _seed(tmp_path)
    h = Handlers(tmp_path)
    h.init(idea="harden the login path", methodology="scrum")

    assert json.loads(h.next())["assignment"]["role"] == "developer"
    assert json.loads(h.submit("developer", {
        "kind": "change_summary", "files": ["app.py"],
        "decision_ref": "D-1", "summary": "login query built from raw input"}))["accepted"]

    assert json.loads(h.next())["assignment"]["role"] == "qa"
    assert json.loads(h.submit("qa", {
        "kind": "failing_test", "test_path": "tests/test_login.py",
        "test_name": "test_login_is_parameterised", "defect_id": "D-1"}))["accepted"]

    assert json.loads(h.next())["assignment"]["role"] == "appsec"
    assert json.loads(h.submit("appsec", {
        "kind": "threat_entry", "cwe_id": "CWE-89",
        "attack_path": "login() interpolates the username straight into SQL, so "
                       "a crafted username changes the query.",
        "affected_files": ["app.py"]}))["accepted"]

    assert json.loads(h.next())["kind"] == "done"


def test_the_build_survives_losing_every_bit_of_memory(tmp_path):
    _seed(tmp_path)
    Handlers(tmp_path).init(idea="harden the login path", methodology="scrum")

    warm = Handlers(tmp_path)
    warm.next()
    warm.submit("developer", {"kind": "change_summary", "files": ["app.py"],
                              "decision_ref": "D-1", "summary": "raw input"})
    del warm

    cold = Handlers(tmp_path)               # brand-new object, nothing shared
    assert json.loads(cold.next())["assignment"]["role"] == "qa"
    assert json.loads(cold.status())["signed_off"] == ["developer"]
