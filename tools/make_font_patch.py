"""Build the in-place font patch for sharedassets0.assets (no code mod, no file-structure change).

The game's Arabic fallback is a *dynamic* TMP font asset whose glyphs are rasterised at runtime from the
embedded TTF of the "NotoSansArabic-VariableFont_wdth,wght" Font object (m_FontData byte vector).
We overwrite exactly that byte range with a static Changa instance (presentation forms added) padded
with zeros to the same length, so every offset, size and length prefix in the file stays identical.

Usage: python -I make_font_patch.py <original sharedassets0.assets> <patched-cmap Changa.ttf> <out dir> [--wght 500]
Writes: <out>/font_region.bin (the replacement bytes) and <out>/font_patch.json (offset, length, hashes).
"""
import hashlib
import io
import json
import struct
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

assets, font_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
wght = float(sys.argv[sys.argv.index("--wght") + 1]) if "--wght" in sys.argv else 500.0
OFFSET = 0x1B9B970          # start of the TTF bytes (found by tools/find_fonts.py, v0.4.4.3)

data = assets.read_bytes()
length = struct.unpack_from("<i", data, OFFSET - 4)[0]
orig_region = data[OFFSET:OFFSET + length]
assert orig_region[:4] == b"\x00\x01\x00\x00", "unexpected font header at offset"
TTFont(io.BytesIO(orig_region))  # must parse
name = TTFont(io.BytesIO(orig_region))["name"].getDebugName(1)
assert "Noto Sans Arabic" in (name or ""), f"unexpected font at offset: {name}"

f = TTFont(font_path, recalcTimestamp=False)  # keep head.modified: reproducible output
if "fvar" in f:
    f = instancer.instantiateVariableFont(f, {"wght": wght}, updateFontNames=False)
buf = io.BytesIO()
f.save(buf)
new = buf.getvalue()
if len(new) > length:
    raise SystemExit(f"replacement font {len(new)} B is larger than the slot {length} B")
region = new + b"\0" * (length - len(new))
TTFont(io.BytesIO(region))  # padded font must still parse

patched = data[:OFFSET] + region + data[OFFSET + length:]
sha = lambda b: hashlib.sha256(b).hexdigest().upper()
out.mkdir(parents=True, exist_ok=True)
(out / "font_region.bin").write_bytes(region)
meta = {
    "target": "REPO_Data/sharedassets0.assets",
    "offset": OFFSET, "length": length,
    "original_file_sha256": sha(data), "patched_file_sha256": sha(patched),
    "original_region_sha256": sha(orig_region), "region_sha256": sha(region),
    "font": "REPO AR Changa (Changa by The Changa Project Authors, SIL OFL 1.1; static wght %g, presentation forms added)" % wght,
    "font_bytes": len(new),
}
(out / "font_patch.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(json.dumps(meta, indent=2))
