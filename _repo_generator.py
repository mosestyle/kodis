#!/usr/bin/env python3
# Build zips to repo/zips/, write addons.xml/md5 there, and copy the latest repo zip to the ROOT.
import argparse, hashlib, os, re, sys, zipfile, shutil
from pathlib import Path
from xml.etree import ElementTree as ET

SRC_DIR = Path("repo")
OUT_DIR = Path("repo/zips")
REPO_ID = "repository.mosestyle"
ROOT    = Path(".")

IGNORE = {".git","__pycache__",".DS_Store","Thumbs.db"}
SEMVER = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")

def semver_key(s):
    m = SEMVER.search(s) or ()
    a = int(m.group(1)) if m and m.group(1) else -1
    b = int(m.group(2)) if m and m.group(2) else -1
    c = int(m.group(3)) if m and m.group(3) else -1
    return (a,b,c,s)

def find_addons():
    for d in sorted(SRC_DIR.iterdir()):
        if d.name.lower()=="zips" or not d.is_dir(): continue
        ax = d/"addon.xml"
        if not ax.exists():
            print(f"[warn] {d}/addon.xml missing; skipping", file=sys.stderr); continue
        try:
            x = ET.fromstring(ax.read_text(encoding="utf-8"))
        except ET.ParseError as e:
            print(f"[warn] {d}/addon.xml parse error: {e}; skipping", file=sys.stderr); continue
        aid, ver = x.get("id"), x.get("version")
        if not aid or not ver:
            print(f"[warn] {d}: missing id/version; skipping", file=sys.stderr); continue
        yield d, aid, ver

def zip_addon(src, aid, ver):
    dst_dir = OUT_DIR/aid
    dst_dir.mkdir(parents=True, exist_ok=True)
    zp = dst_dir/f"{aid}-{ver}.zip"
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in IGNORE and (src/d).exists()]
            for fn in files:
                if fn in IGNORE: continue
                f = Path(root)/fn
                z.write(f, f.relative_to(src).as_posix())
    print(f"[ok] {zp}")
    return zp

def read_addon_xml_from_zip(zp):
    with zipfile.ZipFile(zp,"r") as z:
        for n in z.namelist():
            if n.split("/")[-1].lower()=="addon.xml":
                return z.read(n).decode("utf-8","replace")
    raise FileNotFoundError(f"addon.xml not in {zp}")

def build_addons_xml(zips):
    parts=[]
    for zp in zips:
        parts.append(read_addon_xml_from_zip(zp).strip())
    return "<addons>\n" + "\n\n".join(parts) + "\n</addons>\n"

def md5(text):
    import hashlib
    m=hashlib.md5(); m.update(text.encode("utf-8")); return m.hexdigest()

def latest_repo_zip():
    folder = OUT_DIR/REPO_ID
    if not folder.is_dir(): return None
    zps = sorted(folder.glob(f"{REPO_ID}-*.zip"), key=lambda p: semver_key(p.name))
    return zps[-1] if zps else None

def main():
    created=[]
    for src, aid, ver in find_addons():
        created.append(zip_addon(src, aid, ver))
    if not created:
        print("[err] No add-ons zipped. Aborting.", file=sys.stderr); sys.exit(1)

    xml = build_addons_xml(created)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR/"addons.xml").write_text(xml, encoding="utf-8")
    (OUT_DIR/"addons.xml.md5").write_text(md5(xml), encoding="utf-8")
    print(f"[ok] {OUT_DIR/'addons.xml'}")
    print(f"[ok] {OUT_DIR/'addons.xml.md5'}")

    # Copy latest repository zip to ROOT for your old 'index.html' link
    rz = latest_repo_zip()
    if rz:
        dst = ROOT/rz.name
        shutil.copy2(rz, dst)
        print(f"[ok] Copied {rz.name} to repo ROOT")

    # Minimal index.html like your old guide
    (ROOT/"index.html").write_text(
        f'<!DOCTYPE html>\n<a href="{(rz.name if rz else "repository.mosestyle-1.0.0.zip")}">'
        f'{(rz.name if rz else "repository.mosestyle-1.0.0.zip")}</a>\n',
        encoding="utf-8"
    )
    print("[ok] index.html")
    print("Done.")

if __name__ == "__main__":
    main()
