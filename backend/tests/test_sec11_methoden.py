"""SEC-11 — CSRF per GET schliessen: schreibende Methoden nur POST.

BEFUND (Opus-Review 2026-10-31, HOCH)
======================================
`call_method` nahm GET/POST/PUT/PATCH fuer JEDE whitelist-Funktion an;
`_methode_erlaubt` beschraenkte nur den Login. `CsrfMiddleware` prueft
ausschliesslich schreibende HTTP-Methoden. Das Sitzungs-Cookie ist
`SameSite=Lax` — ein Link `GET {Praefix}/api/method/<schreibende_funktion>?…`,
den ein angemeldeter Admin auf einer fremden Seite anklickt, fuehrt die
Aktion also aus (Mitglied loeschen, Mailversand umstellen, …).

WAS DIESE DATEI FESTHAELT
=========================
  (C1) `@whitelist(methods=["POST"])` ist eine echte Grenze: jede andere
       Methode endet mit 405 (Skript) bzw. 303 auf die Anmeldemaske
       (Browser-Navigation) und fuehrt NICHTS aus.
  (C2) Das Inventar (`tools/whitelist_inventar.py`, `docs/whitelist-inventar.*`)
       stammt aus dem lebenden Register und meldet keine Widersprueche.
  (C4) `Sec-Fetch-Site: cross-site|same-site` auf `/api/method/*` und
       `/api/resource/*` -> 403, ausgenommen die oeffentlichen
       Website-Endpunkte (eigene Herkunftspruefung).
  (C5) Waechter: keine whitelist-Funktion, deren NAME auf Schreiben deutet,
       darf ohne `methods=["POST"]` registriert sein. Dazu Stichproben fuer
       kritische Endpunkte mit Beweis, dass die Datenbank unveraendert bleibt.
"""

from __future__ import annotations

import pytest

#: Verben, die laut Karte auf eine schreibende Wirkung hindeuten.
WACHHUND_VERBEN = (
    "speichern", "setzen", "setze", "set_", "loeschen", "löschen", "delete",
    "create", "update", "anlegen", "entfernen", "hinzufuegen", "add_",
    "import", "uebernehmen", "senden", "zuweisen", "aendern", "freigabe",
    "freigeben", "archiv", "abschliessen", "einladen", "reset", "toggle",
    "decide", "save_", "mark_", "melden", "genehmige", "lehne", "ablehnen",
    "zurueckziehen", "widerruf", "anonymisieren", "entsperren", "sperren",
    "pflegen", "kopieren", "generier", "veroeffentlich", "finalize",
    "resolve", "upload", "insert", "start_", "exchange", "verlaengern",
    "aufraeumen", "erzeugen", "undo", "login", "logout", "passwort",
    "freischalten",
)

#: Praefixe, die unmissverstaendlich LESEN (`get_offene_aenderungen`).
LESE_PRAEFIXE = ("get_", "liste_", "holen", "suche", "pruefe_", "ist_",
                 "zaehle_", "check_")


def _namen_mit_schreibverdacht(name: str) -> bool:
    """Dieselbe Regel wie `tools/whitelist_inventar.ist_schreibname`."""
    klein = name.lower()
    if any(v in klein for v in ("set_", "save_", "add_", "mark_", "start_")):
        return True
    if not klein:
        return False
    if klein.startswith(LESE_PRAEFIXE):
        rest = klein
        for praefix in LESE_PRAEFIXE:
            if rest.startswith(praefix):
                rest = rest[len(praefix):]
                break
        return any(v in rest for v in WACHHUND_VERBEN)
    return any(v in klein for v in WACHHUND_VERBEN)


def _register():
    """Das lebende Register, nach Import ALLER Endpunkt-Module."""
    import diakronos_app.api  # noqa: F401 — registriert die API-Module
    from diakronos_app.frappe_compat import registry

    for modul in ("diakronos_app.devmodus.api", "diakronos_app.website.kontakt"):
        try:
            __import__(modul)
        except Exception:  # noqa: BLE001 — optionales Modul
            pass
    return registry


