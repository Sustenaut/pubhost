"""Steps for terraform.yml's tf_vars: its input, and its step's script run as the runner
runs it, with bash, writing to a GITHUB_ENV file in the scratch directory."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import yaml
from pubtest.core import Result
from pytest_bdd import parsers, scenarios, then, when

scenarios("terraform_workflow.feature")

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "terraform.yml"
STEP = "Give Terraform the repository variables tf_vars names"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step() -> dict:
    (found,) = [s for s in workflow()["jobs"]["terraform"]["steps"] if s.get("name") == STEP]
    return found


def calls(data: dict) -> dict:
    # PyYAML reads the key `on` as True.
    return (data.get("on") or data.get(True))["workflow_call"]


@when(parsers.parse('the workflow\'s input "{name}" is read'))
def input_read(pubtest_ctx, name):
    pubtest_ctx.attempt(lambda: calls(workflow())["inputs"][name])


@when("the tf_vars step's condition is read")
def condition_read(pubtest_ctx):
    pubtest_ctx.attempt(lambda: step()["if"])


@when(parsers.parse('the tf_vars step runs with tf_vars "{names}" and the variables:'))
def step_runs(pubtest_ctx, names, docstring):
    env_file = Path(pubtest_ctx.directory) / "github_env"
    env_file.write_text("")
    pubtest_ctx.env_file = env_file
    env = {**os.environ, "NAMES": names, "VARS": json.dumps(json.loads(docstring)), "GITHUB_ENV": str(env_file)}
    done = subprocess.run(["bash", "-e", "-c", step()["run"]], env=env, capture_output=True, text=True,
                          cwd=pubtest_ctx.directory, check=False)
    pubtest_ctx.ran(Result(value=None, code=done.returncode, stdout=done.stdout, stderr=done.stderr,
                           argv=["bash", STEP]))


def environment(pubtest_ctx) -> dict[str, str]:
    """GITHUB_ENV as the runner reads it: NAME=value lines, and NAME<<DELIMITER blocks."""
    lines, out = pubtest_ctx.env_file.read_text().split("\n"), {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line:
            name, delimiter = line.split("<<", 1)
            end = lines.index(delimiter, i + 1)
            out[name] = "\n".join(lines[i + 1:end])
            i = end + 1
        elif "=" in line:
            name, value = line.split("=", 1)
            out[name] = value
            i += 1
        else:
            i += 1
    return out


@then(parsers.parse('Terraform gets "{name}" as:'))
def gets_block(pubtest_ctx, name, docstring):
    assert environment(pubtest_ctx).get(name) == docstring, environment(pubtest_ctx)


@then(parsers.parse('Terraform gets "{name}" as "{value}"'))
def gets(pubtest_ctx, name, value):
    assert environment(pubtest_ctx).get(name) == value, environment(pubtest_ctx)


@then(parsers.parse('Terraform gets no "{name}"'))
def gets_no(pubtest_ctx, name):
    assert name not in environment(pubtest_ctx), environment(pubtest_ctx)
