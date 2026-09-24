"""HTTP behaviour that the browser, not the server, would otherwise decide.

A downloaded document was served from the browser's cache to a request with no
token: the API sent no Cache-Control, so the browser kept an authenticated
response and reused it. These run against the real application in-process.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_every_api_response_forbids_caching():
    for path in ("/api/status", "/api/conversations", "/api/download/nothing.docx"):
        r = client.get(path)
        assert r.headers.get("cache-control") == "no-store", \
            f"{path} ({r.status_code}) is cacheable: {r.headers.get('cache-control')}"


def test_errors_are_not_cacheable_either():
    """A cached 401 would be harmless; a cached 200 is not. Check the rule
    applies whatever the status, so no code path is missed."""
    r = client.get("/api/conversations")
    assert r.status_code == 401 and r.headers.get("cache-control") == "no-store"


def test_the_interface_itself_stays_cacheable():
    r = client.get("/")
    assert r.headers.get("cache-control") != "no-store"


def test_unknown_api_paths_404_rather_than_serving_the_app():
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and "json" in r.headers.get("content-type", "")


def test_deep_links_serve_the_app():
    r = client.get("/c/anything")
    assert r.status_code == 200 and "text/html" in r.headers.get("content-type", "")


def test_status_names_the_local_model_for_every_tier():
    """The pitch that local inference is one config change rests on each tier
    already naming its on-premise model."""
    status = client.get("/api/status").json()
    for m in status["models"]:
        assert m["modes"].get("sovereign"), f"{m['id']} has no on-premise model"
        assert m["modes"][status["mode"]] == m["name"]


def test_status_shows_where_each_rule_routes():
    """The Models view draws the routing table from this; a rule without its
    target would render as a reason with no destination."""
    rules = client.get("/api/status").json()["rules"]
    assert rules and all("if" in r and "then" in r for r in rules)
    math = next(r for r in rules if r["name"] == "deterministic-math")
    assert math["then"]["tier"] == "L0" and math["if"] == {"task": "arithmetic"}


def test_run_refuses_a_model_outside_the_registry():
    """The picker's value reaches the server as free text; only registry ids
    may be run, so nothing can name an arbitrary hosted model."""
    import time
    from app.auth import USERS, User
    # An in-memory user, never saved: the real account store is not touched.
    USERS.users["_picker_test"] = User(username="_picker_test", password="x", role="engineer")
    try:
        payload = f"_picker_test:1:{int(time.time() + 60)}"
        token = f"{payload}.{USERS._sign(payload)}"
        r = client.post("/api/run", data={"prompt": "hi", "model": "gpt-4o"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400, r.status_code
    finally:
        del USERS.users["_picker_test"]
