import unittest

from ezip_decoder import (
    ARGB8888_LE,
    EZIP_ALPHA_FORMAT,
    EZIP_FORMAT,
    RGB565A_LE,
    RGB565_LE,
    RGB888_LE,
    EzipDecodingError,
    automatic_pixel_layout,
    pixels_to_image,
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


if __name__ == "__main__":
    unittest.main()
