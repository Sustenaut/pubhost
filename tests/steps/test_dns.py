"""Steps for `pubhost dns check`, against a fake `dig` and `delv` among
pubtest's stand-ins that answer from a JSON file: each nameserver's records,
whether it serves the zone, and the key it signs with. The fake delv
validates an answer when the nameserver's signing key is among the trust
anchors it is given. Each run is recorded in the stand-ins' log, so
pubtest's stand-in steps read them."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pubtest.steps.standins import standins
from pytest_bdd import given, parsers, scenarios, then, when

from pubhost import dns as check

scenarios("dns.feature")

TESTDATA = Path(__file__).resolve().parents[2] / "terraform" / "testdata" / "pubrules.json"

FAKE_DIG = f"""#!{sys.executable}
import json, os, sys
state = json.load(open(os.environ["FAKE_DNS"]))
args = sys.argv[1:]
with open(os.environ["FAKE_DNS_LOG"], "a") as log:
    log.write(json.dumps({{"name": "dig", "args": args}}) + "\\n")
if "+short" in args:
    print("\\n".join(state["resolved"]))
    sys.exit(0)
server = next(a[1:] for a in args if a.startswith("@"))
name, rtype = args[args.index("-q") + 1], args[args.index("-t") + 1]
at = state["servers"].get(server)
if not at or not at["serves"]:
    print(";; ->>HEADER<<- opcode: QUERY, status: REFUSED, id: 1")
    print(";; flags: qr; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 1")
    sys.exit(0)
values = at["records"].get(f"{{name}} {{rtype}}", [])
print(";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1")
print(f";; flags: qr aa; QUERY: 1, ANSWER: {{len(values)}}, AUTHORITY: 0, ADDITIONAL: 1")
print()
print(";; ANSWER SECTION:")
for value in values:
    print(f"{{name}}\\t300\\tIN\\t{{rtype}}\\t{{value}}")
"""

FAKE_DELV = f"""#!{sys.executable}
import json, os, sys
state = json.load(open(os.environ["FAKE_DNS"]))
args = sys.argv[1:]
with open(os.environ["FAKE_DNS_LOG"], "a") as log:
    log.write(json.dumps({{"name": "delv", "args": args}}) + "\\n")
anchors = open(args[args.index("-a") + 1]).read()
server = next(a[1:] for a in args if a.startswith("@"))
name, rtype = args[args.index("-q") + 1], args[args.index("-t") + 1]
at = state["servers"].get(server, {{}})
if not at.get("serves") or not at.get("signed_by") or at["signed_by"] not in anchors:
    print(f";; validating {{name}}/{{rtype}}: got insecure response; parent indicates it should be secure")
    print(f";; resolution failed: insecurity proof failed")
elif any(key.startswith(name + " ") for key in at["records"]):
    print("; fully validated")
else:
    print("; negative response, fully validated")
"""


@pytest.fixture
def dns(pubtest_ctx, tmp_path, monkeypatch):
    """The fake DNS's state file, with `dig` and `delv` among the stand-ins."""
    found = standins(pubtest_ctx, tmp_path)
    for name, text in (("dig", FAKE_DIG), ("delv", FAKE_DELV)):
        (found.bin / name).write_text(text)
        (found.bin / name).chmod(0o755)
    state = tmp_path / "dns.json"
    state.write_text(json.dumps({"resolved": [], "servers": {}}))
    monkeypatch.setenv("FAKE_DNS", str(state))
    monkeypatch.setenv("FAKE_DNS_LOG", str(found.log))
    return state


def _edit(dns, change):
    state = json.loads(dns.read_text())
    change(state)
    dns.write_text(json.dumps(state))


def _hosting():
    return json.loads(TESTDATA.read_text())["hosting"]