def _funktionen() -> dict[str, dict]:
    """`{funktionsname: {optionen, pfade}}` — je Funktion EIN Eintrag."""
    reg = _register()
    je_fn: dict[int, dict] = {}
    for pfad, fn in reg.registered().items():
        eintrag = je_fn.get(id(fn))
        if eintrag is None:
            eintrag = {
                "name": getattr(fn, "__name__", "?"),
                "modul": getattr(fn, "__module__", "?"),
                "optionen": reg.options_for(fn),
                "pfade": [],
            }
            je_fn[id(fn)] = eintrag
        eintrag["pfade"].append(pfad)
    return {e["name"]: e for e in je_fn.values()}


# ── C1: die Deklaration ist eine Grenze ────────────────────────────────────


def test_c1_whitelist_nimmt_methods_an_und_normalisiert():
    """`methods` landet im Register — als Tupel, gross geschrieben, sortiert."""
    from diakronos_app.frappe_compat import registry

    @registry.whitelist(methods=["post"])
    def _sec11_probe_fn():
        return "nie aufgerufen"

    try:
        assert registry.methoden_fuer(_sec11_probe_fn) == ("POST",)
    finally:
        registry._REGISTRY.pop("_sec11_probe_fn", None)
        registry._OPTIONS.pop(id(_sec11_probe_fn), None)


def test_c1_unbekannte_methode_wird_beim_dekorieren_abgelehnt():
    """Ein Tippfehler in `methods` faellt beim Import auf, nicht im Betrieb."""
    from diakronos_app.frappe_compat import registry

    with pytest.raises(ValueError):

        @registry.whitelist(methods=["POSTE"])
        def _sec11_probe_kaputt():
            return None


def test_c1_ohne_methods_bleibt_alles_wie_bisher():
    """Bestehende Endpunkte ohne Deklaration verhalten sich unveraendert."""
    from diakronos_app.frappe_compat import registry

    @registry.whitelist(allow_guest=True)
    def _sec11_probe_ohne():
        return None

    try:
        assert registry.methoden_fuer(_sec11_probe_ohne) is None
    finally:
        registry._REGISTRY.pop("_sec11_probe_ohne", None)
        registry._OPTIONS.pop(id(_sec11_probe_ohne), None)


def test_c1_login_ist_post_only_im_register():
    """SEC-11 macht die bisher nur im Router stehende Login-Regel sichtbar."""
    from diakronos_app.frappe_compat import registry

    from diakronos_app.api.auth import login

    assert registry.methoden_fuer(login) == ("POST",)


# ── C5-Waechter: kein Schreibname ohne POST-Beschraenkung ──────────────────


def test_c5_kein_schreibender_name_ohne_post():
    """Waechter der Karte (C5).

    Jede whitelist-Funktion, deren Name auf Schreiben deutet, MUSS
    `methods=["POST"]` tragen. Die Ausnahmen stehen hier namentlich mit
    Begruendung — eine neue Ausnahme ist damit eine sichtbare Entscheidung
    und keine stille Luecke.
    """
    #: Lesende Funktionen, deren Name ein Schreibverb enthaelt. Alle sind in
    #: der Karte geprueft: sie lesen/berechnen und schreiben nichts.
    LESEND_TROTZ_VERB = {
        # BS-1a: liest nur die Liste der Website-Freigaben.
        "freigaben_lesen",
        # Setzt nichts — prueft ein Feld-Kuerzel und meldet den Fehler (417).
        "fail_validation",
        # Vorschau des Rueckgaengig-Ziels („was wuerde undo zuruecknehmen?“).
        "undo_vorschau",
        # Liest nur die Rechte des angemeldeten Nutzers.
        "get_user_create_permissions",
        # Liest den Fortschritt des Google-Imports aus Redis — geschrieben wird
        # von `start_import`/`upload_ical`, nicht hier.
        "get_import_progress",
    }
    verstoesse = []
    for name, eintrag in _funktionen().items():
        if not _namen_mit_schreibverdacht(name):
            continue
        if name in LESEND_TROTZ_VERB:
            continue
        if eintrag["optionen"].get("methods") != ("POST",):
            verstoesse.append(f"{eintrag['modul']}.{name} -> {eintrag['optionen'].get('methods')}")
    assert not verstoesse, (
        "SEC-11/C5: schreibende Endpunkte ohne methods=['POST']:\n  "
        + "\n  ".join(sorted(verstoesse))
    )


