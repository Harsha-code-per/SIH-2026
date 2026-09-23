"""The documentation must not lie about the code.

AGENTS.md and docs/ are the project's memory -- the context any agent or
teammate starts from. A path that no longer exists, a make target that was
renamed or a decision number that does not resolve sends the next reader
somewhere wrong, which is worse than no documentation. These checks keep the
references honest as the code moves.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOCS = [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "CLAUDE.md",
        *sorted((ROOT / "docs").rglob("*.md"))]

def _is_runtime(path: str) -> bool:
    """Is this path created at runtime rather than committed?

    Anything git ignores is runtime state by definition, so it is legitimately
    absent from a fresh clone. A hardcoded list passed on the machine that wrote
    it -- where the index, the audit log and the signing key all existed -- and
    failed on the first clean clone.
    """
    import subprocess
    # Both forms: a directory-only pattern like "data/models/" only matches a
    # path git can tell is a directory, which a nonexistent one is not unless
    # it keeps its trailing slash.
    for candidate in {path, path.rstrip("/")}:
        if subprocess.run(["git", "check-ignore", "-q", candidate],
                          cwd=ROOT, capture_output=True).returncode == 0:
            return True
    return False


def _text(p: Path) -> str:
    return p.read_text()


def test_every_referenced_path_exists():
    missing = []
    for d in DOCS:
        for m in re.finditer(r"`((?:app|docs|tests|scripts|static|egress|data|sandbox)/[\w./-]+?)(?:::\w+)?`",
                             _text(d)):
            path = m.group(1).rstrip(".")
            if "*" in path or "<" in path or _is_runtime(path):
                continue
            if not (ROOT / path).exists():
                missing.append(f"{d.name}: {path}")
    assert not missing, f"documented paths that do not exist: {missing}"


def test_every_make_target_exists():
    mk = (ROOT / "Makefile").read_text()
    targets = set(re.findall(r"^([a-z][a-z-]*)(?:\s+[a-z-]+)*\s*:", mk, re.M))
    targets |= set(re.findall(r"^[a-z][a-z-]* ([a-z][a-z-]*)\s*:", mk, re.M))
    unknown = [f"{d.name}: make {t}" for d in DOCS
               for t in re.findall(r"`make ([a-z-]+)", _text(d)) if t not in targets]
    assert not unknown, f"documented make targets that do not exist: {unknown}"


def test_every_decision_reference_is_defined():
    defined = set(re.findall(r"^### (D-\d+)", _text(ROOT / "docs" / "DECISIONS.md"), re.M))
    undefined = [f"{d.name}: {r}" for d in DOCS
                 for r in set(re.findall(r"\b(D-\d+)\b", _text(d))) if r not in defined]
    assert not undefined, f"decision references with no entry: {undefined}"


def test_decision_numbers_are_unique_and_sequential():
    nums = [int(n) for n in re.findall(r"^### D-(\d+)",
                                       _text(ROOT / "docs" / "DECISIONS.md"), re.M)]
    assert len(nums) == len(set(nums)), "duplicate decision numbers"
    assert nums == list(range(1, len(nums) + 1)), "decisions must run D-1, D-2, ..."


def test_every_named_function_exists():
    missing = []
    for d in DOCS:
        for f, fn in re.findall(r"`(app/\w+\.py)::(\w+)`", _text(d)):
            src = (ROOT / f).read_text()
            if not re.search(rf"\b(def|class)\s+{fn}\b|^{fn}\s*=|\b{fn}\s*=", src, re.M):
                missing.append(f"{d.name}: {f}::{fn}")
    assert not missing, f"documented functions that do not exist: {missing}"


def test_markdown_links_resolve():
    broken = []
    for d in DOCS:
        for link in re.findall(r"\]\(([^)#]+?)\)", _text(d)):
            if not link.startswith("http") and not (d.parent / link).exists():
                broken.append(f"{d.name}: {link}")
    assert not broken, f"broken links: {broken}"


def test_every_playbook_has_a_skill_wrapper_and_vice_versa():
    """Playbooks are the source; the Claude skills only point at them."""
    books = {p.stem for p in (ROOT / "docs" / "playbooks").glob("*.md")}
    skills = {p.parent.name for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")}
    assert books == skills, f"playbooks without skills: {books - skills}; " \
                            f"skills without playbooks: {skills - books}"
    for s in skills:
        body = (ROOT / ".claude" / "skills" / s / "SKILL.md").read_text()
        assert f"docs/playbooks/{s}.md" in body, f"skill {s} does not point at its playbook"


def test_documented_test_count_is_current():
    """AGENTS.md and README quote a test count; it drifts every time a test is
    added. Count the real thing."""
    import importlib.util
    total = 0
    for f in sorted((ROOT / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(f"_count_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        total += sum(1 for n in vars(mod) if n.startswith("test_") and callable(getattr(mod, n)))
    for d in (ROOT / "AGENTS.md", ROOT / "README.md"):
        quoted = {int(n) for n in re.findall(r"\b(\d{2,4})\s+(?:currently|passing)", _text(d))}
        assert not quoted or quoted == {total}, \
            f"{d.name} quotes {quoted} tests; there are {total}"
