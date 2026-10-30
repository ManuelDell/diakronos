"""UX-A2b — Anfragen fuer die Abnahme anlegen (nur im Wegwerf-Stack).

Legt ueber die ECHTEN HTTP-Endpunkte einen Anmeldelink an, schickt drei
oeffentliche Anmeldungen, nimmt eine auf und lehnt eine ab. Damit sind alle
vier Chips belegt und unterscheidbar:

    Alle 3 · Offen 1 · Aufgenommen 1 · Abgelehnt 1

(Und wenn die Demo-Daten eine Warteliste-Anfrage enthalten, ist „Alle“
groesser als die Summe der drei Einzelchips — genau der Fall, der ohne den
„Alle“-Chip unsichtbar waere. Das Skript prueft das und sagt es.)

Kein Modell-Zugriff, keine Direktdatenbank: alles ueber /api/method wie die
Oberflaeche. Laeuft in einem Container IM Stack-Netz:

    docker run --rm --network t_c37ea235_default \
        -v "$PWD":/w:ro -e BASE=http://app:8000 \
        --entrypoint python diakronos-t_c37ea235:test /w/tools/demo/uxa2b-anfragen.py

Das Skript ist NICHT fuer den Betrieb gedacht: es schreibt Anmeldungen und
verweigert eine Basis, die nicht auf einem Wegwerf-Port laeuft (ENV
ABNAHME=1 muss gesetzt sein).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "musterhausen-demo")
ABNAHME = os.environ.get("ABNAHME", "")

if ABNAHME != "1":
    print("ABNAHME=1 nicht gesetzt — dieses Skript legt echte Anfragen an und "
          "laeuft nur im Wegwerf-Stack.", file=sys.stderr)
    raise SystemExit(2)

jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
csrf = {"token": ""}


def ruf(pfad, daten=None):
    """POST auf /api/method/<pfad>; gibt den GANZEN Antwort-Koerper zurueck.

    Schreibende Aufrufe brauchen den CSRF-Token aus dem Login (die SPA nimmt
    ihn aus dem Boot-Objekt, hier kommt er aus der Login-Antwort).
    """
    körper = json.dumps(daten or {}).encode()
    kopf = {"Content-Type": "application/json", "Accept": "application/json"}
    if csrf["token"]:
        kopf["X-Frappe-CSRF-Token"] = csrf["token"]
    anfrage = urllib.request.Request(
        f"{BASE}/api/method/{pfad}", data=körper, headers=kopf, method="POST")
    try:
        with opener.open(anfrage, timeout=30) as antwort:
            return json.loads(antwort.read().decode() or "{}")
    except urllib.error.HTTPError as fehler:
        text = fehler.read().decode(errors="replace")
        raise SystemExit(f"{pfad} -> HTTP {fehler.code}: {text[:400]}")


def nachricht(antwort):
    """`message` aus der Antwort (Frappe-Form) — sonst die Antwort selbst."""
    if isinstance(antwort, dict) and "message" in antwort:
        return antwort["message"]
    return antwort


def main() -> int:
    anmeldung = ruf("login", {"usr": ADMIN, "pwd": ADMIN_PASS})
    csrf["token"] = (anmeldung or {}).get("csrf_token") or ""
    if not csrf["token"]:
        raise SystemExit(f"Login ohne csrf_token: {anmeldung}")
    print("angemeldet als", ADMIN)

    link = nachricht(ruf("diakronos.diakonos.api.registrierungslink_api.create_link",
                         {"bezeichnung": "Abnahme UX-A2b", "typ": "Mitglied-Registrierung",
                          "ohne_ablauf": True, "unbegrenzt": True}))["link"]
    token = link["slug"]
    print("Link angelegt:", token)

    # Drei oeffentliche Anmeldungen ueber denselben Endpunkt wie das Formular.
    personen = [
        ("Anna", "Abnahme"), ("Bernd", "Abnahme"), ("Clara", "Abnahme"),
    ]
    namen = []
    for vorname, nachname in personen:
        ergebnis = nachricht(ruf("diakronos.diakonos.api.registrierung.submit_registrierung",
                                 {"token": token, "vorname": vorname, "nachname": nachname,
                                  "email": f"{vorname.lower()}@example.org", "dsgvo": 1}))
        name = (ergebnis or {}).get("anmeldung") or (ergebnis or {}).get("name")
        namen.append(name)
        print("Anmeldung", vorname, "->", name)

    hub = nachricht(ruf("diakronos.diakonos.api.admin_hub.get_anmeldungen_hub"))
    offene = [a for a in hub["anmeldungen"]
              if a["status"] in ("Anmeldeanfrage", "Ausstehend")]
    print("offene Anmeldungen:", [(a["name"], a["status"]) for a in offene][:6])

    ziele = [a for a in offene if a["name"] in namen]
    if len(ziele) < 2:
        raise SystemExit(f"zu wenige eigene Anmeldungen offen: {len(ziele)}")

    auf = ziele[0]
    ab = ziele[1]
    nachricht(ruf("diakronos.diakonos.api.admin_hub.genehmige_anmeldung",
                  {"anmeldung_id": auf["name"], "dublette_bestaetigt": 1}))
    nachricht(ruf("diakronos.diakonos.api.admin_hub.lehne_anmeldung_ab",
                  {"anmeldung_id": ab["name"], "grund": "Abnahme UX-A2b"}))
    print("aufgenommen:", auf["name"], "| abgelehnt:", ab["name"])

    # Kontrolle ueber dieselbe Quelle, die die Seite liest.
    hub = nachricht(ruf("diakronos.diakonos.api.admin_hub.get_anmeldungen_hub"))
    nach = {}
    for a in hub["anmeldungen"]:
        nach[a["status"]] = nach.get(a["status"], 0) + 1
    print("Bestand nach Status:", json.dumps(nach, ensure_ascii=False))
    offen = nach.get("Anmeldeanfrage", 0) + nach.get("Ausstehend", 0)
    print(json.dumps({
        "alle": len(hub["anmeldungen"]),
        "offen": offen,
        "aufgenommen": nach.get("Bestätigt", 0),
        "abgelehnt": nach.get("Abgelehnt", 0),
        "warteliste": nach.get("Warteliste", 0),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
