"""Convert logical-order Arabic UI strings to the visual form R.E.P.O.'s TextMeshPro renders.

R.E.P.O. (Unity / TextMeshPro, English locale slot) does no Arabic shaping and no BiDi, and the
English locale has RightToLeft = false, so every text component lays glyphs out left-to-right.
We therefore emit:
  * contextual presentation forms (U+FE70..U+FEFF) incl. mandatory lam-alef ligatures,
  * a simplified Unicode BiDi reordering (paragraph level RTL, levels 1/2 only),
  * rich-text tags re-emitted around the visual runs so they stay balanced,
  * placeholders ({x}, smart formats, [input] tokens, emoticons) kept as atomic LTR units,
  * optional logical-order line wrapping, so multi-line text reads top-to-bottom correctly.

The logical (source) translation is never modified; this module only produces the display copy.
"""
from __future__ import annotations

import re
import unicodedata

from arabic_reshaper.letters import LETTERS_ARABIC

# ---------------------------------------------------------------- tokenizing
TOKEN_RE = re.compile(
    r"(?P<nl>\\n|\n)"
    r"|(?P<tag></?(?:b|i|u|s|color|size|mark|sup|sub|uppercase|lowercase|smallcaps|nobr|alpha|cspace|font|voffset|line-height|margin|indent|align|sprite|br)\b[^<>]*>)"
    r"|(?P<atom>\{(?:[^{}]|\{[^{}]*\})*\}|\[[A-Za-z0-9_]+\]|:'?[()]|<[^<>]*>)"
)

HARAKAT = set(range(0x064B, 0x0660)) | {0x0670}
MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<", "«": "»", "»": "«"}

LAM_ALEF = {
    # alef variant (final form) -> (isolated ligature, final ligature)
    "ﺎ": ("ﻻ", "ﻼ"),  # alef
    "ﺂ": ("ﻵ", "ﻶ"),  # alef madda
    "ﺄ": ("ﻷ", "ﻸ"),  # alef hamza above
    "ﺈ": ("ﻹ", "ﻺ"),  # alef hamza below
}
LAM_INITIAL, LAM_MEDIAL = "ﻟ", "ﻠ"


# In R.E.P.O. every glyph that TextMeshPro takes from the fallback "Noto Sans Arabic" dynamic font asset
# is advanced ~20% too little (measured in-game, reports/shots/t9_zoom.png), so joined letters overlap.
# Fix: after each such glyph emit a TMP <space=Nem> equal to ADVANCE_FIX * (glyph advance / unitsPerEm).
# Advances come from tools/noto_arabic_advances.json (derived from the font shipped inside the game).
# With the shipped font patch (static Changa replaces the variable Noto data) the glyph advances are correct,
# measured in-game (reports/shots/t31_row1.png): 0 = clean joins, any positive value opens gaps.
ADVANCE_FIX = 0.0
_ADV_PATH = __import__("pathlib").Path(__file__).with_name("noto_arabic_advances.json")
ADVANCES: dict[str, float] = {}
if _ADV_PATH.exists():
    ADVANCES = {chr(int(k)): v for k, v in __import__("json").loads(_ADV_PATH.read_text(encoding="utf-8")).items()}

# Optional extra gap at non-joining boundaries / word spaces (0 = off; kept for tuning only).
GAP_EM = 0.0
WORD_GAP_FACTOR = 2


class Unit:
    __slots__ = ("text", "atom", "styles", "level", "gap")

    def __init__(self, text: str, atom: bool, styles: tuple):
        self.text = text
        self.atom = atom
        self.styles = styles
        self.level = 1
        self.gap = False  # needs extra space before the logically-next letter


def _tag_name(tag: str) -> str:
    m = re.match(r"</?([a-z\-]+)", tag)
    return m.group(1) if m else ""


