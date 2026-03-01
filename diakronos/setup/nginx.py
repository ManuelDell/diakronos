# diakronos/setup/nginx.py
"""
Fügt CalDAV-Location-Blöcke in die nginx-Konfiguration ein.

Wird automatisch bei 'bench install-app diakronos' aufgerufen.

Nach 'bench setup nginx' (überschreibt die Config) manuell wiederherstellen:
    bench execute diakronos.setup.nginx.setup_caldav_nginx
"""
import subprocess
import frappe


NGINX_CONF = "/etc/nginx/conf.d/frappe-bench.conf"
MARKER    = "# CalDAV – direkt zu Frappe, OHNE Trailing-Slash-Rewrite"

# Doppelte geschweifte Klammern {{ }} sind Python-Escapes für { } im f-String
_BLOCK = """\

\t{marker}
\t# Wiederherstellen nach 'bench setup nginx':
\t#   bench execute diakronos.setup.nginx.setup_caldav_nginx
\tlocation /dav {{
\t\tproxy_http_version 1.1;
\t\tproxy_set_header X-Forwarded-For $remote_addr;
\t\tproxy_set_header X-Forwarded-Proto $scheme;
\t\tproxy_set_header X-Frappe-Site-Name {site};
\t\tproxy_set_header Host $host;
\t\tproxy_set_header X-Use-X-Accel-Redirect True;
\t\tproxy_read_timeout 120;
\t\tproxy_redirect off;
\t\tproxy_pass http://frappe-bench-frappe;
\t}}

\tlocation = /.well-known/caldav {{
\t\tproxy_http_version 1.1;
\t\tproxy_set_header X-Forwarded-For $remote_addr;
\t\tproxy_set_header X-Forwarded-Proto $scheme;
\t\tproxy_set_header X-Frappe-Site-Name {site};
\t\tproxy_set_header Host $host;
\t\tproxy_set_header X-Use-X-Accel-Redirect True;
\t\tproxy_read_timeout 120;
\t\tproxy_redirect off;
\t\tproxy_pass http://frappe-bench-frappe;
\t}}
"""


def setup_caldav_nginx():
    """Fügt CalDAV-location-Blöcke in die nginx-Konfiguration ein (idempotent)."""
    site = frappe.local.site

    # ── Config lesen ──────────────────────────────────────────────────────────
    try:
        with open(NGINX_CONF, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"⚠️  nginx-Config nicht gefunden: {NGINX_CONF}")
        print("    Erst 'bench setup nginx' ausführen, dann erneut aufrufen.")
        return
    except PermissionError:
        print(f"⚠️  Keine Leseberechtigung: {NGINX_CONF}")
        return

    # ── Bereits vorhanden? ────────────────────────────────────────────────────
    if MARKER in content:
        print("✅  nginx CalDAV-Blöcke bereits vorhanden – nichts zu tun.")
        return

    # ── Einfügeposition bestimmen: vor 'location / {' im richtigen server-Block
    # Suche erste Erwähnung des Site-Namens im Proxy-Header → danach 'location / {'
    site_ref = f"X-Frappe-Site-Name {site};"
    ref_pos  = content.find(site_ref)
    if ref_pos == -1:
        print(f"⚠️  Kein server-Block für '{site}' in {NGINX_CONF} gefunden.")
        return

    insert_pos = content.find("\n\tlocation / {", ref_pos)
    if insert_pos == -1:
        print(f"⚠️  'location /' nicht in {NGINX_CONF} gefunden.")
        return

    # ── Einfügen ──────────────────────────────────────────────────────────────
    block = _BLOCK.format(marker=MARKER, site=site)
    new_content = content[:insert_pos] + block + content[insert_pos:]

    try:
        with open(NGINX_CONF, "w") as f:
            f.write(new_content)
    except PermissionError:
        print(f"⚠️  Keine Schreibberechtigung für {NGINX_CONF}.")
        print("    Als root ausführen:")
        print("      sudo -u root bench execute diakronos.setup.nginx.setup_caldav_nginx")
        return

    # ── nginx testen und neu laden ────────────────────────────────────────────
    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        print(f"⚠️  nginx-Konfigurationsfehler – Änderung rückgängig gemacht:\n{test.stderr}")
        with open(NGINX_CONF, "w") as f:
            f.write(content)
        return

    subprocess.run(["nginx", "-s", "reload"], capture_output=True)
    print(f"✅  CalDAV nginx-Blöcke für '{site}' eingefügt und nginx neu geladen.")
