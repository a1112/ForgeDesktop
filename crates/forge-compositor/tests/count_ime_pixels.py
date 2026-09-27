"""Count the persistent IME fixture's exact green pixels in isolated Xvfb."""
import pathlib
import struct
import sys

data = pathlib.Path(sys.argv[1]).read_bytes()
h = struct.unpack('>25I', data[:100])
assert h[1] == 7 and h[3] == 24 and h[7] == 0 and h[11] == 32
offset = h[0] + 12 * h[19]
pixels = []
duplicates = 0
singles = 0
for y in range(h[5]):
    for x in range(h[4]):
        i = offset + y*h[12] + 4*x
        if data[i:i+3] == b'\x00\xff\x00':
            pixels.append((x,y))
        b,g,r = data[i:i+3]
        if g == 255 and r == 127 and b == 127:
            singles += 1
        if g > 220 and r < 100 and b < 100:
            duplicates += 1
if sys.argv[2] == 'alpha':
    print(f'Overlapping translucent IME pixels: {duplicates}')
    assert singles == 800, f'expected 800 candidate pixels, got {singles}'
    assert duplicates == 0, 'IME popup was blended more than once'
    sys.exit(0)
print(f'IME green pixels: {len(pixels)}; bounds={min(pixels) if pixels else None}..{max(pixels) if pixels else None}')
assert len(pixels) == int(sys.argv[2]), 'duplicate or missing IME popup pixels'