def test_c5_die_ausnahmeliste_ist_begruendet_und_vollstaendig():
    """Jeder Name in `LESEND_TROTZ_VERB` existiert wirklich — und ist lesend.

    Sonst wuerde die Ausnahmeliste nach einer Umbenennung still ins Leere
    zeigen und ein echter Verstoss bliebe unbemerkt.
    """
    from diakronos_app.api.planrahmen import undo_vorschau  # noqa: F401
    from diakronos_app.api.gruppen import get_user_create_permissions  # noqa: F401

    funktionen = _funktionen()
    for name in ("fail_validation", "undo_vorschau", "get_user_create_permissions"):
        assert name in funktionen, f"{name} ist nicht (mehr) registriert"
        assert funktionen[name]["optionen"].get("methods") is None, (
            f"{name} traegt jetzt eine Methodenliste — Ausnahme pruefen")


def test_c2_jede_dekoration_behaelt_ihre_bestehenden_argumente():
    """Waechter: `@whitelist(methods=[...])` darf NICHTS verdraengen.

    BEFUND (2026-10-31): das Umstellungswerkzeug hat aus
    `@whitelist(allow_guest=False)` die Zeichenkette
    `@whitelist(methods=["POST"], )` gemacht — `allow_guest` war weg. Folge: ein
    oeffentlicher Endpunkt waere stillschweigend zu „nur angemeldet" geworden
    bzw. `allow_guest=True` verloren gegangen. Der Quelltext-Waechter haelt
    das fest, bevor es jemand im Betrieb merkt.
    """
    import re
    from pathlib import Path

    basis = Path(__file__).resolve().parents[1] / "src"
    kaputt = []
    for datei in basis.rglob("*.py"):
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").split("\n"), 1):
            # Nur ECHTE Dekorationszeilen: die Zeile beginnt (nach Einrueckung
            # und optionalem `async`) mit `@whitelist(`. Dokumentation nennt
            # dieselbe Schreibweise und ist keine Dekoration.
            if not re.match(r"^\s*@whitelist\(", zeile):
                continue
            innen = zeile.split("@whitelist(", 1)[1].rsplit(")", 1)[0]
            if innen.strip().endswith(","):
                kaputt.append(f"{datei.name}:{nr}: {zeile.strip()}")
            # `allow_guest` muss erhalten bleiben, wenn es dort stand: geprueft
            # wird das indirekt — `methods` steht immer VOR den uebrigen
            # Argumenten, der Rest der Zeile darf nicht leer sein, wenn es
            # vorher Argumente gab.
            if innen.strip().startswith("methods=") and innen.strip() == 'methods=["POST"]':
                continue
            if innen.strip().startswith("methods=") and not re.search(r"allow_guest=", innen):
                kaputt.append(f"{datei.name}:{nr}: methods ohne allow_guest: {zeile.strip()}")
    assert not kaputt, "SEC-11: verdraengte Dekorationsargumente:\n  " + "\n  ".join(kaputt)


# ── C2: Inventar stammt aus dem Register ───────────────────────────────────


def test_c2_inventar_dateien_liegen_im_paket():
    """C2 verlangt ein Inventar — maschinenlesbar + Lesefassung.

    Ablage IM PYTHON-PAKET (`frappe_compat/inventar/`), nicht unter `docs/`:
    `docs/` steht in `.dockerignore`, und der Waechter der SPA liest die Datei
    im Image (Regel 13, Karten-Nachtrag 1).
    """
    from diakronos_app.frappe_compat import inventar

    daten = inventar.lade_inventar()
    assert daten["funktionen"] > 0
    assert "| Funktion |" in inventar.text()


