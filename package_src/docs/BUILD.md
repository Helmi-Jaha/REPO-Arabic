# Building the R.E.P.O. Arabic localization from source

Requirements: Windows, Python 3.10+, `pip install fonttools arabic-reshaper` (and `python-bidi` for `test_shape.py`).

1. Copy the game's English sources (they are the developer's text and not redistributed here):
   `REPO_Data/StreamingAssets/Localizations/Default/{HUD,Menu,Game}.tsv` -> `original/en/`.
2. Edit translations only in `translation/ar_{HUD,Menu,Game}.tsv`
   (logical-order Arabic, one `KEY<TAB>text` per line, UTF-8, `\n` for manual line breaks).
3. `python -I tools/test_shape.py` checks shaping and BiDi against arabic-reshaper and python-bidi.
4. `python -I tools/build.py` validates every key: placeholders, tags, leftover Latin, glyph coverage,
   and the 18-char slider limit. It writes `build/Localizations/*.tsv` (display copies) and
   `reports/inventory.csv`. The exit code is non-zero on any error.
   Glyph coverage needs the game's fonts extracted to `extracted/fonts/` (`tools/find_fonts.py`).
5. `python -I tools/make_package.py` assembles and zips the package.

## Why the display files look reversed
R.E.P.O. renders text with TextMeshPro in the English locale slot without Arabic shaping or BiDi.
`tools/ar_shape.py` therefore produces, from the logical translation:
- contextual presentation forms, including the mandatory lam-alef ligatures;
- simplified Unicode BiDi visual order (RTL paragraph); placeholders `{x}`, `[input]` and emoticons stay atomic;
- logical-order line wrapping, because TMP's own wrapping would reverse line order;
- the shipped font patch: static Changa (presentation forms added by tools/patch_font_cmap.py) written over the
  embedded Arabic font bytes of sharedassets0.assets by tools/make_font_patch.py (same length, zero-padded).
  With it no per-glyph spacing fix is needed (ADVANCE_FIX = 0; the old variable Noto font needed ~0.2).
- Slider option values: the game cuts the raw string to 18 characters (`MenuSlider.SetCustomText`), keep them short.
- KEY_CSPACE: negative <cspace> for components with decorative positive letter-spacing.
