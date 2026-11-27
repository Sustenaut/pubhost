"""Steps for pubhost's use of pubrules: the names it imports from pubrules.api,
which its README lists and the installed pubrules.api must export."""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

from pytest_bdd import parsers, scenarios, then, when

scenarios("pubrules.feature")

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "pubhost"


@when("I read every import of pubrules in src/pubhost", target_fixture="imported")
def imports():
    found = set()
    for path in sorted(SOURCE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module \
                    and node.module.split(".")[0] == "pubrules":
                found |= {f"{node.module}.{a.name}" for a in node.names}
            elif isinstance(node, ast.Import):
                assert not any(a.name.split(".")[0] == "pubrules" for a in node.names), \
                    f"{path}: import pubrules names nothing; take the names with from"
    assert found
    return found


def listed():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("## What pubhost takes from pubrules", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"`(pubrules(?:\.[A-Za-z_]+)+)`", section))


@then(parsers.parse('each is one the README lists under "{heading}"'))
def all_listed(imported, heading):
    missing = imported - listed()
    assert not missing, f"imported from pubrules but not listed under {heading}: {sorted(missing)}"


@then("the README lists none that pubhost does not import")
def none_extra(imported):
    extra = listed() - imported
    assert not extra, f"listed but not imported: {sorted(extra)}"


@then("each is from pubrules.api")
def from_api(imported):
    elsewhere = sorted(name for name in imported if name.rpartition(".")[0] != "pubrules.api")
    assert not elsewhere, f"imported from pubrules but not from pubrules.api: {elsewhere}"


@then("the installed pubrules.api exports each of them")
def installed(imported):
    exported = set(importlib.import_module("pubrules.api").__all__)
    missing = sorted(name for name in imported if name.rpartition(".")[2] not in exported)
    assert not missing, f"pubrules.api does not export {missing}"


# The hosting block's maps, whose keys are names the repository chooses
# (a provider, a zone, a site, a DKIM selector, a verification token, a
# DNSSEC provider), not settings.
NAMED = {("providers",), ("zones",), ("zones", "*", "sites"), ("providers", "*", "dkim"),
         ("zones", "*", "email", "verification"), ("zones", "*", "dnssec", "keys")}
TESTDATA = ROOT / "terraform" / "testdata" / "pubrules.json"
VARIABLES = ROOT / "terraform" / "hosting" / "variables.tf"


def settings_named(value, path=()):
    """Every setting the block names, by its key, below the maps of names."""
    if not isinstance(value, dict):
        return set()
    out = set()
    named = path in NAMED
    for key, inner in value.items():
        if not named:
            out.add(key)
        out |= settings_named(inner, (*path, "*" if named else key))
    return out


@when("pubrules' hosting check reads terraform/testdata/pubrules.json", target_fixture="checked")
def hosting_check():
    import json  # noqa: PLC0415

    from pubrules.api import hosting_settings  # noqa: PLC0415
    return hosting_settings(json.loads(TESTDATA.read_text(encoding="utf-8")))


@then("it accepts it")
def accepted(checked):
    assert checked.get("zones"), checked


@then("every setting it names is one the hosting module's config variable declares")
def declared(checked):
    text = VARIABLES.read_text(encoding="utf-8")
    block = text.split('variable "config"', 1)[1].split('\nvariable "', 1)[0]
    attributes = set(re.findall(r"^\s*([a-z_]+)\s*=", block, re.MULTILINE))
    missing = settings_named(checked) - attributes
    assert not missing, f"pubrules.api.hosting_settings accepts settings the hosting module drops: {sorted(missing)}"
