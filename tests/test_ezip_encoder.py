import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from ezip_encoder import (
    EzipEncodingError,
    build_encoder_command,
    encode_png,
    parse_sifli_header,
)


class EzipEncoderTest(unittest.TestCase):
    def test_parses_sifli_dimensions(self):
        value = 1 | (485 << 10) | (520 << 21)
        header = parse_sifli_header(struct.pack("<I", value))
        self.assertEqual(1, header.color_format)
        self.assertEqual(485, header.width)
        self.assertEqual(520, header.height)

    def test_builds_official_rgb565a_command(self):
        command = build_encoder_command(
            encoder=Path("/tool/eZIP.exe"),
            source=Path("/art/face.png"),
            output_dir=Path("/out"),
            color_format="rgb565a",
            wine="wine",
        )
        self.assertEqual(
            [
                "wine", "/tool/eZIP.exe", "-convert", "/art/face.png", "-binfile", "2",
                "-rgb565a", "-outdir", "/out",
            ],
            list(command),
        )

    def test_rejects_unknown_color_format(self):
        with self.assertRaises(EzipEncodingError):
            build_encoder_command(
                Path("eZIP.exe"),
                Path("face.png"),
                Path("out"),
                "rgba8888",
            )

    def test_stages_absolute_input_for_official_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "face.png"
            encoder = root / "eZIP.exe"
            output_dir = root / "result"
            Image.new("RGBA", (12, 34), "red").save(source)
            encoder.write_bytes(b"placeholder")

            def fake_run(command, cwd, **_kwargs):
                self.assertIn("face.png", command)
                self.assertIn("output", command)
                self.assertNotIn(str(source), command)
                header = 1 | (12 << 10) | (34 << 21)
                generated = Path(cwd) / "output" / "face.bin"
                generated.parent.mkdir()
                generated.write_bytes(struct.pack("<I", header) + b"payload")
                return SimpleNamespace(returncode=0, stdout="ok")

            with patch("ezip_encoder.subprocess.run", side_effect=fake_run):
                output, header = encode_png(source, encoder, output_dir)

            self.assertEqual(output_dir / "face.bin", output)
            self.assertEqual((12, 34), (header.width, header.height))


if __name__ == "__main__":
    unittest.main()