def tokenize_lines(s: str):
    """Split a logical string into lines of Units, tracking active rich-text tags."""
    lines, cur, stack = [], [], []
    pos = 0
    for m in TOKEN_RE.finditer(s):
        for ch in s[pos:m.start()]:
            cur.append(Unit(ch, False, tuple(stack)))
        pos = m.end()
        if m.group("nl"):
            lines.append(cur)
            cur = []
        elif m.group("tag"):
            tag = m.group("tag")
            name = _tag_name(tag)
            if tag.startswith("</"):
                for i in range(len(stack) - 1, -1, -1):
                    if _tag_name(stack[i]) == name:
                        del stack[i]
                        break
            elif name in ("br",):
                lines.append(cur)
                cur = []
            else:
                stack.append(tag)
        else:
            cur.append(Unit(m.group("atom"), True, tuple(stack)))
    for ch in s[pos:]:
        cur.append(Unit(ch, False, tuple(stack)))
    lines.append(cur)
    return lines


# ---------------------------------------------------------------- wrapping (logical order)
def _width(u: Unit) -> float:
    if u.atom:
        return 4.0 if u.text.startswith("[") else max(2.0, len(u.text) * 0.6)
    return 1.0


def wrap(units, max_chars: float | None):
    if not max_chars:
        return [units]
    words, word = [], []
    for u in units:
        if not u.atom and u.text == " ":
            words.append(word)
            word = []
        else:
            word.append(u)
    words.append(word)
    out, line, w = [], [], 0.0
    for word in words:
        ww = sum(_width(u) for u in word)
        if line and w + 1 + ww > max_chars:
            out.append(line)
            line, w = [], 0.0
        if line:
            line.append(Unit(" ", False, word[0].styles if word else line[-1].styles))
            w += 1
        line.extend(word)
        w += ww
    out.append(line)
    return out


# ---------------------------------------------------------------- shaping
def _forms(ch: str):
    return LETTERS_ARABIC.get(ch)


def _joins_after(ch: str) -> bool:  # can connect to the following letter
    f = _forms(ch)
    return bool(f and (f[1] or f[2]))


def _joins_before(ch: str) -> bool:  # can connect to the preceding letter
    f = _forms(ch)
    return bool(f and (f[3] or f[2]))


def shape(units):
    n = len(units)
    letters = [(not u.atom and _forms(u.text) is not None) for u in units]

    def neighbour(i, step):
        j = i + step
        while 0 <= j < n:
            u = units[j]
            if not u.atom and ord(u.text) in HARAKAT:
                j += step
                continue
            return j if letters[j] else None
        return None

    shaped = []
    for i, u in enumerate(units):
        if not letters[i]:
            # word spaces shrink too under negative spacing: widen spaces that touch Arabic letters
            if not u.atom and u.text == " " and ((i > 0 and letters[i - 1]) or (i + 1 < n and letters[i + 1])):
                u.gap = WORD_GAP_FACTOR
            shaped.append(u.text)
            continue
        iso, ini, med, fin = _forms(u.text)
        p, q = neighbour(i, -1), neighbour(i, 1)
        can_prev = p is not None and _joins_after(units[p].text) and bool(fin or med)
        can_next = q is not None and _joins_before(units[q].text) and bool(ini or med)
        if can_prev and can_next and med:
            shaped.append(med)
        elif can_prev and fin:
            shaped.append(fin)
            u.gap = q is not None
        elif can_next and ini:
            shaped.append(ini)
        else:
            shaped.append(iso or u.text)
            u.gap = q is not None
    for u, t in zip(units, shaped):
        u.text = t
    # mandatory lam-alef ligatures
    out = []
    for u in units:
        if out and not u.atom and u.text in LAM_ALEF and not out[-1].atom and out[-1].text in (LAM_INITIAL, LAM_MEDIAL):
            prev = out[-1]
            iso, fin = LAM_ALEF[u.text]
            prev.text = iso if prev.text == LAM_INITIAL else fin
            prev.gap = u.gap
            continue
        out.append(u)
    return out


# ---------------------------------------------------------------- bidi (simplified UBA, RTL paragraph)
def _bidi_class(u: Unit) -> str:
    if u.atom:
        return "L"
    c = unicodedata.bidirectional(u.text)
    if c in ("R", "AL"):
        return "R"
    if c in ("EN", "AN"):
        return "EN"
    if c == "L":
        return "L"
    if c in ("ET", "ES", "CS"):
        return c
    return "N"


