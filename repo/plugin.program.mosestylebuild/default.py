import os, io, zipfile
import xbmc, xbmcgui, xbmcaddon, xbmcvfs
from urllib.request import urlopen, Request

ADDON  = xbmcaddon.Addon()
DIALOG = xbmcgui.Dialog()

BUILD_URL = ADDON.getSettingString("build_url").strip()
HOME = xbmcvfs.translatePath("special://home/")

def download_bytes(url):
    req = Request(url, headers={"User-Agent": "Kodi"})
    with urlopen(req) as r:
        return r.read()

def ensure_dir(p):
    if not xbmcvfs.exists(p):
        xbmcvfs.mkdirs(p)

def extract_zip_to_home(zbytes):
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        for zi in z.infolist():
            name = zi.filename.replace("\\", "/")
            if name.startswith("./"):
                name = name[2:]
            if not (name.startswith("addons/") or name.startswith("userdata/")):
                continue
            target = os.path.join(HOME, name).replace("\\", "/")
            if zi.is_dir():
                ensure_dir(target)
            else:
                ensure_dir(os.path.dirname(target))
                with z.open(zi) as src, xbmcvfs.File(target, "w") as dst:
                    dst.write(src.read())
    return True

def main():
    if not BUILD_URL:
        DIALOG.ok("Mosestyle Installer", "Build URL is empty in add-on settings.")
        return
    if not DIALOG.yesno("Mosestyle Installer", "Install Mosestyle build now?",
                        f"[CR]Source: [B]{BUILD_URL}[/B]"):
        return
    try:
        DIALOG.notification("Mosestyle", "Downloading build…", xbmcgui.NOTIFICATION_INFO, 2000)
        data = download_bytes(BUILD_URL)
        DIALOG.notification("Mosestyle", "Extracting…", xbmcgui.NOTIFICATION_INFO, 2000)
        extract_zip_to_home(data)
        DIALOG.ok("Mosestyle", "Build installed successfully.[CR]Restart Kodi to finish setup.")
    except Exception as e:
        DIALOG.ok("Mosestyle Error", f"Install failed: {e}")

if __name__ == "__main__":
    main()
