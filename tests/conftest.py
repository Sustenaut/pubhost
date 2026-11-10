"""pubhost's suite. The steps it does not define here (`it succeeds`, `it
prints ...`) are pubkit's plugin's.

Steps and fixtures more than one steps module uses live here: the scratch
repository, running the `pubhost` command in it, and its files. pytest-bdd
registers a step only in the module that defines it, or in a conftest.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, when


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    return root


def pubhost():
    """The `pubhost` installed beside the Python running this suite."""
    found = shutil.which("pubhost", path=str(Path(sys.executable).parent))
    assert found, "pubhost is not installed in this environment; run `make venv`"
    return found


@given("an empty repository")
def empty(repo):
    pass


@given(parsers.parse('the file "{path}" reads "{text}"'))
@when(parsers.parse('the file "{path}" reads "{text}"'))
def file_reads(repo, path, text):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n")


@pytest.fixture
def env():
    return {}


@when(parsers.re(r'I run pubhost (?P<args>(?:"[^"]*" ?)+)'), target_fixture="result")
def run_pubhost(repo, run, env, args):
    variables = {k: v for k, v in env.items() if k != "resolved"}
    return run(pubhost(), *args.strip().strip('"').split('" "'), cwd=repo, env=variables)
