"""Assemble the distributable package: package/REPO_Arabic_v<version>/ + .zip

Contains only our translations, installer, docs and build sources - never game files, the
English source text, or save data.  Usage: python -I make_package.py
"""
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

VERSION = "1.1.1"
SUPPORTED = [{
    "game_version": "v0.4.4.3",
    "steam_build": 23363152,
    "assembly_csharp_sha256": "CE995A182DDC884EA965E87786F1986248D9616300FA825BCC04BCA671EE6526",
}]

root = Path(__file__).resolve().parents[1]
src = root / "package_src"
out = root / "package" / f"REPO_Arabic_v{VERSION}"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def main() -> int:
    if shutil.which("python") is None:
        pass
    if out.exists():
        shutil.rmtree(out)
    (out / "files" / "Localizations").mkdir(parents=True)
    (out / "installer").mkdir()
    payload = []
    for t in ("HUD", "Menu", "Game"):
        f = root / "build" / "Localizations" / f"{t}.tsv"
        d = out / "files" / "Localizations" / f.name
        shutil.copy2(f, d)
        payload.append({"name": f.name, "sha256": sha(d), "size": d.stat().st_size})
    # in-place font patch (static Changa replaces the embedded Arabic font bytes, same length)
    fp_dir = root / "fontpatch_build"
    font_patch = json.loads((fp_dir / "font_patch.json").read_text(encoding="utf-8"))
    shutil.copy2(fp_dir / "font_region.bin", out / "files" / "font_region.bin")
    assert sha(out / "files" / "font_region.bin") == font_patch["region_sha256"]
    shutil.copy2(root / "third_party" / "changa" / "OFL.txt", out / "LICENSE_Changa_OFL.txt")
    (out / "manifest.json").write_text(json.dumps({
        "package": "REPO_Arabic", "version": VERSION, "supported": SUPPORTED, "payload": payload,
        "font_patch": font_patch,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    # PowerShell 5.1 needs a BOM to read the Arabic literals as UTF-8
    ps = (src / "installer" / "repo_arabic.ps1").read_text(encoding="utf-8-sig")
    (out / "installer" / "repo_arabic.ps1").write_text(ps.replace("\r\n", "\n").replace("\n", "\r\n"), encoding="utf-8-sig")
    for name, action in (("Install_Arabic.cmd", "Install"), ("Uninstall_Arabic.cmd", "Uninstall")):
        (out / name).write_bytes((
            "@echo off\r\n"
            f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\\repo_arabic.ps1" -Action {action} %*\r\n'
            "if errorlevel 1 pause\r\n").encode("ascii"))
    for d in (src / "docs").iterdir():
        shutil.copy2(d, out / d.name)
    (out / "SUPPORTED_VERSIONS.txt").write_text(
        "\n".join(f"R.E.P.O. {s['game_version']}  (Steam build {s['steam_build']})\n"
                  f"  Assembly-CSharp.dll SHA-256: {s['assembly_csharp_sha256']}" for s in SUPPORTED) + "\n",
        encoding="utf-8")
    (out / "CHANGELOG.txt").write_text(
        f"{VERSION}\n- Reproducible build: font tools keep the source timestamp; full source published.\n"
        "1.1.0\n- Decorative Arabic font (Changa, SIL OFL) via an in-place font-data patch: no code mod, no [MODDED] tag.\n"
        "- Spacing recalibrated for the new font; regions/ping shortened; dialog wrap 32.\n"
        "1.0.0\n- First release: all 603 official localization strings in Arabic, display shaping + BiDi,\n"
        "  installer with version check, backup and restore.\n", encoding="utf-8")
    # build sources
    s_out = out / "source"
    (s_out / "translation").mkdir(parents=True)
    (s_out / "tools").mkdir()
    for f in (root / "translation").glob("ar_*.tsv"):
        if f.name == "ar_phrases.tsv":  # BepInEx add-on only (not shipped)
            continue
        shutil.copy2(f, s_out / "translation" / f.name)
    for n in ("ar_shape.py", "build.py", "test_shape.py", "make_package.py",
              "find_fonts.py", "patch_font_cmap.py", "make_font_patch.py"):
        shutil.copy2(root / "tools" / n, s_out / "tools" / n)
    shutil.copytree(src / "installer", s_out / "installer_src")
    # zip
    z = out.parent / (out.name + ".zip")
    if z.exists():
        z.unlink()
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(out.parent))
    print(f"package: {out}\nzip: {z} ({z.stat().st_size} bytes)")
    for f in payload:
        print(f"  {f['name']}  {f['sha256']}  {f['size']} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
