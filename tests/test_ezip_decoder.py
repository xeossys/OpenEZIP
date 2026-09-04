import struct
import unittest
import zlib

from ezip_decoder import (
    ARGB8888_LE,
    EZIP_ALPHA_FORMAT,
    EZIP_FORMAT,
    RGB565A_LE,
    RGB565_LE,
    RGB888_LE,
    EzipDecodingError,
    NotStandardEzipStreamError,
    automatic_pixel_layout,
    decompress_standard_ezip,
    infer_bytes_per_pixel,
    parse_ezip_stream_header,
    pixels_to_image,
    unfilter_png_blocks,
    validate_stream_bit_depth,
)


class EzipPixelDecoderTest(unittest.TestCase):
    def assert_row(self, expected, image):
        self.assertEqual(
            expected,
            [image.getpixel((x, 0)) for x in range(image.width)],
        )

    def test_selects_layout_from_resource_format_and_pixel_size(self):
        self.assertEqual(RGB565_LE, automatic_pixel_layout(EZIP_FORMAT, 2))
        self.assertEqual(RGB888_LE, automatic_pixel_layout(EZIP_FORMAT, 3))
        self.assertEqual(RGB565A_LE, automatic_pixel_layout(EZIP_ALPHA_FORMAT, 3))
        self.assertEqual(ARGB8888_LE, automatic_pixel_layout(EZIP_ALPHA_FORMAT, 4))

    def test_rejects_ambiguous_layout(self):
        with self.assertRaises(EzipDecodingError):
            automatic_pixel_layout(EZIP_FORMAT, 4)

    def test_decodes_little_endian_rgb565(self):
        image = pixels_to_image(
            bytes.fromhex("00 f8 e0 07 1f 00"), 3, 1, RGB565_LE
        )
        self.assert_row([(255, 0, 0), (0, 255, 0), (0, 0, 255)], image)

    def test_decodes_little_endian_rgb888(self):
        image = pixels_to_image(
            bytes.fromhex("00 00 ff 00 ff 00 ff 00 00"), 3, 1, RGB888_LE
        )
        self.assert_row([(255, 0, 0), (0, 255, 0), (0, 0, 255)], image)

    def test_decodes_little_endian_rgb565_with_alpha(self):
        image = pixels_to_image(
            bytes.fromhex("00 f8 20 e0 07 80 1f 00 ff"), 3, 1, RGB565A_LE
        )
        self.assert_row(
            [(255, 0, 0, 32), (0, 255, 0, 128), (0, 0, 255, 255)],
            image,
        )

    def test_rgb565_expansion_is_identical_with_and_without_alpha(self):
        for packed in (0x0001, 0x1234, 0x7BEF, 0x8410, 0xFFFE):
            rgb565 = packed.to_bytes(2, "little")
            opaque = pixels_to_image(rgb565, 1, 1, RGB565_LE).getpixel((0, 0))
            with_alpha = pixels_to_image(
                rgb565 + b"\x7f", 1, 1, RGB565A_LE
            ).getpixel((0, 0))
            self.assertEqual(opaque, with_alpha[:3])
            self.assertEqual(127, with_alpha[3])

    def test_decodes_little_endian_argb8888(self):
        image = pixels_to_image(
            bytes.fromhex("1e 14 0a 28 46 3c 32 50"), 2, 1, ARGB8888_LE
        )
        self.assert_row([(10, 20, 30, 40), (50, 60, 70, 80)], image)

    def test_rejects_wrong_pixel_data_length(self):
        with self.assertRaises(EzipDecodingError):
            pixels_to_image(b"\x00\x00", 2, 1, RGB565_LE)


