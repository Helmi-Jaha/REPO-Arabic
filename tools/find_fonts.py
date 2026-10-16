"""Locate embedded sfnt (TTF/OTF) blobs inside a Unity asset file and report coverage.

Usage: python -I find_fonts.py <assets file> <out dir>
"""
import io
import struct
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

src = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
data = src.read_bytes()

SIGS = [b"\x00\x01\x00\x00", b"OTTO", b"true"]
VALID_TAGS = {b"cmap", b"head", b"hhea", b"hmtx", b"maxp", b"name", b"OS/2", b"post", b"glyf", b"loca", b"CFF ", b"GSUB", b"GPOS", b"GDEF", b"fvar", b"gvar"}

found = []
for sig in SIGS:
    pos = 0
    while True:
        i = data.find(sig, pos)
        if i < 0:
            break
        pos = i + 1
        if i + 12 > len(data):
            continue
        num = struct.unpack(">H", data[i + 4:i + 6])[0]
        if not (4 <= num <= 64):
            continue
        tags = [data[i + 12 + 16 * k:i + 16 + 16 * k] for k in range(num)]
        if sum(t in VALID_TAGS for t in tags) < 4:
            continue
        # Unity stores the blob as a byte vector preceded by an int32 length
        length = struct.unpack("<I", data[i - 4:i])[0]
        end = 0
        for k in range(num):
            off, ln = struct.unpack(">II", data[i + 20 + 16 * k:i + 28 + 16 * k])
            end = max(end, off + ln)
        size = length if end <= length <= end + 4096 else end
        found.append((i, size))

for i, size in found:
    blob = data[i:i + size]
    try:
        f = TTFont(io.BytesIO(blob))
    except Exception as e:  # noqa: BLE001
        print(f"@{i:#x} size={size} parse error: {e}")
        continue
    name = f["name"].getDebugName(4) or f["name"].getDebugName(1)
    cmap = f.getBestCmap() or {}
    def cov(a, b):
        return sum(1 for c in range(a, b + 1) if c in cmap)
    lic = (f["name"].getDebugName(13) or "")[:80]
    print(f"@{i:#x} size={size} name={name!r} glyphs={len(f.getGlyphOrder())} cmap={len(cmap)}")
    print(f"   arabic 0600-06FF={cov(0x600, 0x6FF)} presB FE70-FEFF={cov(0xFE70, 0xFEFF)} presA FB50-FDFF={cov(0xFB50, 0xFDFF)} latin 20-7E={cov(0x20, 0x7E)} GSUB={'GSUB' in f} fvar={'fvar' in f}")
    print(f"   license: {lic}")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (name or "font"))
    (out / f"{safe}_{i:x}.ttf").write_bytes(blob)
