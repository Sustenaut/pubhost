"""Steps for `pubhost site check`, against small built sites written into
the scratch directory with pubtest's file steps: one complete page, its
card (an image's first bytes, all the check reads), and the changes each
scenario makes to them."""

from __future__ import annotations

import struct

from pytest_bdd import given, parsers, scenarios

scenarios("site.feature")


def png(width: int, height: int) -> bytes:
    """A PNG's signature and header: all the check reads."""
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)


def jpeg(width: int, height: int) -> bytes:
    """A JPEG's start, an APP0 segment and a baseline frame header."""
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


IMAGES = {"PNG": png, "JPEG": jpeg}


@given(parsers.parse("the site's card is a {width:d}×{height:d} {kind}"))
def card(ctx, width, height, kind):
    # Named card.png whatever it is: the check reads the bytes, not the name.
    (ctx.directory / "_site" / "card.png").write_bytes(IMAGES[kind](width, height))


@given("the site's card is a WebP")
def webp_card(ctx):
    (ctx.directory / "_site" / "card.png").write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
