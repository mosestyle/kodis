# Mosestyle Build Installer — safer skin-switch + restart
import xbmc, xbmcgui, xbmcaddon, xbmcvfs
import os, zipfile, urllib.request, shutil, json, re, time
from xml.etree import ElementTree as ET

ADDON = xbmcaddon.Addon()
HOME  = xbmcvfs.translatePath('special://home/')
PKGS  = xbmcvfs.translatePath('special://home/addons/packages/')
TMP_ZIP = os.path.join(PKGS, 'mosestyle_build.zip')

SERVICE_ID = "service.mosestyle.config"

def log(msg): xbmc.log(f"[MosestyleBuild] {msg}", xbmc.LOGINFO)

def rpc(method, params=None):
    payload = {"jsonrpc":"2.0","id":1,"method":method}
    if params is not None: payload["params"] = params
    try: return json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    except Exception as e:
        log(f"JSON parse error: {e}")
        return {}

def download(url, dst):
    xbmcvfs.mkdirs(PKGS)
    with urllib.request.urlopen(url) as r, open(dst, 'wb') as f:
        f.write(r.read())

def safe_wipe():
    keep = {'addons','userdata','addons/packages'}
    for name in os.listdir(HOME):
        if name in keep: continue
        p = os.path.join(HOME, name)
        try:
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
        except Exception as e: log(f"wipe top error {name}: {e}")
    u = os.path.join(HOME, 'userdata')
    if os.path.isdir(u):
        for name in os.listdir(u):
            if name.lower() in ('database','thumbnails'): continue
            p = os.path.join(u, name)
            try:
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
            except Exception as e: log(f"wipe userdata error {name}: {e}")

def extract_to_home(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(HOME)

def parse_zip_for_addons_and_skins(zip_path):
    addon_ids, skin_ids = [], []
    with zipfile.ZipFile(zip_path, 'r') as z:
        for n in z.namelist():
            if not n.lower().endswith('addon.xml'): continue
            if not re.search(r'(^|/)addons/[^/]+/addon\.xml$', n, re.IGNORECASE): continue
            try:
                root = ET.fromstring(z.read(n))
                aid = root.attrib.get('id')
                if aid and aid not in addon_ids:
                    addon_ids.append(aid)
                for ext in root.findall('extension'):
                    if ext.attrib.get('point') in ('xbmc.gui.skin','kodi.gui.skin'):
                        if aid not in skin_ids:
                            skin_ids.append(aid)
            except Exception as e:
                log(f"parse failed for {n}: {e}")
    return addon_ids, skin_ids

def enable_unknown_sources():
    if ADDON.getSettingBool('enable_unknown_sources'):
        rpc("Settings.SetSettingValue", {"setting":"addons.unknownsources","value":True})

def update_local_addons_and_wait(target_ids, timeout=120):
    if not target_ids: return
    xbmc.executebuiltin('UpdateLocalAddons')
    deadline = time.time() + timeout
    pending = set(target_ids)
    mon = xbmc.Monitor()
    while pending and time.time() < deadline and not mon.abortRequested():
        for aid in list(pending):
            details = rpc("Addons.GetAddonDetails", {"addonid": aid, "properties":["enabled","name","version"]})
            if details.get("result",{}).get("addon"):
                pending.discard(aid)
        xbmc.sleep(500)
    if pending:
        log(f"Timeout waiting for addons to register: {sorted(pending)}")

def enable_addons(addon_ids):
    for aid in addon_ids:
        rpc("Addons.SetAddonEnabled", {"addonid": aid, "enabled": True})

def ensure_service_enabled():
    rpc("Addons.SetAddonEnabled", {"addonid": SERVICE_ID, "enabled": True})

def set_skin(skin_id):
    if not skin_id: return
    rpc("Addons.SetAddonEnabled", {"addonid": skin_id, "enabled": True})
    rpc("Settings.SetSettingValue", {"setting":"lookandfeel.skin","value":skin_id})

def skin_prompt_active():
    return xbmc.getCondVisibility('Window.IsActive(yesnodialog)')

def wait_for_skin_prompt(timeout=120):
    mon = xbmc.Monitor()
    end = time.time() + timeout
    saw_prompt = False
    while time.time() < end and not mon.abortRequested():
        if skin_prompt_active():
            saw_prompt = True
        else:
            if saw_prompt:
                return True  # was visible, now gone
        xbmc.sleep(250)
    return not saw_prompt  # True if never saw it

def maybe_delete_guisettings():
    if not ADDON.getSettingBool('delete_guisettings'): return
    for path in [
        xbmcvfs.translatePath('special://profile/guisettings.xml'),
        os.path.join(HOME, 'userdata', 'guisettings.xml')
    ]:
        try:
            if xbmcvfs.exists(path): xbmcvfs.delete(path)
        except Exception as e:
            log(f"delete guisettings failed: {e}")

def main():
    xbmcgui.Dialog().notification('Mosestyle Build', 'Starting installer…', xbmcgui.NOTIFICATION_INFO, 2000)

    url   = ADDON.getSettingString('build_url').strip()
    fresh = ADDON.getSettingBool('fresh')
    if not url:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), 'No Build ZIP URL set.'); return
    if not xbmcgui.Dialog().yesno('Mosestyle Build', f'Install build from:\n[COLOR cyan]{url}[/COLOR]\n\nContinue?'):
        return

    try:
        enable_unknown_sources()
        download(url, TMP_ZIP)

        addon_ids, skin_ids = parse_zip_for_addons_and_skins(TMP_ZIP)

        if fresh and xbmcgui.Dialog().yesno('Fresh Install?', 'This wipes most of your current Kodi data first (keeps Thumbnails/Database).\n\nProceed?'):
            safe_wipe()

        extract_to_home(TMP_ZIP)

        update_local_addons_and_wait(addon_ids)
        enable_addons(addon_ids)
        ensure_service_enabled()
        maybe_delete_guisettings()

        target_skin = ""
        if ADDON.getSettingBool('auto_set_skin'):
            target_skin = ADDON.getSettingString('skin_id_override').strip() or (skin_ids[0] if skin_ids else "")
            if target_skin:
                set_skin(target_skin)
                # Wait for the "Keep skin?" prompt to be handled before any restart
                wait_for_skin_prompt(timeout=120)

        xbmcgui.Dialog().ok('Mosestyle Build',
                            "Build installed.\nOn next start, Mosestyle's First-Run Config will apply GUI settings.")
        if ADDON.getSettingBool('auto_restart'):
            xbmc.executebuiltin('RestartApp')

    except Exception as e:
        xbmcgui.Dialog().ok('Mosestyle Build', f'Install failed:\n{e}')

if __name__ == "__main__":
    main()
