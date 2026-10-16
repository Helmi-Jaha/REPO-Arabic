# R.E.P.O. Arabic Translation — تعريب R.E.P.O.

An unofficial Arabic fan translation of **R.E.P.O.** (semiwork) for game version **v0.4.4.3** (Steam build 23363152).
This repository contains the full source: every translated string, the text-shaping and build tools, the installer
script, and the steps to rebuild the release package from scratch.

**There is no compiled program and no code mod.** The release has a PowerShell installer (plain text, source in
`package_src/installer/repo_arabic.ps1`), the Arabic string tables, and a font-data file built from the Changa font.

## What the installer does
1. Checks the game version: SHA-256 of `REPO_Data/Managed/Assembly-CSharp.dll` and of `REPO_Data/sharedassets0.assets`.
   Unknown versions are refused and nothing is changed.
2. Copies `HUD.tsv`, `Menu.tsv` and `Game.tsv` to `REPO_Data/StreamingAssets/Localizations/`. This is the
   translation-override folder documented by the developers in `Localizations/Default/readme.txt`.
3. Overwrites the bytes of the embedded Arabic fallback font inside `sharedassets0.assets` in place.
   - The region is at offset `0x1B9B970` and is 843,008 bytes long.
   - The new data is a static Changa instance, zero-padded to the same length, so the file's structure is unchanged.
   - The original bytes are saved first and verified by SHA-256.
   - The whole file is verified after patching, and the change is rolled back on any mismatch.
4. Uninstall restores the original bytes (verified) and removes only its own files.
   Save data (`AppData\LocalLow`) is never touched. No administrator rights are needed, and nothing is downloaded.

## Repository layout
| Path | Contents |
|---|---|
| `translation/ar_{HUD,Menu,Game}.tsv` | Arabic translation in logical (normal) order, `KEY<TAB>text`, UTF-8 |
| `tools/ar_shape.py` | Arabic contextual shaping, lam-alef ligatures, simplified BiDi reordering and line wrapping for display |
| `tools/build.py` | Validates every key (placeholders, tags, leftover Latin, glyph coverage, slider length) and writes `build/Localizations/*.tsv` |
| `tools/patch_font_cmap.py` | Adds Arabic Presentation Forms-B code points to the Changa cmap, mapped to Changa's own GSUB glyphs |
| `tools/make_font_patch.py` | Builds `font_region.bin` (static Changa, padded) plus offsets and hashes from the original game file |
| `tools/make_package.py` | Assembles and zips the release package |
| `tools/find_fonts.py` | Extracts the game's own fonts (Teko, Noto Sans Arabic, Liberation) locally, for the glyph-coverage check |
| `tools/test_shape.py`, `tools/test_installer.ps1` | Shaping self-test and installer tests (run against a copy of the game) |
| `package_src/installer/repo_arabic.ps1` | Installer and uninstaller source |
| `package_src/docs/` | User documentation (Arabic), credits and licenses |
| `third_party/changa/` | Changa variable font + its SIL OFL 1.1 licence (unmodified, from github.com/google/fonts) |

The game's English text and game files are **not** included. You copy them from your own installation (step 2 below).

## Building the release
Requirements: Windows, R.E.P.O. v0.4.4.3 installed, Python 3.10+, and
`pip install fonttools arabic-reshaper python-bidi`.

```powershell
# 1. from the repository root
$game = "C:\Program Files (x86)\Steam\steamapps\common\REPO"

# 2. English source tables (keys + reference text) from your own game copy
New-Item -ItemType Directory -Force original\en | Out-Null
Copy-Item "$game\REPO_Data\StreamingAssets\Localizations\Default\*.tsv" original\en\

# 3. the game's own fonts, extracted locally for the glyph-coverage check (read-only)
python -I tools\find_fonts.py "$game\REPO_Data\sharedassets0.assets" extracted\fonts

# 4. shaping self-test
python -I tools\test_shape.py

# 5. display tables -> build\Localizations\*.tsv (exit code 1 on any validation error)
python -I tools\build.py

# 6. font: add presentation forms to Changa, then build the in-place font region
New-Item -ItemType Directory -Force build_fonts | Out-Null
python -I tools\patch_font_cmap.py third_party\changa\Changa-VariableFont_wght.ttf build_fonts\REPOAR-Changa.ttf "REPO AR Changa"
python -I tools\make_font_patch.py "$game\REPO_Data\sharedassets0.assets" build_fonts\REPOAR-Changa.ttf fontpatch_build --wght 500

# 7. package -> package\REPO_Arabic_v1.1.1\ and .zip
python -I tools\make_package.py

# 8. optional: installer tests on a COPY of the game folder
powershell -ExecutionPolicy Bypass -File tools\test_installer.ps1 -Game D:\REPO_test_copy
```

Steps 5–6 are deterministic for the same tool versions. `manifest.json` in the package lists the SHA-256 of every
payload file, so you can compare a rebuild with the published release.

## Credits & licences
- Translation and tools: B_H_W.
- Font: Changa, Copyright 2018 The Changa Project Authors (https://github.com/googlefonts/changa-vf), SIL Open Font
  License 1.1 (`third_party/changa/OFL.txt`). The release contains a modified static copy named "REPO AR Changa".
- R.E.P.O. belongs to semiwork. This is an unofficial fan project.