class EzipFilterDecoderTest(unittest.TestCase):
    def test_infers_pixel_size_with_and_without_filters(self):
        self.assertEqual(3, infer_bytes_per_pixel(24, 4, 2, False))
        self.assertEqual(3, infer_bytes_per_pixel(26, 4, 2, True))

    def test_rejects_non_integral_pixel_size(self):
        with self.assertRaises(EzipDecodingError):
            infer_bytes_per_pixel(25, 4, 2, True)

    def test_legacy_pixel_size_preserves_floor_division(self):
        self.assertEqual(3, infer_bytes_per_pixel(27, 4, 2, True, strict=False))

    def test_unfilters_sub_scanline(self):
        decoded = unfilter_png_blocks(
            bytes([1, 10, 10, 10]), 3, 1, 1, 1, True
        )
        self.assertEqual(bytes([10, 20, 30]), decoded)

    def test_unfilters_up_scanline(self):
        decoded = unfilter_png_blocks(
            bytes([0, 10, 20, 2, 1, 2]), 2, 2, 1, 2, True
        )
        self.assertEqual(bytes([10, 20, 11, 22]), decoded)

    def test_resets_previous_row_at_block_boundary(self):
        decoded = unfilter_png_blocks(
            bytes([0, 10, 20, 2, 1, 2]), 2, 2, 1, 1, True
        )
        self.assertEqual(bytes([10, 20, 1, 2]), decoded)

    def test_rejects_unknown_filter(self):
        with self.assertRaises(EzipDecodingError):
            unfilter_png_blocks(bytes([5, 10]), 1, 1, 1, 1, True)

    def test_legacy_unfilter_tolerates_partial_rows_and_unknown_filters(self):
        decoded = unfilter_png_blocks(
            bytes([5, 10]), 2, 2, 1, 2, True, strict=False
        )
        self.assertEqual(bytes([10, 0, 0, 0]), decoded)

    def test_legacy_unfiltered_data_is_truncated_to_image_size(self):
        decoded = unfilter_png_blocks(
            bytes([1, 2, 3]), 2, 1, 1, 1, False, strict=False
        )
        self.assertEqual(bytes([1, 2]), decoded)


class EzipStreamDecoderTest(unittest.TestCase):
    @staticmethod
    def make_stream(output, width=2, height=1, block_rows=32, filter_mode=0):
        compressor = zlib.compressobj(level=9, wbits=-15)
        compressed = compressor.compress(output) + compressor.flush()
        data_size = 16 + len(compressed) + 4
        header = struct.pack(
            ">IBBBBHHBBBB",
            data_size,
            0x1C,
            24,
            block_rows,
            0,
            width,
            height,
            filter_mode,
            0,
            0,
            0,
        )
        checksum = struct.pack(">I", zlib.adler32(output) & 0xFFFFFFFF)
        return header + compressed + checksum

    def test_parses_official_stream_header_layout(self):
        header = parse_ezip_stream_header(
            bytes.fromhex("00 00 0b a4 1c 18 20 00 00 44 00 25 00 00 00 00")
            + bytes(2964)
        )
        self.assertEqual(2980, header.data_size)
        self.assertEqual(24, header.bit_depth)
        self.assertEqual(32, header.block_rows)
        self.assertEqual((68, 37), (header.width, header.height))
        self.assertTrue(header.has_filters)

    def test_decompresses_standard_stream_and_verifies_checksum(self):
        expected = bytes([0, 0, 0, 255, 0, 248])
        header, output = decompress_standard_ezip(self.make_stream(expected))
        self.assertEqual((2, 1), (header.width, header.height))
        self.assertEqual(expected, output)

    def test_malformed_header_is_available_to_legacy_fallback(self):
        with self.assertRaises(NotStandardEzipStreamError):
            decompress_standard_ezip(bytes(16))

    def test_validates_stream_bit_depth(self):
        header, _ = decompress_standard_ezip(self.make_stream(b"pixels"))
        validate_stream_bit_depth(header, 3)
        with self.assertRaisesRegex(EzipDecodingError, "bit depth"):
            validate_stream_bit_depth(header, 2)

    def test_rejects_bad_standard_stream_checksum(self):
        stream = bytearray(self.make_stream(b"decoded pixels"))
        stream[-1] ^= 0xFF
        with self.assertRaisesRegex(EzipDecodingError, "checksum mismatch"):
            decompress_standard_ezip(stream)

    def test_identifies_non_standard_compression(self):
        stream = bytearray(self.make_stream(b"decoded pixels"))
        stream[16:-4] = bytes(len(stream[16:-4]))
        with self.assertRaises(NotStandardEzipStreamError):
            decompress_standard_ezip(stream)


if __name__ == "__main__":
    unittest.main()
