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


def infer_bytes_per_pixel(data_size, width, height, has_filters, strict=True):
    """Infer pixel size while validating the decompressed scanline length."""
    if width <= 0 or height <= 0:
        raise EzipDecodingError("Image dimensions must be positive")

    filter_bytes = height if has_filters else 0
    pixel_bytes = data_size - filter_bytes
    pixel_count = width * height
    if not strict:
        return pixel_bytes // pixel_count
    if pixel_bytes <= 0 or pixel_bytes % pixel_count:
        raise EzipDecodingError(
            "Decompressed data size {} is invalid for a {}x{} image{}".format(
                data_size,
                width,
                height,
                " with row filters" if has_filters else "",
            )
        )
    return pixel_bytes // pixel_count


def unfilter_png_blocks(
    data,
    width,
    height,
    bytes_per_pixel,
    block_row_size,
    has_filters,
    strict=True,
):
    """Reverse PNG scanline filters, resetting the previous row per eZIP block."""
    stride = width * bytes_per_pixel
    expected_size = height * (stride + (1 if has_filters else 0))
    if strict and len(data) != expected_size:
        raise EzipDecodingError(
            "Decompressed data has {} bytes; expected {}".format(
                len(data), expected_size
            )
        )
    if not has_filters:
        return bytearray(data if strict else data[:expected_size])
    if strict and block_row_size <= 0:
        raise EzipDecodingError("Filtered data requires a positive block row size")

    out = bytearray(width * height * bytes_per_pixel)
    row_len = stride + 1

    def paeth(a, b, c):
        prediction = a + b - c
        distance_a = abs(prediction - a)
        distance_b = abs(prediction - b)
        distance_c = abs(prediction - c)
        if distance_a <= distance_b and distance_a <= distance_c:
            return a
        if distance_b <= distance_c:
            return b
        return c

    for y in range(height):
        in_row_start = y * row_len
        if not strict and in_row_start >= len(data):
            break
        filter_type = data[in_row_start]
        if strict and filter_type > 4:
            raise EzipDecodingError(
                "Unsupported PNG filter type {} on row {}".format(filter_type, y)
            )
        in_row = data[in_row_start + 1 : in_row_start + 1 + stride]
        first_row_in_block = y % block_row_size == 0

        for x, raw in enumerate(in_row):
            left = out[y * stride + x - bytes_per_pixel] if x >= bytes_per_pixel else 0
            up = 0 if first_row_in_block else out[(y - 1) * stride + x]
            up_left = (
                0
                if first_row_in_block or x < bytes_per_pixel
                else out[(y - 1) * stride + x - bytes_per_pixel]
            )

            if filter_type == 0:
                value = raw
            elif filter_type == 1:
                value = raw + left
            elif filter_type == 2:
                value = raw + up
            elif filter_type == 3:
                value = raw + (left + up) // 2
            elif filter_type == 4:
                value = raw + paeth(left, up, up_left)
            else:
                value = raw
            out[y * stride + x] = value & 0xFF

    return out


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
