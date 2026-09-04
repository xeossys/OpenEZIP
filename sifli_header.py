"""Shared parsing for the four-byte SiFli image resource header."""

from dataclasses import dataclass
import struct


class SifliHeaderError(ValueError):
    """Raised when a SiFli resource header is missing or invalid."""


@dataclass(frozen=True)
class SifliResourceHeader:
    color_format: int
    width: int
    height: int


def parse_sifli_header(data):
    """Parse the five-bit format and eleven-bit dimensions."""
    if len(data) < 4:
        raise SifliHeaderError("Input is shorter than a SiFli resource header")
    value = struct.unpack_from("<I", data)[0]
    return SifliResourceHeader(
        color_format=value & 0x1F,
        width=(value >> 10) & 0x7FF,
        height=(value >> 21) & 0x7FF,
    )
