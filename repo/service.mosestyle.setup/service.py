import json, os, xbmc, xbmcaddon, xbmcgui

ADDON   = xbmcaddon.Addon()
PROFILE = xbmc.translatePath(ADDON.getAddonInfo('profile'))
FLAG    = os.path.join(PROFILE, "done.flag")

def rpc(method, params=None):
    req = {"jsonrpc":"2.0","id":1,"method":method}
    if params is not None:
        req["params"] = params
    resp = xbmc.executeJSONRPC(json.dumps(req))
    try:
        return json.loads(resp)
    except Exception:
        return {}

def set_setting(key, value):
    return rpc("Settings.SetSettingValue", {"setting": key, "value": value}).get("result") == "OK"

def notify(msg):
    xbmcgui.Dialog().notification("Mosestyle", msg, time=2500)

if not os.path.exists(PROFILE):
    os.makedirs(PROFILE, exist_ok=True)

if not os.path.exists(FLAG):
    # --- Player ▸ Videos ---
    set_setting("videoskipsteps", [-10, 10])
    set_setting("videoskipdelay", 750)
    set_setting("videoscreen.adjustrefreshrate", 2)   # Always
    set_setting("videoplayer.syncplayback", True)
    set_setting("videoplayer.minimizeblackbars", 20)
    set_setting("videoscreen.stretch43", 2)           # Stretch 16:9

    # --- Player ▸ Language ---
    set_setting("locale.audiolanguage", "English")
    set_setting("locale.subtitlelanguage", "English")

    # --- Player ▸ Subtitles ---
    set_setting("subtitles.align", 0)                 # Bottom
    set_setting("subtitles.style", 2)                 # Bold
    set_setting("subtitles.languages", ["English", "Swedish"])
    set_setting("subtitles.pauseonsearch", True)
    set_setting("subtitles.autodownloadfirst", True)
    rpc("Addons.SetAddonEnabled", {"addonid": "service.subtitles.a4kSubtitles", "enabled": True})
    set_setting("subtitles.movies", "service.subtitles.a4kSubtitles")
    set_setting("subtitles.tvshows", "service.subtitles.a4kSubtitles")

    # --- System ▸ Audio ---
    set_setting("audiooutput.guisoundmode", 0)        # Never

    # --- System ▸ Add-ons ---
    set_setting("addons.unknownsources", True)
    set_setting("addons.officialrepopolicy", 1)       # Any repositories

    # --- Media ▸ General ---
    set_setting("filelists.showparentdiritems", False)

    # --- Interface ▸ Regional ---
    set_setting("locale.region", "Central Europe")

    # --- Extra defaults (best-effort) ---
    set_setting("videoplayer.defaultvideosettings.viewmode", 4)
    set_setting("videoplayer.defaultvideosettings.brightness", 51.0)

    open(FLAG, "w").close()
    notify("Applied Mosestyle first-run settings")
    rpc("Addons.SetAddonEnabled", {"addonid": ADDON.getAddonInfo('id'), "enabled": False})
