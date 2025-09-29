# Mosestyle First-Run Config (v1.0.4)
# - Waits for Home, extra settle time
# - Robust per-setting retries & type-casting
# - If anything applied, perform one-time clean restart to flush guisettings.xml
# - Writes done.flag before restart to avoid loops; disables itself afterwards

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

def wait_home(timeout=120, settle_ms=1500):
    mon = xbmc.Monitor(); end=time.time()+timeout
    while time.time()<end and not mon.abortRequested():
        if xbmc.getCondVisibility('Window.IsActive(home)'):
            xbmc.sleep(settle_ms)  # let skin/init finish
            return True
        xbmc.sleep(200)
    return False

def get_maps():
    # Ask for full 'expert' set; fall back to default if needed
    res = rpc("Settings.GetSettings", {"level":"expert"})
    if "result" not in res:
        res = rpc("Settings.GetSettings")
    settings = res.get("result",{}).get("settings",[])
    by_id    = {s["id"]: s for s in settings if "id" in s}
    by_lbl   = {(s.get("label","") or "").strip().lower(): s["id"] for s in settings if "id" in s}
    return by_id, by_lbl

def get_current(setting):
    return rpc("Settings.GetSettingValue", {"setting": setting}).get("result",{}).get("value",None)

def _attempt_set(setting, value):
    r = rpc("Settings.SetSettingValue", {"setting":setting,"value":value})
    return (r.get("result") == "OK")

def set_value_retry(setting, desired, max_tries=5, sleep_ms=250):
    """
    Try multiple representations (enum names/ints, language names/codes, lists),
    and retry a few times in case the settings backend isn't ready yet.
    """
    def cast_like(val, ref):
        try:
            if isinstance(ref, bool):  return bool(val)
            if isinstance(ref, int):   return int(val)
            if isinstance(ref, float): return float(val)
            if isinstance(ref, list):  return list(val) if isinstance(val,(list,tuple,set)) else [val]
            if isinstance(ref, str):   return str(val)
        except: pass
        return val

    cur = get_current(setting)
    attempts = []

    # Known enums & special cases
    if setting in ("videoplayer.adjustrefreshrate","videoscreen.adjustrefreshrate"):
        if isinstance(desired, str):
            m = {"off":0, "onstartstop":1, "always":2}
            attempts = [desired.lower(), m.get(desired.lower(), desired)]
        else:
            attempts = [desired]
    elif setting in ("videoplayer.displayas","videoplayer.scalingmethod43"):
        if isinstance(desired, str):
            m = {"normal":0, "stretch 16:9":1, "stretch16:9":1, "zoom":2}
            attempts = [desired, desired.lower(), m.get(desired.lower(), desired)]
        else:
            attempts = [desired]
    elif setting == "audiooutput.guisoundmode":
        m = {"never":0, "onlywhenvideo":1, "only when video playing":1, "always":2}
        attempts = [m.get(str(desired).lower(), desired)]
    elif setting == "subtitles.style":
        m = {"normal":0,"bold":1,"italic":2,"bold italic":3,"bolditalic":3}
        attempts = [m.get(str(desired).lower(), desired)]
    elif setting in ("locale.audiolanguage","locale.subtitlelanguage"):
        if isinstance(desired, str):
            attempts = [desired, desired.title(), desired.lower(), "en", "English"]
        else:
            attempts = [desired]
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

    # Retry loop
    for i in range(max_tries):
        for a in attempts:
            v = cast_like(a, cur)
            if _attempt_set(setting, v):
                return v
        xbmc.sleep(sleep_ms)
        cur = get_current(setting)  # refresh type reference
    return None

# Your requested settings (labels help if IDs change).
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
    (["addons.updatefromrepo","addons.updatemode"], "update official add-ons from", "any"),

    # Media » General
    (["filelists.showparentdiritems"], "show parent folder items", False),

    # Interface » Regional
    (["locale.region","locale.country"], "region default format", "Central Europe"),
]

def main():
    # If we already ran, bail.
    if xbmcvfs.exists(RUN_FLAG):
        return

    xbmcvfs.mkdirs(DATA_DIR)
    wait_home(timeout=120, settle_ms=1500)
    by_id, by_lbl = get_maps()

    applied, skipped = {}, []
    applied_any = False

    for cands, label, value in WANTS:
        sel = next((cid for cid in cands if cid in by_id), None)
        if not sel:
            sel = by_lbl.get(label.lower())
        if not sel:
            skipped.append({"label":label, "reason":"setting not found", "candidates":cands})
            continue

        v = set_value_retry(sel, value, max_tries=6, sleep_ms=300)
        if v is None:
            skipped.append({"id":sel, "label":label, "wanted":value, "reason":"set failed"})
        else:
            applied[sel] = {"label":label, "value":v}
            applied_any = True

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump({"applied":applied, "skipped":skipped}, f, ensure_ascii=False, indent=2)

    # Mark done BEFORE any restart to prevent loops
    with open(RUN_FLAG, "w") as f:
        f.write("ok")

    if applied_any:
        xbmc.executebuiltin('Notification(Mosestyle,Settings applied — restarting once to save,4000)')
        # Disable self now; Kodi will come back clean with guisettings.xml on disk.
        rpc("Addons.SetAddonEnabled", {"addonid":ADDON_ID, "enabled": False})
        xbmc.sleep(1200)
        xbmc.executebuiltin('RestartApp')
    else:
        xbmc.executebuiltin('Notification(Mosestyle,No settings changed,4000)')
        rpc("Addons.SetAddonEnabled", {"addonid":ADDON_ID, "enabled": False})

if __name__ == "__main__":
    main()
