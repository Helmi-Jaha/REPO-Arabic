"""Build + validate the Arabic localization for R.E.P.O.

Inputs  : original/en/{HUD,Menu,Game}.tsv   (copied from the game's Localizations/Default, hash-checked)
          translation/ar_{HUD,Menu,Game}.tsv (logical-order Arabic, the editable source of truth)
          translation/layout.tsv             (optional per-key wrap widths, overrides the rules below)
Outputs : build/Localizations/{HUD,Menu,Game}.tsv  (display copies for the game)
          reports/inventory.csv                    (full inventory with status + checks)
          reports/validation.txt                   (summary; exit code 1 on any error)

Usage: python -I build.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from fontTools.ttLib import TTFont

from ar_shape import TOKEN_RE, has_arabic, to_visual

ROOT = Path(__file__).resolve().parents[1]
TABLES = ["HUD", "Menu", "Game"]

# Wrap widths (in Arabic characters) per key pattern; first match wins. None = never wrap.
WRAP_RULES = [
    (r"^POPUP\..*\.BODY$", 32),        # Changa is wider than Noto: 36 overflowed (u2_public.png)
    (r"^SPLASH\..*\.TEXT$", 60),
    (r"^SAVES\.PAGE_INFO\.DESCRIPTION$", 42),  # wide panel (u3_saves.png)
    (r"^TUTORIAL\..*\.DUMMY_TEXT$", 40),
    (r"^TUTORIAL\..*\.TEXT$", 55),
    (r"^MOONS\..*\.ATTRIBUTE_\d$", 45),
]

# Slider option values: MenuSlider.SetCustomText cuts the RAW string to 18 chars + "..." (IL verified),
# so they get no per-glyph <space> tags, only one short <cspace=N> (pixel units) when it still fits.
SLIDER_RE = re.compile(r"^SETTINGS\.(CAMERA_ANIMATION|RICH_PRESENCE|WINDOW_MODE|MAX_FPS|LIGHT_DISTANCE|"
                       r"SHADOW_QUALITY|SHADOW_DISTANCE|RENDER_SIZE|MIC_DEVICE)\.")
SLIDER_MAX = 18
SLIDER_CSPACE = {g: 0 for g in ("CAMERA_ANIMATION", "RICH_PRESENCE", "WINDOW_MODE", "MAX_FPS", "LIGHT_DISTANCE",
                                "SHADOW_QUALITY", "SHADOW_DISTANCE", "RENDER_SIZE", "MIC_DEVICE")}  # calibrated in-game (t13_zoom.png)


# Add-on profile (BepInEx add-on with its own Changa/Lalezar atlases): correct glyph metrics, so no
# per-glyph advance fix; headings/menus get the Lalezar display font through TMP's <font> tag.
ADDON = "--addon" in sys.argv
ADDON_ADV_FIX = 0.0
HEADER_FONT = "REPO_AR_Lalezar"
HEADER_RE = re.compile(r"(\.HEADER$|^MAIN\.|^ESC\.|^BIG_MESSAGE\.|^LEVEL\.NAME\.|^LOADING\.LEVEL\.|^ARENA\.|"
                       r"^MOONS\.MOON_\d\.NAME$|^TUTORIAL\.TRANSITION_TEXT$|^EXTRACTION\.|"
                       r"^TRUCK_SCREEN\.(DESTROYING|STARTING|HITTING))")


def display(key: str, logical: str, wrap) -> str:
    if not ADDON:
        return to_visual(logical, max_chars=wrap)
    vis = to_visual(logical, max_chars=wrap, adv_fix=ADDON_ADV_FIX)
    if HEADER_RE.search(key):
        vis = f'<font="{HEADER_FONT}">{vis}</font>'
    return vis


def slider_visual(key: str, logical: str) -> str:
    vis = to_visual(logical, adv_fix=0)
    n = 0 if ADDON else SLIDER_CSPACE[SLIDER_RE.match(key).group(1)]
    if not n:
        return vis
    tagged = f"<cspace={n:g}>{vis}"
    return tagged if len(tagged) <= SLIDER_MAX else vis


# Components that use decorative positive letter-spacing (fine for Latin, breaks Arabic joins):
# counter it with a negative <cspace>, calibrated in-game (reports/shots/u6_header_zoom.png).
KEY_CSPACE = {"SAVES.SINGLEPLAYER_MODE": "-0.15em", "SAVES.MULTIPLAYER_MODE": "-0.15em"}

# Latin words that may legitimately stay in an Arabic string (outside placeholders)
ALLOWED_LATIN = {"R.E.P.O."}

PLACEHOLDER_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}|\[[A-Za-z0-9_]+\]")
TAG_RE = re.compile(r"</?([a-z\-]+)[^<>]*>")


def read_tsv(p: Path) -> dict[str, str]:
    out = {}
    for n, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise SystemExit(f"{p.name}:{n}: expected 2 tab-separated columns, got {len(parts)}")
        if parts[0] in out:
            raise SystemExit(f"{p.name}:{n}: duplicate key {parts[0]}")
        out[parts[0]] = parts[1]
    return out


def tags_balanced(s: str) -> bool:
    stack = []
    for m in TAG_RE.finditer(s):
        name = m.group(1)
        if m.group(0).startswith("</"):
            if not stack or stack[-1] != name:
                return False
            stack.pop()
        elif name not in ("br", "sprite"):
            stack.append(name)
    return not stack


def wrap_for(key: str, layout: dict[str, str]):
    if key in layout:
        v = layout[key]
        return None if v in ("", "none", "0") else float(v)
    for pat, w in WRAP_RULES:
        if re.match(pat, key):
            return w
    return None


def font_cmaps():
    fonts = {}
    for f in (ROOT / "extracted" / "fonts").glob("*.ttf"):
        if f.name.startswith(("Teko", "Noto_Sans_Arabic", "Liberation")):
            fonts[f.name] = set(TTFont(f).getBestCmap())
    return fonts


def build_phrases(covered) -> list:
    """Add-on only: exact hard-coded English UI phrases -> Arabic display text (translation/ar_phrases.tsv)."""
    errs, out = [], []
    p = ROOT / "translation" / "ar_phrases.tsv"
    if not p.exists():
        return errs
    for en, ar in read_tsv(p).items():
        vis = to_visual(ar, adv_fix=ADDON_ADV_FIX)
        if not has_arabic(ar):
            errs.append(f"phrases:{en}: no Arabic")
        out.append(f"{en}\t{vis}")
    (ROOT / "addon_build" / "phrases.tsv").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"phrases: {len(out)}")
    return errs


def main() -> int:
    layout = {}
    lp = ROOT / "translation" / "layout.tsv"
    if lp.exists():
        layout = read_tsv(lp)
    cmaps = font_cmaps()
    covered = set().union(*cmaps.values()) if cmaps else set()
    errors, warnings, rows = [], [], []
    outdir = ROOT / ("addon_build" if ADDON else "build") / "Localizations"
    outdir.mkdir(parents=True, exist_ok=True)
    total = translated = 0
    for t in TABLES:
        en = read_tsv(ROOT / "original" / "en" / f"{t}.tsv")
        ar = read_tsv(ROOT / "translation" / f"ar_{t}.tsv")
        for k in ar:
            if k not in en:
                errors.append(f"{t}:{k}: key not in English source (typo or removed key)")
        lines = []
        for k, src in en.items():
            total += 1
            a = ar.get(k, "").strip()
            status, notes = "translated", []
            if not a:
                status = "missing"
                errors.append(f"{t}:{k}: missing translation")
            else:
                if not has_arabic(a):
                    status = "suspect"
                    errors.append(f"{t}:{k}: no Arabic letters in translation")
                # Smart-format separators (e.g. list "and") are translatable; compare variable names + formatter only
                def ph(s):
                    return sorted(re.sub(r"^\{(\w+(?::\w+)?).*\}$", r"{\1}", p) for p in PLACEHOLDER_RE.findall(s))
                if ph(src) != ph(a):
                    errors.append(f"{t}:{k}: placeholders differ: en={PLACEHOLDER_RE.findall(src)} ar={PLACEHOLDER_RE.findall(a)}")
                if not tags_balanced(a):
                    errors.append(f"{t}:{k}: unbalanced rich-text tags")
                plain = TOKEN_RE.sub(" ", a)
                for word in re.findall(r"[A-Za-z][A-Za-z.]*", plain):
                    if word not in ALLOWED_LATIN:
                        errors.append(f"{t}:{k}: leftover Latin text '{word}'")
                if re.search(r"[ً-ٰٟـ]", a):
                    warnings.append(f"{t}:{k}: contains harakat/tatweel (TMP cannot position marks)")
                if src.count("\\n") and not a.count("\\n"):
                    warnings.append(f"{t}:{k}: English has manual line breaks, Arabic has none")
            w = wrap_for(k, layout)
            if a and SLIDER_RE.match(k):
                vis = slider_visual(k, a)
                if len(vis) > SLIDER_MAX:
                    errors.append(f"{t}:{k}: slider value longer than {SLIDER_MAX} raw chars, the game will cut it")
            else:
                vis = display(k, a, w) if a else src
                if a and k in KEY_CSPACE:
                    vis = f"<cspace={KEY_CSPACE[k]}>{vis}</cspace>"
            if covered:
                missing = sorted({c for c in TOKEN_RE.sub("", vis) if ord(c) > 0x20 and ord(c) not in covered})
                if missing:
                    errors.append(f"{t}:{k}: glyphs not in game fonts: {' '.join(f'U+{ord(c):04X}' for c in missing)}")
            if "\t" in vis or "\n" in vis:
                errors.append(f"{t}:{k}: display text contains raw tab/newline")
            if status == "translated":
                translated += 1
            lines.append(f"{k}\t{vis}")
            rows.append({"id": f"{t}:{k}", "table": t, "key": k, "en": src, "ar": a, "display": vis,
                         "wrap": w or "", "status": status, "review": "self-reviewed" if status == "translated" else ""})
        (outdir / f"{t}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rep = ROOT / "reports"
    rep.mkdir(exist_ok=True)
    if not ADDON:
        with (rep / "inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    if ADDON:
        errors += build_phrases(covered)
    summary = [f"keys: {total}  translated: {translated}  errors: {len(errors)}  warnings: {len(warnings)}",
               f"fonts checked: {', '.join(sorted(cmaps)) or 'NONE'}"] + ["ERROR " + e for e in errors] + ["WARN  " + w for w in warnings]
    (rep / ("validation_addon.txt" if ADDON else "validation.txt")).write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary[:60]))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
