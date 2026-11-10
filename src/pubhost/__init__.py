"""pubhost: what makes a repository's sites and zones exist and stay right
at the outside systems that serve them. Its Terraform modules (terraform/)
turn pubkit.json's hosting block into DNS, mail, DNSSEC, Cloud Run and
bucket resources; `pubhost dns check` compares a zone's nameservers live;
terraform.yml applies a stack from CI; the actions build an image
(docker-build) and deploy a static site (deploy-static), which first runs
`pubhost site check`.

It uses pubkit as a library, for the hosting block's shape (pubkit.hosting),
which `pubkit sync` checks; pubkit never imports it.
"""

from __future__ import annotations


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415
    try:
        return version("pubhost")
    except PackageNotFoundError:
        return "0+source"


__version__ = _version()
