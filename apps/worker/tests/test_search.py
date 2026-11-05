import pytest

from tools.search import make_search_tools


@pytest.fixture
def search(executor):
    (search_code,) = make_search_tools(executor)
    return search_code


def test_finds_match(search, write):
    write("src/calc.py", "def add(a, b):\n    return a + b\n")
    out = search("def add")
    assert "src/calc.py:1:def add(a, b):" in out


def test_no_match(search, write):
    write("a.py", "x = 1\n")
    assert search("nothing_here").startswith("No matches")


def test_file_glob(search, write):
    write("a.py", "needle\n")
    write("b.md", "needle\n")
    out = search("needle", file_glob="*.py")
    assert "a.py" in out and "b.md" not in out


def test_excluded_dirs(search, write):
    write("node_modules/x.js", "needle\n")
    write("src/y.js", "needle\n")
    out = search("needle")
    assert "node_modules" not in out and "src/y.js" in out


@pytest.mark.parametrize("pattern", ["$(echo pwned)", "'; echo pwned; '", "-v", "a|b", '"quoted"'])
def test_special_patterns_are_safe(search, write, pattern):
    write("a.txt", "plain text\n")
    out = search(pattern)
    assert "pwned" not in out or out.startswith("No matches")


def test_pattern_starting_with_dash_matches_literally(search, write):
    write("a.txt", "--flag here\n")
    assert "a.txt:1:--flag here" in search("--flag")


def test_path_escape_rejected(search):
    assert "outside the workspace" in search("x", path="..")


def test_empty_pattern(search):
    assert search("").startswith("Error:")
