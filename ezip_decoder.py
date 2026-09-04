"""Core helpers for decoding SiFli eZIP image data."""

from PIL import Image


EZIP_FORMAT = 1
EZIP_ALPHA_FORMAT = 2

RGB565_LE = "RGB565_LE"
RGB565A_LE = "RGB565A_LE"
RGB888_LE = "RGB888_LE"
ARGB8888_LE = "ARGB8888_LE"


class EzipDecodingError(ValueError):
    """Raised when decoded eZIP pixels have an unsupported layout."""


def automatic_pixel_layout(resource_format, bytes_per_pixel):
    """Return the SiFli pixel layout implied by the resource header and size."""
    layouts = {
        (EZIP_FORMAT, 2): RGB565_LE,
        (EZIP_FORMAT, 3): RGB888_LE,
        (EZIP_ALPHA_FORMAT, 3): RGB565A_LE,
        (EZIP_ALPHA_FORMAT, 4): ARGB8888_LE,
    }
    try:
        return layouts[(resource_format, bytes_per_pixel)]
    except KeyError:
        raise EzipDecodingError(
            "Unsupported eZIP pixel layout: resource format {}, {} bytes/pixel".format(
                resource_format, bytes_per_pixel
            )
        )


def _expand_5_bits(value):
    return value * 255 // 31


def _expand_6_bits(value):
    return value * 255 // 63


def _decode_rgb565a(raw_pixels, width, height):
    rgba = bytearray(width * height * 4)
    output_index = 0
    for input_index in range(0, len(raw_pixels), 3):
        packed = raw_pixels[input_index] | (raw_pixels[input_index + 1] << 8)
        rgba[output_index] = _expand_5_bits((packed >> 11) & 0x1F)
        rgba[output_index + 1] = _expand_6_bits((packed >> 5) & 0x3F)
        rgba[output_index + 2] = _expand_5_bits(packed & 0x1F)
        rgba[output_index + 3] = raw_pixels[input_index + 2]
        output_index += 4
    return Image.frombytes("RGBA", (width, height), bytes(rgba))


def pixels_to_image(raw_pixels, width, height, layout):
    """Convert unfiltered SiFli pixel bytes to a Pillow image."""
    bytes_per_pixel = {
        RGB565_LE: 2,
        RGB565A_LE: 3,
        RGB888_LE: 3,
        ARGB8888_LE: 4,
        "RGB;16": 2,
        "BGR;16": 2,
        "RGB": 3,
        "BGR": 3,
        "RGBA": 4,
        "BGRA": 4,
    }.get(layout)
    if bytes_per_pixel is None:
        raise EzipDecodingError("Unsupported pixel layout: {}".format(layout))

    expected_size = width * height * bytes_per_pixel
    if len(raw_pixels) != expected_size:
        raise EzipDecodingError(
            "Pixel data has {} bytes; {} requires {} bytes for {}x{}".format(
                len(raw_pixels), layout, expected_size, width, height
            )
        )

    if layout == RGB565A_LE:
        return _decode_rgb565a(raw_pixels, width, height)
    if layout == RGB565_LE:
        return Image.frombytes("RGB", (width, height), bytes(raw_pixels), "raw", "BGR;16")
    if layout == RGB888_LE:
        return Image.frombytes("RGB", (width, height), bytes(raw_pixels), "raw", "BGR")
    if layout == ARGB8888_LE:
        return Image.frombytes("RGBA", (width, height), bytes(raw_pixels), "raw", "BGRA")

    image_mode = "RGBA" if layout in ("RGBA", "BGRA") else "RGB"
    return Image.frombytes(image_mode, (width, height), bytes(raw_pixels), "raw", layout)
