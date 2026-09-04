#!/usr/bin/env python3
"""Bridge to the official SiFli eZIP encoder.

OpenEZIP intentionally does not bundle eZIP.exe or any vendor DLLs.  Point this
module at a copy obtained from SiFli's GraphicsTool installation instead.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional, Sequence, Tuple

from sifli_header import (
    SifliHeaderError,
    SifliResourceHeader,
    parse_sifli_header as _parse_sifli_header,
)


class EzipEncodingError(RuntimeError):
    """Raised when the official encoder cannot produce a valid eZIP file."""


SUPPORTED_FORMATS = ("rgb565a", "rgb565", "rgb888")


def parse_sifli_header(data: bytes) -> SifliResourceHeader:
    """Parse a resource header, preserving the encoder bridge error API."""
    try:
        return _parse_sifli_header(data)
    except SifliHeaderError as error:
        raise EzipEncodingError(str(error)) from error


def build_encoder_command(
    encoder: Path,
    source: Path,
    output_dir: Path,
    color_format: str,
    wine: Optional[str] = None,
) -> Sequence[str]:
    """Return the exact GraphicsTool command without executing it."""
    if color_format not in SUPPORTED_FORMATS:
        raise EzipEncodingError(
            "Unsupported color format {!r}; choose one of {}".format(
                color_format, ", ".join(SUPPORTED_FORMATS)
            )
        )
    command = [
        str(encoder),
        "-convert",
        str(source),
        "-binfile",
        "2",
        "-" + color_format,
        "-outdir",
        str(output_dir),
    ]
    return [wine] + command if wine else command


def encode_png(
    source: Path,
    encoder: Path,
    output_dir: Path,
    color_format: str = "rgb565a",
    wine: Optional[str] = None,
) -> Tuple[Path, SifliResourceHeader]:
    """Encode *source* using a user-supplied official eZIP.exe installation.

    On Linux, pass ``wine="wine"`` (or the absolute Wine executable path).
    The function validates that eZIP produced a SiFli header whose dimensions
    match the source image; it does not claim to implement SiFli compression.
    """
    source = Path(source).expanduser().resolve()
    encoder = Path(encoder).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    if not source.is_file():
        raise EzipEncodingError("Input PNG does not exist: {}".format(source))
    if not encoder.is_file():
        raise EzipEncodingError("eZIP.exe does not exist: {}".format(encoder))
    if source.suffix.lower() != ".png":
        raise EzipEncodingError("The official bridge accepts PNG input only")
    if wine and shutil.which(wine) is None and not Path(wine).is_file():
        raise EzipEncodingError("Wine executable was not found: {}".format(wine))

    from PIL import Image

    with Image.open(source) as image:
        expected_size = image.size
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (source.stem + ".bin")
    # eZIP.exe treats an absolute input path as part of the output filename
    # when -outdir is supplied. Stage the source and use relative paths to
    # make its Windows and Wine behavior identical.
    with tempfile.TemporaryDirectory(prefix="openezip-") as workspace_name:
        workspace = Path(workspace_name)
        staged_source = workspace / source.name
        staged_output_dir = workspace / "output"
        shutil.copy2(source, staged_source)
        command = build_encoder_command(
            encoder,
            Path(staged_source.name),
            Path(staged_output_dir.name),
            color_format,
            wine,
        )
        result = subprocess.run(
            command,
            cwd=str(workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        generated = staged_output_dir / (source.stem + ".bin")
        if result.returncode != 0 or not generated.is_file():
            raise EzipEncodingError(
                "Official eZIP conversion failed (exit {}):\n{}".format(
                    result.returncode, result.stdout.strip()
                )
            )
        shutil.copy2(generated, output)
    header = parse_sifli_header(output.read_bytes())
    if (header.width, header.height) != expected_size:
        raise EzipEncodingError(
            "eZIP dimensions {}x{} do not match PNG dimensions {}x{}".format(
                header.width, header.height, expected_size[0], expected_size[1]
            )
        )
    return output, header


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Encode a PNG through a user-supplied official SiFli eZIP.exe"
    )
    parser.add_argument("input", type=Path, help="PNG to encode")
    parser.add_argument("--encoder", required=True, type=Path, help="Path to eZIP.exe")
    parser.add_argument("--outdir", required=True, type=Path, help="Directory for the .bin")
    parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="rgb565a")
    parser.add_argument(
        "--wine",
        nargs="?",
        const="wine",
        help="Run eZIP.exe through Wine (optionally specify the Wine executable)",
    )
    args = parser.parse_args()
    try:
        output, header = encode_png(
            args.input, args.encoder, args.outdir, args.format, args.wine
        )
    except EzipEncodingError as error:
        parser.error(str(error))
    print("Wrote {}".format(output))
    print(
        "SiFli header: format={} width={} height={}".format(
            header.color_format, header.width, header.height
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