def reorder(units):
    cls = [_bidi_class(u) for u in units]
    n = len(cls)
    # W2: EN whose preceding strong type is R (or sos, which is R here) -> AN
    last = "R"
    for i, c in enumerate(cls):
        if c in ("R", "L"):
            last = c
        elif c == "EN" and last == "R":
            cls[i] = "AN"
    # W4: single ES/CS between EN -> EN, single CS between AN -> AN
    for i in range(1, n - 1):
        if cls[i - 1] == cls[i + 1] == "EN" and cls[i] in ("ES", "CS"):
            cls[i] = "EN"
        elif cls[i - 1] == cls[i + 1] == "AN" and cls[i] == "CS":
            cls[i] = "AN"
    # W5: ET sequences adjacent to EN -> EN
    for _ in range(2):
        for i, c in enumerate(cls):
            if c == "ET" and ((i > 0 and cls[i - 1] == "EN") or (i + 1 < n and cls[i + 1] == "EN")):
                cls[i] = "EN"
    cls = ["EN" if c == "AN" else c for c in cls]
    cls = ["N" if c in ("ET", "ES", "CS") else c for c in cls]
    # N1/N2: neutrals take the direction of surrounding strong types (EN counts as R), else RTL
    def strong(c):
        return "L" if c == "L" else ("R" if c in ("R", "EN") else None)

    i = 0
    while i < n:
        if cls[i] != "N":
            i += 1
            continue
        j = i
        while j < n and cls[j] == "N":
            j += 1
        before = strong(cls[i - 1]) if i > 0 else "R"
        after = strong(cls[j]) if j < n else "R"
        res = "L" if (before == "L" and after == "L") else "R"
        for k in range(i, j):
            cls[k] = res
        i = j
    for u, c in zip(units, cls):
        u.level = 2 if c in ("L", "EN") else 1
        if u.level == 1 and not u.atom and u.text in MIRROR:
            u.text = MIRROR[u.text]
    # L2: reverse the whole line, then restore order inside each level-2 run
    vis = list(reversed(units))
    out, run = [], []
    for u in vis:
        if u.level == 2:
            run.append(u)
        else:
            if run:
                out.extend(reversed(run))
                run = []
            out.append(u)
    if run:
        out.extend(reversed(run))
    return out


# ---------------------------------------------------------------- emit
def emit(units, gap_em: float = GAP_EM, adv_fix: float = ADVANCE_FIX) -> str:
    parts, active = [], ()
    for u in units:
        if u.styles != active:
            # close everything that differs, then open the new stack
            common = 0
            while common < min(len(active), len(u.styles)) and active[common] == u.styles[common]:
                common += 1
            for tag in reversed(active[common:]):
                parts.append(f"</{_tag_name(tag)}>")
            parts.extend(u.styles[common:])
            active = u.styles
        if u.gap and gap_em:
            # visual order: the logically-next letter sits to the LEFT, i.e. is emitted just before us
            parts.append(f"<space={round(gap_em * u.gap, 3):g}em>")
        parts.append(u.text)
        if adv_fix and not u.atom and u.text in ADVANCES:
            parts.append(f"<space={ADVANCES[u.text] * adv_fix:.3f}em>")
    for tag in reversed(active):
        parts.append(f"</{_tag_name(tag)}>")
    return "".join(parts)


def to_visual(logical: str, max_chars: float | None = None, newline: str = "\\n", gap_em: float = GAP_EM,
              adv_fix: float = ADVANCE_FIX) -> str:
    out_lines = []
    for line in tokenize_lines(logical):
        for sub in wrap(line, max_chars):
            out_lines.append(emit(reorder(shape(sub)), gap_em, adv_fix))
    return newline.join(out_lines)


ARABIC_RE = re.compile(r"[؀-ۿ]")


def has_arabic(s: str) -> bool:
    return bool(ARABIC_RE.search(s))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for t in sys.argv[1:]:
        print(to_visual(t))
