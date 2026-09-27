"""Convert the isolated Xvfb's 24-depth/32-bpp little-endian test capture."""
import pathlib
import struct
import sys
import zlib


def convert(source, destination):
    data = pathlib.Path(source).read_bytes()
    header = struct.unpack(">25I", data[:100])
    if not (header[1] == 7 and header[3] == 24 and header[7] == 0
            and header[11] == 32 and header[14:17] == (0xFF0000, 0xFF00, 0xFF)):
        raise ValueError("unsupported Xvfb capture format")
    offset = header[0] + 12 * header[19]
    width, height = header[4:6]
    if not 0 < width <= 8192 or not 0 < height <= 8192:
        raise ValueError("capture dimensions outside test bounds")
    rows = []
    for y in range(height):
        pixels = data[offset + y * header[12]:offset + y * header[12] + width * 4]
        if len(pixels) != width * 4:
            raise ValueError("truncated capture")
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = pixels[2::4], pixels[1::4], pixels[0::4]
        rows.append(b"\0" + rgb)

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    pathlib.Path(destination).write_bytes(png)


if __name__ == "__main__":
    convert(*sys.argv[1:])
