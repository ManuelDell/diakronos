# diakronos/install.py
import os
import requests
from frappe import get_app_path, log_error

def symlink_create_install():
    """Automatisiert Symlinks und holt externe Bibliotheken bei App-Installation."""

    # 1. FullCalendar v6 global bundle (nur JS – CSS wird automatisch injiziert)
    fc_version = "6.1.15"  # oder höher, z.B. "6.1.20" wenn du upgraden willst
    base_url = f"https://cdn.jsdelivr.net/npm/fullcalendar@{fc_version}/"
    js_file = {
        "url": f"{base_url}index.global.min.js",
        "target_path": get_app_path("diakronos", "public", "js", "lib", "fullcalendar", "index.global.min.js")
    }
    target = js_file["target_path"]
    url = js_file["url"]
    os.makedirs(os.path.dirname(target), exist_ok=True)

    if not os.path.exists(target):
        print(f"Downloading FullCalendar v{fc_version} global bundle: {os.path.basename(target)}")
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            with open(target, "wb") as f:
                f.write(response.content)
            print(f"✅ Downloaded → {target}")
        except Exception as e:
            log_error("Download fehlgeschlagen", f"URL: {url}\nError: {str(e)}")
            print(f"⚠️ Manuell herunterladen: {url} → {target}")
    else:
        print(f"✅ FullCalendar asset schon vorhanden: {os.path.basename(target)}")

    # 3. Symlink für moment.min.js von Frappe (aus node_modules)
    frappe_node_modules = os.path.join(get_app_path('frappe'), 'public', 'node_modules')
    moment_target_dir = get_app_path("diakronos", "public", "js", "lib", "moment")
    os.makedirs(moment_target_dir, exist_ok=True)

    moment_source = os.path.join(frappe_node_modules, 'moment', 'min', 'moment.min.js')
    moment_target = os.path.join(moment_target_dir, "moment.min.js")

    if not os.path.exists(moment_target):
        if os.path.exists(moment_source):
            try:
                os.symlink(moment_source, moment_target)
                print(f"✅ Symlink moment.min.js erstellt: {moment_target} → {moment_source}")
            except Exception as e:
                log_error("Symlink moment.min.js fehlgeschlagen", str(e))
        else:
            print(f"⚠️ moment.min.js in Frappe nicht gefunden: {moment_source}")

    # 4. Symlink für moment-timezone-with-data-10-year-range.min.js (aus node_modules)
    mtz_source = os.path.join(frappe_node_modules, 'moment-timezone', 'builds', 'moment-timezone-with-data-10-year-range.min.js')
    mtz_target = os.path.join(moment_target_dir, "moment-timezone-with-data-10-year-range.min.js")

    if not os.path.exists(mtz_target):
        if os.path.exists(mtz_source):
            try:
                os.symlink(mtz_source, mtz_target)
                print(f"✅ Symlink moment-timezone erstellt: {mtz_target} → {mtz_source}")
            except Exception as e:
                log_error("Symlink moment-timezone fehlgeschlagen", str(e))
        else:
            print(f"⚠️ moment-timezone-with-data-10-year-range.min.js in Frappe nicht gefunden: {mtz_source}")

    # Dein alter Download-Code für moment ist jetzt überflüssig – du kannst ihn entfernen
    # (Kommentiere ihn aus oder lösche, wenn du sicher bist)
    # moment_version = "2.30.1"
    # moment_url = f"https://cdn.jsdelivr.net/npm/moment@{moment_version}/moment.min.js"
    # ...

    print("✅ Symlink-Installation abgeschlossen")

    # 5. nginx für CalDAV-Zugriff konfigurieren
    from diakronos.setup.nginx import setup_caldav_nginx
    setup_caldav_nginx()