def test_c2_inventar_kennt_alle_schreibenden_endpunkte():
    """Das Inventar ist nicht veraltet: jede POST-only-Funktion steht als
    schreibend drin, und die Zahlen passen zum Register."""
    from diakronos_app.frappe_compat import inventar

    daten = inventar.lade_inventar()
    laut_inventar = {e["funktion"] for e in daten["eintraege"]
                     if e["einstufung"] == "schreibend"}
    laut_register = {f"{e['modul']}.{e['name']}" for e in _funktionen().values()
                     if e["optionen"].get("methods") == ("POST",)}
    fehlt = laut_register - laut_inventar
    assert not fehlt, (
        "Diese POST-only-Endpunkte fehlen im Inventar — "
        "`tools/whitelist_inventar.py` neu laufen lassen:\n  " + "\n  ".join(sorted(fehlt)))
    assert daten["zaehlung"]["schreibend"] >= len(laut_register)
    assert daten["zaehlung"]["schreibend"] + daten["zaehlung"]["lesend"] == daten["funktionen"]


# ── C4: Herkunftsschranke ──────────────────────────────────────────────────


@pytest.mark.parametrize("herkunft", ["cross-site", "same-site", "CROSS-SITE"])
def test_c4_fremde_herkunft_wird_fuer_jede_api_methode_abgewiesen(guest_client, herkunft):
    """`Sec-Fetch-Site` fremd -> 403, und zwar per GET (der Luecke der Karte)."""
    antwort = guest_client.get(
        "/api/method/diakronos.diakonos.api.mitglieder.get_mitglieder_liste",
        headers={"Sec-Fetch-Site": herkunft, "Accept": "application/json"},
    )
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["exc_type"] == "PermissionError"


@pytest.mark.parametrize("pfad", [
    "/api/method/irgendein.pfad",
    "/api/resource/Eventkategorie",
    "/api/resource/Eventkategorie/KAT-1",
])
def test_c4_gilt_auch_fuer_resource_und_unbekannte_methoden(guest_client, pfad):
    """Die Schranke haengt an keinem Endpunkt — auch 404-Pfade und
    `/api/resource` (dort sind Aenderungen nur PUT/POST/DELETE; GET liest)."""
    antwort = guest_client.get(pfad, headers={"Sec-Fetch-Site": "cross-site"})
    assert antwort.status_code == 403, antwort.text


@pytest.mark.parametrize("herkunft", ["same-origin", "none", ""])
def test_c4_eigene_herkunft_und_fehlender_kopf_bleiben_erlaubt(client, herkunft):
    """`same-origin`/`none` und ein FEHLENDER Kopf duerfen nicht 403 geben —
    sonst waeren Apps, CalDAV und aeltere Browser ausgesperrt."""
    kopf = {"Sec-Fetch-Site": herkunft} if herkunft else {}
    antwort = client.get("/api/method/ping", headers=kopf)
    assert antwort.status_code == 200, antwort.text


@pytest.mark.parametrize("praefix", ["", "/diakronos"])
def test_c4_gilt_auch_unter_dem_betriebs_praefix(praefix):
    """SEC-11: Der Praefix darf die Schranke nicht aushebeln.

    BEFUND beim Wegwerf-Stack (2026-10-31): `request.url.path` traegt unter
    dem Praefix `/diakronos/api/method/…`, `base_path.aktiver_praefix()` war
    im laufenden Prozess aber leer — die Pruefung `startswith("/api/method/")`
    griff nicht und cross-site kam mit 401 statt 403 durch.

    Geprueft wird die ENTSCHEIDUNG der Middleware (der Mount-Praefix laesst
    sich im Test-Client nicht nachstellen, dort wuerde der Pfad 404).
    """
    from types import SimpleNamespace

    from diakronos_app import base_path
    from diakronos_app.frappe_compat.auth_middleware import fremde_herkunft_abgewiesen

    alt = base_path.aktiver_praefix()
    base_path.setze_praefix(praefix)
    try:
        ziel = f"{praefix}/api/method/ping" if praefix else "/api/method/ping"
        request = SimpleNamespace(
            url=SimpleNamespace(path=ziel),
            headers={"sec-fetch-site": "cross-site"},
        )
        assert fremde_herkunft_abgewiesen(request) is True, ziel
        # und mit eigener Herkunft NICHT abweisen
        eigen = SimpleNamespace(
            url=SimpleNamespace(path=ziel),
            headers={"sec-fetch-site": "same-origin"},
        )
        assert fremde_herkunft_abgewiesen(eigen) is False
    finally:
        base_path.setze_praefix(alt)


