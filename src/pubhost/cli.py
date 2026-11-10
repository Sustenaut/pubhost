"""pubhost: a repository's hosting, checked live.

    pubhost dns check ZONE [--record NAME/TYPE...]
    pubhost site check DIR [--url URL]

Each runs in the repository's root, where pubkit.json is. The Terraform
modules, terraform.yml and the deploy-static and docker-build actions are
used from the repository by commit (README).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from . import __version__


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pubhost", description=__doc__.split("\n")[0])
    parser.add_argument("--version", action="version", version=f"pubhost {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("dns", help="check a zone in pubkit.json's hosting block, live")
    dns = p.add_subparsers(dest="dns_command", required=True)
    p = dns.add_parser("check", help="every nameserver gives the same answers and, with dnssec, "
                                     "validates alone against the pinned keys")
    p.add_argument("zone", help="a zone in pubkit.json's hosting block, such as example.eu")
    p.add_argument("--record", action="append", default=[], metavar="NAME/TYPE",
                   help="another rrset to compare, such as www/A; repeat it")
    p = commands.add_parser("site", help="check a public site's built pages")
    site = p.add_subparsers(dest="site_command", required=True)
    p = site.add_parser("check", help="every page names itself, has an Open Graph card with a "
                                      "large enough image, and robots.txt lets preview bots in")
    p.add_argument("dir", type=Path, help="the built site, such as _site")
    p.add_argument("--url", help="the site's https:// address, to find og:image files in DIR")
    return parser


# A copy of pubkit's paths.confined (pubkit 0.34.0): a path given on the
# command line lies in the working directory or a temporary directory.
def confined(path: Path | str, what: str) -> Path:
    bases = [Path.cwd(), Path(tempfile.gettempdir())]
    if os.environ.get("RUNNER_TEMP"):
        bases.append(Path(os.environ["RUNNER_TEMP"]))
    resolved = Path(path).resolve()
    if any(resolved.is_relative_to(base.resolve()) for base in bases):
        return resolved
    sys.exit(f"pubhost: {what} ({path}) must be in the working directory or a temporary directory")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd()
    if args.command == "dns":
        from .dns import check  # noqa: PLC0415
        return check(root, args.zone, args.record)
    from .site import run as site  # noqa: PLC0415
    return site(root, confined(args.dir, "the site directory"), args.url)


if __name__ == "__main__":
    sys.exit(main())
