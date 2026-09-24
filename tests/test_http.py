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