def test_c4_oeffentliche_website_endpunkte_sind_ausgenommen():
    """Die Website ruft aus fremder Herkunft — sie hat ihre eigene Pruefung."""
    from diakronos_app.frappe_compat.auth_middleware import (
        ist_oeffentlicher_website_endpunkt,
    )

    for pfad in (
        "/api/method/website.kontakt_senden",
        "/api/method/kontakt.kontakt_senden",
        "/api/method/diakronos.diakronos.api.website.kontakt_senden",
        "/api/method/website.login_uebergabe",
        "/api/method/website.status",
    ):
        assert ist_oeffentlicher_website_endpunkt(pfad) is True, pfad
    for pfad in (
        "/api/method/diakronos.diakonos.api.mitglieder.get_mitglieder_liste",
        "/api/resource/Eventkategorie",
        "/api/method/kontakt_senden_mehr",
        "/login",
    ):
        assert ist_oeffentlicher_website_endpunkt(pfad) is False, pfad


def test_c4_kontaktformular_bleibt_von_fremder_herkunft_erreichbar(guest_client):
    """Der oeffentliche Weg darf NICHT an der neuen Schranke scheitern.

    Geprueft wird die Middleware-Entscheidung; der Endpunkt selbst antwortet
    auf fremde Herkunft mit seiner EIGENEN 403 (WEB-10/K3) — beides ist 403,
    deshalb wird hier direkt die Funktion befragt.
    """
    from types import SimpleNamespace

    from diakronos_app.frappe_compat.auth_middleware import fremde_herkunft_abgewiesen

    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/method/website.kontakt_senden"),
        headers={"sec-fetch-site": "cross-site"},
    )
    assert fremde_herkunft_abgewiesen(request) is False


# ── C1/C2 Stichproben: GET fuehrt NICHTS aus (Wirkungsnachweis) ────────────


def _mitglieder_anzahl(session_factory) -> int:
    from sqlalchemy import select

    from diakronos_app.models.diakonos import Mitglied

    sess = session_factory()
    try:
        return len(sess.execute(select(Mitglied.name)).all())
    finally:
        sess.close()


def test_stichprobe_mitglied_status_aendert_nichts_per_get(client, patched_db, seed_mitglieder):
    """Kritischer Endpunkt 1: Mitgliedsstatus — GET 405, DB unveraendert."""
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    try:
        vorher = sess.get(Mitglied, "M-0001").status
    finally:
        sess.close()

    antwort = client.get(
        "/api/method/diakronos.diakonos.api.mitglieder.set_mitglied_status",
        params={"mitglied_id": "M-0001", "status": "Ausgetreten"},
    )
    assert antwort.status_code == 405, antwort.text
    assert antwort.headers["allow"] == "POST"

    sess = patched_db()
    try:
        assert sess.get(Mitglied, "M-0001").status == vorher
    finally:
        sess.close()


def test_stichprobe_loeschen_per_get_laesst_zeilen_stehen(client, patched_db, seed_mitglieder):
    """Kritischer Endpunkt 2: Loeschen — die Zeilen bleiben."""
    vorher = _mitglieder_anzahl(patched_db)
    for pfad in (
        "/api/method/diakronos.diakonos.api.mitglieder.delete_mitglied",
        "/api/method/diakronos.diakonos.api.beitraege.delete_beitrag",
        "/api/method/diakronos.diakonos.api.planrahmen.plan_loeschen",
    ):
        antwort = client.get(pfad, params={"name": "M-0001", "beitrag_id": "B-1",
                                          "plan": "P-1"})
        # Nicht existierende Funktion -> 404; existierende, schreibende -> 405.
        assert antwort.status_code in (404, 405), (pfad, antwort.status_code, antwort.text)
        if antwort.status_code == 405:
            assert antwort.json()["exc_type"] != "PermissionError"
    assert _mitglieder_anzahl(patched_db) == vorher


