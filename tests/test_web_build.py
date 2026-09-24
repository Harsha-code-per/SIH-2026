"""The interface must not load anything from outside.

The container has no route to the internet, but the *browser* does. A font from
Google Fonts or a script from a CDN would be fetched by the user's browser
directly, bypassing every egress control the stack has -- and would appear in
nobody's egress monitor. These checks keep D-13 true for the browser as well as
the server.

HTML and CSS are where external loads live. JavaScript bundles legitimately
contain URL strings -- licence headers, documentation links in error messages --
so they are not scanned; the runtime check is the browser's network panel,
recorded in docs/playbooks/verify-containment.md.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# A reference that makes the browser fetch from another host.
EXTERNAL = re.compile(
    r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//"""      # <script src="//cdn…">
    r"""|url\(\s*["']?\s*(?:https?:)?//"""                 # url(https://…)
    r"""|@import\s+(?:url\()?\s*["']?\s*(?:https?:)?//""",  # @import "https://…"
    re.I)

# The xmlns in an inline SVG data URI is a namespace, not a fetch.
ALLOWED = ("http://www.w3.org/2000/svg",)


def _offending(text: str) -> list[str]:
    hits = []
    for m in EXTERNAL.finditer(text):
        window = text[m.start():m.start() + 120]
        if not any(a in window for a in ALLOWED):
            hits.append(window.split("\n")[0][:100])
    return hits


def _check(paths):
    found = []
    for p in paths:
        for hit in _offending(p.read_text(errors="replace")):
            found.append(f"{p.relative_to(ROOT)}: {hit}")
    return found


def test_the_source_references_no_external_host():
    """Catches a CDN link or a Google Fonts import being added by hand."""
    web = ROOT / "web"
    paths = [web / "index.html", *(web / "src").rglob("*.css")]
    assert not (found := _check(paths)), f"external references in source: {found}"


def test_the_build_references_no_external_host():
    """Catches a dependency that injects one at build time."""
    static = ROOT / "static"
    if not (static / "index.html").exists():
        # Built by `make web`, `make dev` or the Docker image. Without a build
        # there is nothing to scan; the source check above still runs.
        return
    paths = [static / "index.html", *static.rglob("*.css")]
    assert not (found := _check(paths)), f"external references in build: {found}"


def test_fonts_are_bundled_not_fetched():
    css = (ROOT / "web" / "src" / "index.css").read_text()
    assert "@fontsource" in css, "fonts must come from a bundled package"
    assert "fonts.googleapis" not in css and "fonts.gstatic" not in css


def test_the_pattern_catches_what_it_should():
    """The check is only worth having if it fires. Negative controls."""
    for bad in ('<script src="https://cdn.jsdelivr.net/x.js">',
                '<link href="//fonts.googleapis.com/css2?family=Inter">',
                '@import url("https://fonts.googleapis.com/css")',
                "background: url(https://example.com/a.png)"):
        assert _offending(bad), f"missed {bad!r}"
    for ok in ('<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\'">',
               '<script type="module" src="/assets/index.js">',
               "background: url(/assets/a.png)"):
        assert not _offending(ok), f"false positive on {ok!r}"
