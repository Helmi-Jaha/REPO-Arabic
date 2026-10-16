"""Make an internal copy of an Arabic font whose cmap also covers every Arabic Presentation Form B
(U+FE70..U+FEFC), pointing each to the glyph the font's own GSUB would produce (isol/init/medi/fina,
lam-alef ligatures). Renames the family (OFL-modified version). Prints coverage before/after.

Usage: python -I patch_font_cmap.py <in.ttf> <out.ttf> "<New Family Name>"
"""
import sys
import unicodedata

from fontTools.ttLib import TTFont

src, dst, family = sys.argv[1], sys.argv[2], sys.argv[3]
f = TTFont(src, recalcTimestamp=False)  # keep head.modified: reproducible output
cmap = f.getBestCmap()
gsub = f["GSUB"].table if "GSUB" in f else None
FORM = {"<isolated>": "isol", "<initial>": "init", "<medial>": "medi", "<final>": "fina"}


def lookups_for(tag):
    idx = []
    if gsub is None:
        return idx
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == tag:
            idx += fr.Feature.LookupListIndex
    out = []
    for li in sorted(set(idx)):
        lk = gsub.LookupList.Lookup[li]
        for st in lk.SubTable:
            t = lk.LookupType
            if t == 7:
                t, st = st.ExtensionLookupType, st.ExtSubTable
            out.append((t, st))
    return out


def single(tag, glyph):
    for t, st in lookups_for(tag):
        if t == 1 and glyph in st.mapping:
            return st.mapping[glyph]
    return None


def ligature(first, rest):
    for tag in ("rlig", "liga", "calt"):
        for t, st in lookups_for(tag):
            if t == 4 and first in st.ligatures:
                for lig in st.ligatures[first]:
                    if lig.Component == rest:
                        return lig.LigGlyph
    return None


before = sum(1 for c in range(0xFE70, 0xFEFD) if c in cmap)
added = {}
for cp in range(0xFE70, 0xFEFD):
    if cp in cmap:
        continue
    dec = unicodedata.decomposition(chr(cp)).split()
    if len(dec) < 2 or dec[0] not in FORM:
        continue
    form, bases = FORM[dec[0]], [int(x, 16) for x in dec[1:]]
    if any(b not in cmap for b in bases):
        continue
    if len(bases) == 1:
        g0 = cmap[bases[0]]
        g = single(form, g0) or (g0 if form == "isol" else None)
    else:  # lam-alef: isolated = lam.init + alef.fina ; final = lam.medi + alef.fina
        lam = single("init" if form == "isol" else "medi", cmap[bases[0]]) or cmap[bases[0]]
        alef = single("fina", cmap[bases[1]]) or cmap[bases[1]]
        g = ligature(lam, [alef]) or ligature(cmap[bases[0]], [cmap[bases[1]]])
    if g:
        added[cp] = g
for table in f["cmap"].tables:
    if table.isUnicode():
        table.cmap.update(added)
for rec in f["name"].names:
    if rec.nameID in (1, 4, 16):
        rec.string = family if rec.nameID != 4 else family + " Regular"
    elif rec.nameID == 6:
        rec.string = family.replace(" ", "") + "-Regular"
after = sum(1 for c in range(0xFE70, 0xFEFD) if c in f.getBestCmap())
f.save(dst)
missing = [hex(c) for c in range(0xFE80, 0xFEFD) if c not in f.getBestCmap()]
print(f"{family}: presentation forms {before} -> {after}; still missing in FE80-FEFC: {missing or 'none'}")