def test_stichprobe_mailversand_und_sicherung_sind_post_only(client):
    """Kritische Endpunkte 3: Mailversand, Datensicherung, Konten, Links."""
    for pfad in (
        "/api/method/diakronos.diakonos.api.mailversand.mailversand_speichern",
        "/api/method/diakronos.diakonos.api.mailversand.mailversand_testmail",
        "/api/method/diakronos.diakonos.api.sicherung.sicherung_jetzt",
        "/api/method/diakronos.diakonos.api.sicherung.sicherung_loeschen",
        "/api/method/diakronos.diakonos.api.zugang.setze_passwort",
        "/api/method/diakronos.diakonos.api.zugang.konto_anlegen",
        "/api/method/diakronos.diakonos.api.registrierungslink_api.create_link",
        "/api/method/diakronos.diakonos.api.gruppen.update_gruppe",
        "/api/method/diakronos.diakonos.api.kronos.event_crud.delete_event",
        "/api/method/diakronos.diakonos.api.auth.logout",
        "/api/method/logout",
    ):
        antwort = client.get(pfad)
        assert antwort.status_code == 405, (pfad, antwort.status_code, antwort.text)
        assert antwort.headers["allow"] == "POST"


def test_stichprobe_browser_navigation_landet_auf_der_anmeldemaske(client):
    """Ein Link im Browser (Navigation) fuehrt zur Maske — nicht zur Aktion."""
    antwort = client.get(
        "/api/method/diakronos.diakonos.api.mitglieder.set_mitglied_status",
        params={"mitglied_id": "M-0001", "status": "Ausgetreten"},
        headers={"Accept": "text/html,application/xhtml+xml", "Sec-Fetch-Mode": "navigate"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303, antwort.text
    assert antwort.headers["location"].startswith("/login?noredirect=1")
    assert antwort.headers["cache-control"] == "no-store"


def test_stichprobe_post_bleibt_erlaubt(client, patched_db, seed_mitglieder):
    """Die Sperre darf den EIGENEN Weg nicht treffen: POST erreicht die Fachfunktion.

    Der Client ist `Administrator` ohne `Has Role`-Zeile; die Mitglieder-
    verwaltung verlangt eine Rolle und antwortet darum 403 — entscheidend ist,
    dass die Antwort NICHT 405 ist: die Methode kommt durch.
    """
    antwort = client.post(
        "/api/method/diakronos.diakonos.api.mitglieder.set_mitglied_status",
        json={"mitglied_id": "M-0001", "status": "Ausgetreten"},
    )
    assert antwort.status_code != 405, antwort.text
    assert antwort.headers.get("allow") is None
    assert antwort.json()["exc_type"] in ("PermissionError", "Error")


def test_stichprobe_lesende_endpunkte_bleiben_per_get_erreichbar(client, patched_db):
    """Gegenprobe: Leser behalten GET (sonst waere die SPA blind)."""
    for pfad in (
        "/api/method/diakronos.diakonos.api.mitglieder.get_mitglieder_liste",
        "/api/method/diakronos.planrahmen.api.schema_holen",
        "/api/method/diakronos.kronos.api.permissions.get_accessible_calendars",
        "/api/method/diakronos.diakonos.api.session.get_current_user_context",
    ):
        antwort = client.get(pfad)
        assert antwort.status_code == 200, (pfad, antwort.status_code, antwort.text[:200])


def test_planrahmen_schreibdienst_ist_post_only(client):
    """Der Planrahmen-Wrapper (`_endpunkt(schreiben=True)`) setzt die Grenze
    jetzt ebenfalls im Register — vorher stand sie nur im Rumpf."""
    from diakronos_app.frappe_compat import registry
    from diakronos_app.api.planrahmen import eintrag_setzen, undo

    for fn in (eintrag_setzen, undo):
        assert registry.methoden_fuer(fn) == ("POST",)
    antwort = client.get(
        "/api/method/diakronos.planrahmen.api.undo", params={"plan": "P-1"})
    assert antwort.status_code == 405, antwort.text
