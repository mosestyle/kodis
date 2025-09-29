#!/usr/bin/env python3
"""
Mosestyle repo generator (ultra-verbose, Windows-friendly)
- Zips each add-on under ./repo/<addon_id>/
- Writes ./repo/addons.xml and ./repo/addons.xml.md5
- Copies newest repository zip to repo root
- Writes/updates ./index.html
Run from the folder that contains:  _repo_generator.py, repo\ (sources)
"""

import os, sys, io, zipfile, hashlib, shutil
from xml.etree import ElementTree as ET
from datetime import datetime

def say(msg):
    print(f"[generator] {msg}", flush=True)

ROOT = os.path.abspath(os.path.dirname(__file__))
REPO_SRC = os.path.join(ROOT, "repo")
ZIPS_DIR = os.path.join(ROOT, "zips")
IGNORE = {".git", ".github", "__pycache__", ".DS_Store", "Thumbs.db"}

def read_text(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()

def write_text(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

def md5_hex(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def collect_addons():
    if not os.path.isdir(REPO_SRC):
        say("ERROR: ./repo/ folder not found next to _repo_generator.py")
        return []
    entries = []
    for name in sorted(os.listdir(REPO_SRC)):
        path = os.path.join(REPO_SRC, name)
        if not os.path.isdir(path) or name in IGNORE:
            continue
        ax = os.path.join(path, "addon.xml")
        if not os.path.isfile(ax):
            say(f"SKIP: {name} (no addon.xml)")
            continue
        try:
            root = ET.parse(ax).getroot()
        except Exception as e:
            say(f"ERROR parsing {ax}: {e}")
            continue
        addon_id = root.attrib.get("id")
        version  = root.attrib.get("version")
        if not addon_id or not version:
            say(f"ERROR: {ax} missing id or version")
            continue
        entries.append((addon_id, version, ax, path))
    return entries

def zip_addon(src_dir, addon_id, version):
    out_dir = os.path.join(ZIPS_DIR, addon_id)
    os.makedirs(out_dir, exist_ok=True)
    out_zip = os.path.join(out_dir, f"{addon_id}-{version}.zip")
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE]
            for f in files:
                if f in IGNORE: continue
                ap = os.path.join(root, f)
                rp = os.path.relpath(ap, src_dir)
                z.write(ap, arcname=os.path.join(addon_id, rp))
    say(f"ZIPPED: {addon_id}-{version} -> {os.path.relpath(out_zip, ROOT)}")
    return out_zip

def build_addons_xml(paths):
    parts = []
    for p in paths:
        t = read_text(p)
        if t.lstrip().startswith("<?xml"):
            t = t[t.find("?>")+2:]
        parts.append(t.strip())
    merged = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n' + "\n\n".join(parts) + "\n</addons>\n"
    return merged

def write_index_html(latest_repo_zip_name):
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Mosestyle Kodi Repo</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.5">
<h1 style="margin:0 0 8px">Mosestyle Kodi Repository</h1>
<p>Install this zip in Kodi to add the repository:</p>
<p><a href="{latest_repo_zip_name}">{latest_repo_zip_name}</a></p>
<hr>
<p><strong>Repo index:</strong> <a href="repo/addons.xml">addons.xml</a> &middot; <a href="repo/addons.xml.md5">addons.xml.md5</a></p>
<p><strong>ZIP folders:</strong></p>
<ul>""" + "".join(
        f'<li><a href="zips/{d}/">{d}/</a></li>' for d in sorted(os.listdir(ZIPS_DIR)) if os.path.isdir(os.path.join(ZIPS_DIR, d))
    ) + f"""</ul>
<p><strong>Builds:</strong> <a href="builds/">builds/</a></p>
<p style="color:#888">Updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</p>
</body></html>"""
    write_text(os.path.join(ROOT, "index.html"), html)
    say("UPDATED: index.html")

def main():
    say(f"Python: {sys.version}")
    say(f"cwd: {os.getcwd()}")
    say(f"script dir: {ROOT}")
    if not os.path.isdir(REPO_SRC):
        say("ERROR: Missing ./repo/ folder. Create it and put your add-ons in there.")
        return
    addons = collect_addons()
    if not addons:
        say("ERROR: No valid add-ons found under ./repo/. Expect folders like repository.mosestyle/, plugin.program.mosestylebuild/, service.mosestyle.config/")
        return

    addon_xmls = []
    repo_zip_candidates = []
    for addon_id, version, addon_xml, src in addons:
        out_zip = zip_addon(src, addon_id, version)
        addon_xmls.append(addon_xml)
        if addon_id == "repository.mosestyle":
            repo_zip_candidates.append((version, out_zip))

    merged = build_addons_xml(addon_xmls)
    write_text(os.path.join(ROOT, "repo", "addons.xml"), merged)
    write_text(os.path.join(ROOT, "repo", "addons.xml.md5"), md5_hex(merged))
    say("WROTE: repo/addons.xml + repo/addons.xml.md5")

    if repo_zip_candidates:
        repo_zip_candidates.sort(key=lambda x: x[0])
        latest_ver, latest_zip = repo_zip_candidates[-1]
        dest_name = f"repository.mosestyle-{latest_ver}.zip"
        shutil.copy2(latest_zip, os.path.join(ROOT, dest_name))
        say(f"COPIED: {dest_name} to repo root")
        write_index_html(dest_name)

    say("DONE. Commit & push: /repo /zips repository.mosestyle-<ver>.zip index.html (and /builds if used)")

if __name__ == "__main__":
    main()
