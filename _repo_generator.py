#!/usr/bin/env python3
"""
Mosestyle repo generator (verbose)
- Zips each add-on under ./repo/<addon_id>/
- Writes ./repo/addons.xml and ./repo/addons.xml.md5
- Copies latest repository zip to repo root
- Writes/updates index.html
Run from the repo root:
  py -3 _repo_generator.py   # Windows
  python _repo_generator.py  # if python is 3.x
"""

import os, io, sys, zipfile, hashlib, shutil
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.dirname(__file__))
REPO_SRC = os.path.join(ROOT, "repo")
ZIPS_DIR = os.path.join(ROOT, "zips")
IGNORE = {".git", ".github", "__pycache__", ".DS_Store", "Thumbs.db"}

def say(m): print(f"[generator] {m}", flush=True)
def read_text(p):  return io.open(p, "r", encoding="utf-8").read()
def write_text(p,s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def md5_hex(s):    return hashlib.md5(s.encode("utf-8")).hexdigest()

def ensure_layout():
    say(f"cwd: {os.getcwd()}")
    if not os.path.isdir(REPO_SRC):
        say("ERROR: ./repo/ not found"); sys.exit(1)
    entries = [e for e in os.listdir(REPO_SRC) if os.path.isdir(os.path.join(REPO_SRC, e))]
    if not entries: say("ERROR: ./repo/ has no add-on folders"); sys.exit(1)
    say(f"./repo/ contains: {', '.join(entries)}")

def zip_addon(src_dir, addon_id, version):
    out_dir = os.path.join(ZIPS_DIR, addon_id)
    os.makedirs(out_dir, exist_ok=True)
    out_zip = os.path.join(out_dir, f"{addon_id}-{version}.zip")
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE]
            for name in files:
                if name in IGNORE: continue
                ap = os.path.join(root, name)
                rp = os.path.relpath(ap, src_dir)
                z.write(ap, arcname=os.path.join(addon_id, rp))
    say(f"ZIPPED: {addon_id}-{version} -> {os.path.relpath(out_zip, ROOT)}")
    return out_zip

def collect_addons():
    items = []
    for entry in sorted(os.listdir(REPO_SRC)):
        src = os.path.join(REPO_SRC, entry)
        if not os.path.isdir(src) or entry in IGNORE: continue
        ax = os.path.join(src, "addon.xml")
        if not os.path.isfile(ax):
            say(f"SKIP: {entry} (no addon.xml)"); continue
        root = ET.parse(ax).getroot()
        addon_id = root.attrib.get("id"); version = root.attrib.get("version")
        if not addon_id or not version:
            say(f"ERROR: {ax} missing id or version"); sys.exit(1)
        items.append((addon_id, version, ax, src))
    if not items:
        say("ERROR: no valid add-ons found in ./repo/"); sys.exit(1)
    return items

def build_addons_xml(paths):
    parts = []
    for p in paths:
        t = read_text(p)
        if t.lstrip().startswith("<?xml"): t = t[t.find("?>")+2:]
        parts.append(t.strip())
    return '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n' + "\n\n".join(parts) + "\n</addons>\n"

def write_index_html(latest_repo_zip):
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Mosestyle Kodi Repo</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.5">
<h1 style="margin:0 0 8px">Mosestyle Kodi Repository</h1>
<p>Install this zip in Kodi:</p>
<p><a href="{latest_repo_zip}">{latest_repo_zip}</a></p>
<hr><p><strong>Repo index:</strong> <a href="repo/addons.xml">addons.xml</a> · <a href="repo/addons.xml.md5">md5</a></p>
<p><strong>ZIP folders:</strong></p><ul>""" + "".join(
        f'<li><a href="zips/{d}/">{d}/</a></li>' for d in sorted(os.listdir(ZIPS_DIR))
        if os.path.isdir(os.path.join(ZIPS_DIR, d))
    ) + f"""</ul>
<p><strong>Builds:</strong> <a href="builds/">builds/</a></p>
<p style="color:#888">Updated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</p>
</body></html>"""
    write_text(os.path.join(ROOT, "index.html"), html)
    say("Wrote index.html")

def main():
    ensure_layout()
    addons = collect_addons()
    addon_xmls, repo_zips = [], []
    for addon_id, version, addon_xml, src in addons:
        out = zip_addon(src, addon_id, version)
        addon_xmls.append(addon_xml)
        if addon_id == "repository.mosestyle":
            repo_zips.append((version, out))

    merged = build_addons_xml(addon_xmls)
    write_text(os.path.join(ROOT, "repo", "addons.xml"), merged)
    write_text(os.path.join(ROOT, "repo", "addons.xml.md5"), md5_hex(merged))
    say("WROTE: repo/addons.xml & repo/addons.xml.md5")

    if repo_zips:
        repo_zips.sort(key=lambda x: x[0])
        ver, path = repo_zips[-1]
        dest = f"repository.mosestyle-{ver}.zip"
        shutil.copy2(path, os.path.join(ROOT, dest))
        say(f"COPIED: {dest} to repo root")
        write_index_html(dest)

    say("Done. Commit & push: /repo /zips repository.mosestyle-<ver>.zip index.html (and /builds if used)")

if __name__ == "__main__":
    main()
