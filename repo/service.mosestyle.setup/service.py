# Mosestyle First-Run Config (v1.0.2)
# - JSON-RPC only (no file edits) => won't reset guisettings.xml
# - Robust enum handling for refresh rate, 4:3 mode, subtitle style
# - Robust language handling (names + ISO codes)
# - Waits for GUI to be ready; applies once; logs results; disables itself

import json, time, xbmc, xbmcaddon, xbmcvfs, os

ADDON    = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
DATA_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
RUN_FLAG = os.path.join(DATA_DIR, "done.flag")
LOG_FILE = os.path.join(DATA_DIR, "applied.json")

def rpc(method, params=None):
    payload = {"jsonrpc":"2.0","id":1,"method":method}
    if params is not None: payload["params"] = params
    return json.loads(xbmc.executeJSONRPC(json.dumps(payload)))

def wait_home(timeout=60):
    mon = xbmc.Monitor(); end=time.time()+timeout
    while time.time()<end and not mon.abortRequested():
        if xbmc.getCondVisibility('Window.IsActive(home)'):
            xbmc.sleep(600)  # let skin settle
            return True
        xbmc.sleep(200)
    return False

def get_maps():
    res = rpc("Settings.GetSettings", {"level":"expert"})
    settings = res.get("result",{}).get("settings",[])
    by_id    = {s["id"]: s for s in settings if "id" in s}
    by_lbl   = {(s.get("label","") or "").strip().lower(): s["id"] for s in settings if "id" in s}
    return by_id, by_lbl

def get_current(setting):
    return rpc("Settings.GetSettingValue", {"setting": setting}).get("result",{}).get("value",None)

def set_value(setting, desired):
    """Try a few representations to fit whatever this Kodi build expects."""
    cur = get_current(setting)

    # Normalize common enums
    attempts = []

    # refresh rate: off/onstartstop/always OR 0/1/2
    if setting in ("videoplayer.adjustrefreshrate","videoscreen.adjustrefreshrate"):
        if isinstance(desired, str):
            m = {"off":0, "onstartstop":1, "always":2}
            attempts = [desired.lower(), m.get(desired.lower(), desired)]
        else:
            attempts = [desired]
    # 4:3 display mode often int enum: 0=Normal, 1=Stretch 16:9, 2=Zoom
    elif setting in ("videoplayer.displayas","videoplayer.scalingmethod43"):
        if isinstance(desired, str):
            m = {"normal":0, "stretch 16:9":1, "stretch16:9":1, "zoom":2}
            attempts = [desired, desired.lower(), m.get(desired.lower(), desired)]
        else:
            attempts = [desired]
    # GUI sound mode: 0=Never,1=Only when video,2=Always
    elif setting == "audiooutput.guisoundmode":
        m = {"never":0, "onlywhenvideo":1, "only when video playing":1, "always":2}
        attempts = [m.get(str(desired).lower(), desired)]
    # Subtitle style: 0=Normal,1=Bold,2=Italic,3=Bold Italic
    elif setting == "subtitles.style":
        m = {"normal":0,"bold":1,"italic":2,"bold italic":3,"bolditalic":3}
        attempts = [m.get(str(desired).lower(), desired)]
    # Preferred languages accept names and codes
    elif setting in ("locale.audiolanguage","locale.subtitlelanguage"):
        if isinstance(desired, str):
            attempts = [desired, desired.title(), desired.lower(), "en"]
        else:
            attempts = [desired]
    # Subtitle download languages: list of names or codes
    elif setting == "subtitles.languages":
        if isinstance(desired, (list,tuple)):
            names  = [str(x).title() for x in desired]
            lower  = [str(x).lower() for x in desired]
            iso    = []
            for x in desired:
                s=str(x).lower()
                iso.append({"english":"eng","en":"eng","swedish":"swe","sv":"swe"}.get(s, s))
            attempts = [names, lower, iso]
        else:
            attempts = [[str(desired).title()],[str(desired).lower()]]
    else:
        attempts = [desired]

    # Cast to current type when possible
    def cast_like(val, ref):
        try:
            if isinstance(ref, bool):  return bool(val)
            if isinstance(ref, int):   return int(val)
            if isinstance(ref, float): return float(val)
            if isinstance(ref, list):  return list(val) if isinstance(val,(list,tuple,set)) else [val]
            if isinstance(ref, str):   return str(val)
        except: pass
        return val

    for a in attempts:
        v = cast_like(a, cur)
        r = rpc("Settings.SetSettingValue", {"setting":setting,"value":v})
        if r.get("result") == "OK":
            return v

    # final raw try
    r = rpc("Settings.SetSettingValue", {"setting":setting,"value":desired})
    return desired if r.get("result")=="OK" else None