@given('every nameserver of "example.net" serves it alike')
def example_net(dns):
    """deSEC's nameservers, from pubrules.json, and Cloudflare's, which the
    resolver finds: each serves every key and signs with its provider's."""
    keys = _hosting()["zones"]["example.net"]["dnssec"]["keys"]
    desec = ["ns1.desec.io.", "ns2.desec.org."]
    cloudflare = ["ns1.cloudflare.example.", "ns2.cloudflare.example."]
    records = {
        "example.net. NS": sorted(desec + cloudflare),
        "example.net. A": ["192.0.2.2"],
        "example.net. DNSKEY": keys["desec"] + keys["cloudflare"],
    }

    def change(state):
        state["resolved"] = cloudflare
        for server in desec + cloudflare:
            signer = keys["desec" if server in desec else "cloudflare"][0]
            state["servers"][server] = {"serves": True, "signed_by": signer.split(" ")[3],
                                        "records": dict(records)}
    _edit(dns, change)


@given('every nameserver of "example.org" serves it alike')
def example_org(dns):
    """Hetzner's external nameservers, from pubrules.json, unsigned."""
    servers = _hosting()["providers"]["hetzner"]["dns"]["external_nameservers"]
    records = {
        "example.org. NS": servers,
        "auth.example.org. A": ["192.0.2.2"],
        "docs.example.org. A": ["192.0.2.2"],
    }

    def change(state):
        state["resolved"] = servers
        for server in servers:
            state["servers"][server] = {"serves": True, "signed_by": None, "records": dict(records)}
    _edit(dns, change)


@given(parsers.parse('"{server}" answers "{rrset}" with "{values}"'))
def answers(dns, server, rrset, values):
    def change(state):
        state["servers"][server]["records"][rrset] = values.split(", ")
    _edit(dns, change)


@given(parsers.parse('"{server}" does not serve the zone'))
def refuses(dns, server):
    def change(state):
        state["servers"][server]["serves"] = False
    _edit(dns, change)


@given(parsers.parse('"{server}" also serves the key "{key}"'))
def extra_key(dns, server, key):
    def change(state):
        state["servers"][server]["records"]["example.net. DNSKEY"].append(key)
    _edit(dns, change)


@given(parsers.parse('"{server}" does not serve the {provider} keys'))
def lacks_keys(dns, server, provider):
    keys = set(_hosting()["zones"]["example.net"]["dnssec"]["keys"][provider])

    def change(state):
        rrset = state["servers"][server]["records"]["example.net. DNSKEY"]
        state["servers"][server]["records"]["example.net. DNSKEY"] = [k for k in rrset if k not in keys]
    _edit(dns, change)


@given(parsers.parse('"{server}" signs with a key pubrules.json does not pin'))
def unpinned_signer(dns, server):
    def change(state):
        state["servers"][server]["signed_by"] = "c29tZXRoaW5nIGVsc2U="
    _edit(dns, change)


def _asked(pubtest_ctx):
    """What each run of delv asked: the nameserver, the name and the root."""
    asked = []
    for args in pubtest_ctx.standins.runs("delv"):
        asked.append({"server": next(a[1:] for a in args if a.startswith("@")), "name": args[args.index("-q") + 1],
                      "root": next(a for a in args if a.startswith("+root="))})
    return asked


@then(parsers.parse('delv asked each of the {count:d} nameservers alone for a name that does not exist, '
                    'with "{zone}" as its root'))
def asked_missing(pubtest_ctx, count, zone):
    asked = [q for q in _asked(pubtest_ctx) if q["name"].startswith("pubhost-check-")]
    assert len({q["server"] for q in asked}) == count == len(asked), asked
    assert len({q["name"] for q in asked}) == 1, asked
    assert all(q["name"].endswith(f".{zone}.") and q["root"] == f"+root={zone}." for q in asked), asked


@when(parsers.parse('the rrsets to compare for "{zone}" are listed'))
def compared(ctx, zone):
    hosting = _hosting()
    ctx.attempt(lambda: ", ".join(f"{name} {rtype}" for name, rtype in
                                  check.rrsets(hosting["zones"][zone], hosting["providers"], [])))
