import pytest

from tools.filesystem import MAX_DIR_ENTRIES, MAX_READ_LINES, make_filesystem_tools


@pytest.fixture
def fs(executor):
    read_file, edit_file, write_file, list_dir = make_filesystem_tools(executor)
    return {"read": read_file, "edit": edit_file, "write": write_file, "ls": list_dir}


# ---- read_file -------------------------------------------------------------------
def test_read_empty(fs, write):
    write("empty.md", "")
    assert fs["read"]("empty.md") == "empty.md is empty."


def test_read_line_numbers(fs, write):
    write("a.txt", "one\ntwo\nthree\n")
    out = fs["read"]("a.txt")
    assert "(lines 1-3 of 3)" in out
    assert "    2| two" in out


def test_read_chunking(fs, write):
    write("big.txt", "".join(f"line {i}\n" for i in range(1, 1001)))
    out = fs["read"]("big.txt")
    assert f"(lines 1-{MAX_READ_LINES} of 1000)" in out
    assert f"start_line={MAX_READ_LINES + 1}" in out
    out2 = fs["read"]("big.txt", start_line=990)
    assert "(lines 990-1000 of 1000)" in out2
    assert "more lines" not in out2


def test_read_past_end(fs, write):
    write("a.txt", "x\n")
    assert fs["read"]("a.txt", start_line=5).startswith("Error:")


def test_read_crlf_shows_clean_lines(fs, write):
    write("c.txt", "a\r\nb\r\n")
    out = fs["read"]("c.txt")
    assert "\r" not in out
    assert "(lines 1-2 of 2)" in out


def test_read_form_feed_does_not_split(fs, write):
    write("ff.txt", "a\x0cb\nc\n")
    assert "(lines 1-2 of 2)" in fs["read"]("ff.txt")


def test_read_missing(fs):
    assert "file not found" in fs["read"]("nope.txt")


def test_read_escape_is_error_string(fs):
    out = fs["read"]("../../.env")
    assert out.startswith("Error:") and "outside the workspace" in out


def test_read_directory_is_error_string(fs, write):
    write("d/x.txt", "x")
    assert fs["read"]("d").startswith("Error:")


# ---- edit_file -------------------------------------------------------------------
def test_edit_single_match(fs, write, tmp_path):
    write("e.py", "x = 1\ny = 2\n")
    assert fs["edit"]("e.py", "y = 2", "y = 3").startswith("Edited")
    assert (tmp_path / "e.py").read_text() == "x = 1\ny = 3\n"


def test_edit_no_match(fs, write):
    write("e.py", "x = 1\n")
    assert "not found" in fs["edit"]("e.py", "z = 9", "z = 0")


def test_edit_multiple_matches(fs, write, tmp_path):
    write("d.py", "print('a')\nprint('a')\n")
    assert "matches 2 places" in fs["edit"]("d.py", "print('a')", "print('b')")
    assert (tmp_path / "d.py").read_text() == "print('a')\nprint('a')\n"  # untouched


def test_edit_empty_old_str(fs, write):
    write("e.py", "x\n")
    assert fs["edit"]("e.py", "", "y").startswith("Error:")


def test_edit_preserves_crlf(fs, write, tmp_path):
    write("c.txt", "one\r\ntwo\r\nthree\r\n")
    assert fs["edit"]("c.txt", "two\nthree", "TWO\nTHREE").startswith("Edited")
    assert (tmp_path / "c.txt").read_bytes() == b"one\r\nTWO\r\nTHREE\r\n"


def test_edit_keeps_lf(fs, write, tmp_path):
    write("l.txt", "a\nb\n")
    fs["edit"]("l.txt", "b", "c")
    assert b"\r" not in (tmp_path / "l.txt").read_bytes()


# ---- write_file ------------------------------------------------------------------
def test_write_new(fs, tmp_path):
    assert fs["write"]("new/file.md", "# hi\n").startswith("Wrote")
    assert (tmp_path / "new" / "file.md").read_text() == "# hi\n"


def test_write_refuses_overwrite(fs, write, tmp_path):
    write("a.md", "keep")
    assert "already exists" in fs["write"]("a.md", "replace")
    assert (tmp_path / "a.md").read_text() == "keep"


def test_write_overwrite_opt_in(fs, write, tmp_path):
    write("a.md", "old")
    fs["write"]("a.md", "new", overwrite=True)
    assert (tmp_path / "a.md").read_text() == "new"


def test_write_escape_is_error(fs):
    assert "outside the workspace" in fs["write"]("../evil.txt", "x")


# ---- list_dir --------------------------------------------------------------------
def test_list_folders_first_and_ignored(fs, write):
    write("b.txt", "")
    write("a_dir/x.txt", "")
    write("node_modules/junk.js", "")
    write(".git/HEAD", "")
    assert fs["ls"]().split("\n") == ["a_dir/", "b.txt"]


def test_list_recursive(fs, write):
    write("top.txt", "")
    write("src/a.py", "")
    write("src/sub/b.py", "")
    write("node_modules/junk.js", "")
    lines = fs["ls"](".", recursive=True).split("\n")
    assert set(lines) == {"src/", "top.txt", "src/sub/", "src/a.py", "src/sub/b.py"}


def test_list_recursive_subdir(fs, write):
    write("src/a.py", "")
    write("src/sub/b.py", "")
    lines = fs["ls"]("src", recursive=True).split("\n")
    assert set(lines) == {"sub/", "a.py", "sub/b.py"}


def test_list_cap(fs, write):
    for i in range(MAX_DIR_ENTRIES + 5):
        write(f"f{i:04}.txt", "")
    out = fs["ls"]()
    assert "[... 5 more entries]" in out


def test_list_empty(fs, tmp_path):
    (tmp_path / "empty").mkdir()
    assert fs["ls"]("empty") == "(empty directory)"


def test_list_escape(fs):
    assert "outside the workspace" in fs["ls"]("..")


def test_list_on_file(fs, write):
    write("f.txt", "")
    assert fs["ls"]("f.txt").startswith("Error:")