WANTS = [
    # Player » Videos
    (["videoplayer.seeksteps","videoscreen.seeksteps"], "skip steps", [-10,10]),
    (["videoplayer.seekdelay","videoscreen.seekdelay"], "skip delay", 750),
    (["videoplayer.adjustrefreshrate","videoscreen.adjustrefreshrate"], "adjust display refresh rate", "always"),
    (["videoplayer.syncplayback","videoplayer.synctype"], "sync playback to display", True),
    (["videoplayer.minimizeblackbars","videoplayer.zoomamount"], "minimise black bars", 20),
    (["videoplayer.displayas","videoplayer.scalingmethod43"], "display 4:3 videos as", "stretch16:9"),

    # Player » Language
    (["locale.audiolanguage"], "preferred audio language", "English"),
    (["locale.subtitlelanguage"], "preferred subtitle language", "English"),

    # Player » Subtitles
    (["subtitles.align"], "position on screen", 0),
    (["subtitles.style"], "style", "bold"),
    (["subtitles.languages"], "languages to download subtitles for", ["English","Swedish"]),
    (["subtitles.pauseonsearch"], "pause when searching for subtitles", True),
    (["subtitles.autoselect"], "auto download first subtitle", True),
    (["subtitles.tvshowsdefaultservice"], "default tv show service", "service.subtitles.a4ksubtitles"),
    (["subtitles.moviesdefaultservice"], "default movie service", "service.subtitles.a4ksubtitles"),

    # System » Audio
    (["audiooutput.guisoundmode"], "play gui sounds", "never"),

    # System » Add-ons
    (["addons.unknownsources"], "unknown sources", True),
    (["addons.updatefromrepo"], "update official add-ons from", "any"),

    # Media » General
    (["filelists.showparentdiritems"], "show parent folder items", False),

    # Interface » Regional
    (["locale.region"], "region default format", "Central Europe"),
]

def main():
    # run once
    if xbmcvfs.exists(RUN_FLAG):
        return

    xbmcvfs.mkdirs(DATA_DIR)
    wait_home(60)
    by_id, by_lbl = get_maps()

    applied, skipped = {}, []

    for cands, label, value in WANTS:
        # pick first candidate that exists; else by label text
        sel = next((cid for cid in cands if cid in by_id), None)
        if not sel:
            sel = by_lbl.get(label.lower())
        if not sel:
            skipped.append({"label":label, "reason":"setting not found", "candidates":cands})
            continue
        v = set_value(sel, value)
        if v is None:
            skipped.append({"id":sel, "label":label, "wanted":value, "reason":"set failed"})
        else:
            applied[sel] = {"label":label, "value":v}

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump({"applied":applied, "skipped":skipped}, f, ensure_ascii=False, indent=2)

    xbmc.executebuiltin('Notification(Mosestyle,First-run settings applied,4000)')
    # mark done & disable self
    with open(RUN_FLAG, "w") as f: f.write("ok")
    rpc("Addons.SetAddonEnabled", {"addonid":ADDON_ID, "enabled": False})

if __name__ == "__main__":
    main()
