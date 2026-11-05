"""Check that Gemini sees clean tool schemas: no `executor` param, docstrings and params intact."""
import inspect

import pytest
from google import genai
from google.genai import types

from executor import LocalExecutor
from tools import build_tools

EXPECTED = {
    "read_file": {"path", "start_line", "end_line"},
    "edit_file": {"path", "old_str", "new_str"},
    "write_file": {"path", "content", "overwrite"},
    "list_dir": {"path", "recursive"},
    "search_code": {"pattern", "path", "file_glob"},
    "git_diff": set(),
}


@pytest.fixture
def tools(tmp_path):
    # bash_path is never used here; pass a dummy so the test doesn't need Git Bash.
    return build_tools(LocalExecutor(root=str(tmp_path), bash_path="bash"))


@pytest.fixture
def api_client():
    return genai.Client(api_key="test-key")._api_client  # no network call on construction


def test_tool_names(tools):
    assert [t.__name__ for t in tools] == list(EXPECTED)


@pytest.mark.parametrize("name", list(EXPECTED))
def test_schema(tools, api_client, name):
    fn = next(t for t in tools if t.__name__ == name)
    assert "executor" not in inspect.signature(fn).parameters

    decl = types.FunctionDeclaration.from_callable(client=api_client, callable=fn)
    assert decl.name == name
    assert decl.description and len(decl.description) > 20

    props = set((decl.parameters.properties or {}).keys()) if decl.parameters else set()
    assert props == EXPECTED[name]
