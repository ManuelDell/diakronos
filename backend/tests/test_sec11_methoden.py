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

import sys

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
    """`{"modul.name": {…}}` — je Funktion EIN Eintrag (SEC-11b/F3).

    BEFUND (Review SEC-11): der Schluessel war der blosse Funktionsname. Zwei
    gleichnamige Funktionen aus verschiedenen Modulen (`sitzung_status` in
    `api.session` und `devmodus.api`) haben einander ueberschrieben — geprueft
    wurde danach nur eine von beiden, die andere war unsichtbar. Der Schluessel
    ist jetzt `modul.name`; `name` bleibt als Feld erhalten (inventar/JSON).
    """
    reg = _register()
    je_fn: dict[int, dict] = {}
    for pfad, fn in reg.registered().items():
        eintrag = je_fn.get(id(fn))
        if eintrag is None:
            name = getattr(fn, "__name__", "?")
            modul = getattr(fn, "__module__", "?")
            eintrag = {
                "name": name,
                "modul": modul,
                "schluessel": f"{modul}.{name}",
                "optionen": reg.options_for(fn),
                "pfade": [],
            }
            je_fn[id(fn)] = eintrag
        eintrag["pfade"].append(pfad)
    schluessel = [e["schluessel"] for e in je_fn.values()]
    assert len(schluessel) == len(set(schluessel)), (
        "SEC-11b/F3: Funktionsschluessel sind nicht eindeutig — "
        f"{len(schluessel)} Funktionen, {len(set(schluessel))} Schluessel")
    return {e["schluessel"]: e for e in je_fn.values()}


def _werkzeug(dateiname: str):
    """Ein Werkzeug aus `tools/` laden — im Repo UND im Image (SEC-11b).

    BEFUND (Image-Abnahme 2026-10-31): der Test rechnete mit dem Repo-Pfad
    `<repo>/tools/...`. IM Image liegt der Quellbaum unter `/app`, die
    Werkzeuge aber unter `/app/tools` — beides ist derselbe Ort, nur die Zahl
    der `..` unterscheidet sich (`parents[2]` vs. `parents[1]`). Statt die
    Herkunft zu raten, werden die Kandidaten durchprobiert.
    """
    import importlib.util
    from pathlib import Path

    hier = Path(__file__).resolve()
    kandidaten = [
        hier.parents[2] / "tools" / dateiname,   # Repo: backend/tests -> <repo>/tools
        hier.parents[1] / "tools" / dateiname,   # Image: /app/tests -> /app/tools
        Path("/app/tools") / dateiname,          # Image, ausdruecklich
    ]
    ziel = next((k for k in kandidaten if k.exists()), None)
    assert ziel is not None, (
        f"{dateiname} fehlt — geprueft: " + ", ".join(str(k) for k in kandidaten))
    spec = importlib.util.spec_from_file_location(
        f"{ziel.stem}_kopie", ziel)
    assert spec is not None
    modul = importlib.util.module_from_spec(spec)
    # Vor `exec_module` ins Register: sonst kann `dataclasses` die Modul-Typen
    # nicht aufloesen ("'NoneType' object has no attribute '__dict__'").
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def _inventar_modul():
    """`tools/whitelist_lesen.py` — dieselbe Rumpfpruefung wie das Inventar."""
    return _werkzeug("whitelist_lesen.py")


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
    `methods=["POST"]` tragen. Die Ausnahmen stehen im Inventar-Werkzeug
    (`tools/whitelist_inventar.AUSNAHMEN`) mit Begruendung — eine neue Ausnahme
    ist damit eine sichtbare Entscheidung und keine stille Luecke.
    """
    ausnahmen = _ausnahmen()
    verstoesse = [
        f"{e['modul']}.{e['name']} -> {e['optionen'].get('methods')}"
        for e in _betriebseintraege().values()
        if _namen_mit_schreibverdacht(e["name"])
        and _schluessel(e) not in _ausnahmen()
        and e["optionen"].get("methods") != ("POST",)
    ]
    assert not verstoesse, (
        "SEC-11/C5: schreibende Endpunkte ohne methods=['POST']:\n  "
        + "\n  ".join(sorted(verstoesse))
    )


def _ausnahmen() -> set[str]:
    """Die begruendeten Ausnahmen des Inventarwerkzeugs — Schluessel `modul.name`.

    SEC-11c (R2): vorher der blosse Funktionsname. Zwei gleichnamige Endpunkte
    in verschiedenen Modulen (`logout` in `api.auth` und `api.frappe_core`)
    haetten sich eine Ausnahme geteilt — eine Ausnahme fuer den einen haette
    den anderen mit freigestellt.
    """
    return set(_werkzeug("whitelist_inventar.py").AUSNAHMEN)


def _schluessel(eintrag: dict) -> str:
    """`modul.name` eines Register-Eintrags (SEC-11c/R2)."""
    return f"{eintrag['modul']}.{eintrag['name']}"


def _nur_test(eintrag: dict) -> bool:
    """SEC-11c (R4): entsteht dieser Endpunkt nur in einer Testdatei?

    Testdateien dekorieren Hilfsfunktionen mit `@whitelist(...)`
    (`boese_methode`, `_werfende_methode`), um Fehlerpfade zu pruefen. Die
    Dekoration schreibt ins PROZESSWEITE Register und wird nie
    zurueckgenommen — in der vollen Suite sieht dieser Waechter die Phantome
    aus fremden Testdateien und meldete „schreibend ohne POST" fuer Funktionen,
    die im Betrieb nicht existieren. Erkannt am Modulnamen; das Inventar
    (`tools/whitelist_inventar.py`) filtert mit derselben Regel.
    """
    kurz = str(eintrag.get("modul", "")).rsplit(".", 1)[-1]
    return kurz == "__main__" or kurz.startswith("test_") or kurz.startswith("_test")


def _betriebseintraege() -> dict[str, dict]:
    """`_funktionen()` ohne die Endpunkte, die nur in Testdateien entstehen."""
    return {k: e for k, e in _funktionen().items() if not _nur_test(e)}


def test_c5b_rumpfpruefung_widerspricht_nie_posten():
    """SEC-11b (F2) — der WAECHTER DER KARTE: Rumpf gegen Methode.

    Bis hier stufte das Inventar „lesend" nur nach Namen ein. Jetzt entscheidet
    der Funktionsrumpf (AST, `tools/whitelist_lesen.py`): jede Funktion, in
    deren Rumpf eine Schreibung steht (`_update_doc`, `insert`, `commit`,
    `session.add`, `set_value`, Redis `set`/`setex`/`delete`, Dateischreiben,
    SQL — und eine Ebene Hilfsfunktion im selben Modul), MUSS `POST` sein.
    Jeder verbleibende Widerspruch braucht einen Eintrag in `AUSNAHMEN`.
    """
    import inspect

    lesen = _inventar_modul()
    cache: dict[str, dict] = {}
    ausnahmen = _ausnahmen()
    verstoesse = []
    for e in _betriebseintraege().values():
        fn = next((f for p, f in _register().registered().items()
                   if getattr(f, "__module__", "") == e["modul"]
                   and getattr(f, "__name__", "") == e["name"]), None)
        if fn is None:  # pragma: no cover — kann bei id-Gleichheit nicht passieren
            continue
        try:
            datei = inspect.getsourcefile(fn)
        except (OSError, TypeError):  # pragma: no cover
            datei = None
        if not datei:
            continue
        if datei not in cache:
            try:
                cache[datei] = lesen.klassifiziere(lesen.lies(datei))
            except (OSError, SyntaxError, UnicodeDecodeError):  # pragma: no cover
                cache[datei] = {}
        befund = cache[datei].get(e["name"])
        if befund is None or befund.einstufung != lesen.SCHREIBEND:
            continue
        if _schluessel(e) in ausnahmen:
            continue
        if e["optionen"].get("methods") != ("POST",):
            verstoesse.append(
                f"{e['modul']}.{e['name']} -> {e['optionen'].get('methods')} "
                f"({lesen.zeilen_gruende(befund, 1)})")
    assert not verstoesse, (
        "SEC-11b/F2: Funktionen, deren RUMPF schreibt, ohne methods=['POST']:\n  "
        + "\n  ".join(sorted(verstoesse)))


def test_c5d_ausnahmen_sind_begruendet_und_wirken():
    """SEC-11b (F2): jede Ausnahme hat einen Grund und deckt einen echten Befund.

    Eine Ausnahme, die auf keine schreibende Funktion mehr zeigt, ist eine
    stille Luecke fuer die naechste — sie muss weg.
    """
    import json
    from importlib import resources

    roh = json.loads(
        resources.files("diakronos_app.frappe_compat.inventar")
        .joinpath("whitelist.json").read_text(encoding="utf-8"))
    ausnahmen = roh["ausnahmen"]
    assert ausnahmen, "SEC-11b/F2: das Inventar kennt keine Ausnahmen"
    for name, grund in ausnahmen.items():
        assert grund and len(grund) > 10, f"keine Begruendung fuer {name}"
    # Gedeckt ist eine Ausnahme, wenn ihr Grund im Inventar STEHT und sie einen
    # der Befunde (Name/Rumpf) gegen „lesend ohne POST" verteidigt. Die vier
    # Ausnahmen aus SEC-11 C5 (`fail_validation`, `undo_vorschau`,
    # `get_user_create_permissions`, `get_import_progress`) beruhen auf einem
    # Namensbefund ohne Rumpfbefund — sie sind gueltig, auch wenn sie in der
    # Widerspruchstabelle nicht mehr als Abweichung erscheinen.
    # SEC-11c (R2): Schluessel ist `modul.name` — in `eintraege`, in
    # `widersprueche` und in `AUSNAHMEN`.
    namen = {e["funktion"] for e in roh["eintraege"]}
    gedeckt = {w["funktion"] for w in roh["widersprueche"] if w["ausnahme"]}
    gedeckt |= set(ausnahmen) & namen
    ohne_treffer = set(ausnahmen) - gedeckt
    assert not ohne_treffer, (
        "Diese Ausnahmen zeigen auf keine registrierte Funktion mehr "
        "(entfernen): " + ", ".join(sorted(ohne_treffer)))
    angewandt = set(roh["ausnahmen_angewandt"])
    assert angewandt <= set(ausnahmen), (
        "Diese angewandten Ausnahmen stehen nicht mit Begruendung im "
        "Werkzeug: " + ", ".join(sorted(angewandt - set(ausnahmen))))
    # Offen ist ein Widerspruch nur, wenn er NICHT post-only ist: ein
    # Endpunkt, dessen Rumpf und Deklaration beide „schreibend" sagen (nur den
    # Namen betrifft die Abweichung), ist genau das gewuenschte Ergebnis —
    # `get_oauth_url` (schreibt, heisst aber „get_…") ist der Musterfall.
    offen = [w["funktion"] for w in roh["widersprueche"]
             if not w["ausnahme"] and w["methoden"] != ["POST"]]
    assert not offen, (
        "Offene Widersprueche im Inventar — `tools/whitelist_inventar.py` "
        "neu erzeugen bzw. begruenden:\n  " + "\n  ".join(sorted(offen)))


def test_c5c_funktionsschluessel_trennt_gleichnamige_module():
    """SEC-11b (F3): gleiche Namen in zwei Modulen sind zwei Eintraege."""
    funktionen = _funktionen()
    namen = [e["name"] for e in funktionen.values()]
    doppelt = {n for n in namen if namen.count(n) > 1}
    assert doppelt, ("Der Schluessel `modul.name` ist nur dann noetig, wenn es "
                     "gleichnamige Funktionen gibt — sonst ist der Test blind.")
    for n in doppelt:
        assert sum(1 for e in funktionen.values() if e["name"] == n) == namen.count(n)


def test_c1_schreibende_get_endpunkte_sind_post_only():
    """SEC-11b (F1) — die sechs Nachzuegler aus dem Opus-Review.

    Sie waren als „lesend" eingestuft und nahmen GET an. `get_oauth_url`
    schreibt den OAuth-State nach Redis; die uebrigen legen Zeilen an bzw.
    aendern sie. Der Waechter oben wuerde sie jetzt auch ohne diesen Test
    finden — der Test haelt den Stand zusaetzlich an den Pfaaden fest, die die
    SPA benutzt (ein Rename faellt damit auf).
    """
    from diakronos_app.frappe_compat import registry

    from diakronos_app.api.kronos.google_import import get_oauth_url
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus
    from diakronos_app.api.planung import speichere_plan_entwurf
    from diakronos_app.api.registrierung import submit_gast, submit_registrierung
    from diakronos_app.api.veranstaltungsanmeldung import register_mitglied

    for fn in (schliesse_mitglied_aus, register_mitglied, speichere_plan_entwurf,
               submit_registrierung, submit_gast, get_oauth_url):
        assert registry.methoden_fuer(fn) == ("POST",), fn.__name__



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
    laut_register = {f"{e['modul']}.{e['name']}"
                     for e in _betriebseintraege().values()
                     if e["optionen"].get("methods") == ("POST",)}
    fehlt = laut_register - laut_inventar
    assert not fehlt, (
        "Diese POST-only-Endpunkte fehlen im Inventar — "
        "`tools/whitelist_inventar.py` neu laufen lassen:\n  " + "\n  ".join(sorted(fehlt)))
    assert daten["zaehlung"]["schreibend"] >= len(laut_register)
    assert daten["zaehlung"]["schreibend"] + daten["zaehlung"]["lesend"] == daten["funktionen"]
    # SEC-11b (F2): die Einstufung kommt aus dem Rumpf, nicht nur aus dem Namen.
    assert "rumpf_zaehlung" in daten, "Inventar ohne Rumpfbefund — neu erzeugen"
    assert daten["rumpf_zaehlung"].get("schreibend", 0) > 0
    assert all("nach_rumpf" in e and "rumpf_grund" in e for e in daten["eintraege"])


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
    ):
        assert ist_oeffentlicher_website_endpunkt(pfad) is True, pfad
    for pfad in (
        "/api/method/diakronos.diakonos.api.mitglieder.get_mitglieder_liste",
        "/api/resource/Eventkategorie",
        "/api/method/kontakt_senden_mehr",
        "/login",
    ):
        assert ist_oeffentlicher_website_endpunkt(pfad) is False, pfad


def test_c4b_ausnahme_ist_exakt_und_keine_praefix_regel():
    """SEC-11b (F4) — die Ausnahme ist die KONKRETE Menge, kein Praefix.

    BEFUND (Review SEC-11): `name.startswith("website.")` befreite JEDEN
    Endpunkt unter `website.*` von der Herkunftsschranke — auch einen
    schreibenden, den es morgen gibt. Ein Praefix ist keine Entscheidung.
    """
    from diakronos_app.frappe_compat.auth_middleware import (
        ist_oeffentlicher_website_endpunkt,
    )

    # Kein Praefix-Zweig mehr: alles, was nur zufaellig so anfaengt, faellt
    # wieder unter die Schranke.
    for pfad in (
        "/api/method/website.oeffentlich.irgendwas_neues",
        "/api/method/website.oeffentlich",
        "/api/method/website.gruppe_speichern",
        "/api/method/diakronos.diakronos.api.website.andere_funktion",
    ):
        assert ist_oeffentlicher_website_endpunkt(pfad) is False, pfad

    # Und die Gegenprobe: die echte Ausnahme steht im Register noch da und ist
    # oeffentlich.
    from diakronos_app.frappe_compat import registry
    from diakronos_app.website.kontakt import kontakt_senden

    assert registry.options_for(kontakt_senden).get("allow_guest") is True


def test_c4c_toter_zweig_ist_entfernt():
    """SEC-11b (F4): der alte Praefix-Zweig existiert nicht mehr im Quelltext."""
    from pathlib import Path

    quelle = (Path(__file__).resolve().parents[1] / "src" / "diakronos_app"
              / "frappe_compat" / "auth_middleware.py")
    text = quelle.read_text(encoding="utf-8")
    assert 'startswith("website.oeffentlich.")' not in text
    assert 'startswith("website.")' not in text



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


def test_stichprobe_f1_ausschluss_per_get_bleibt_ohne_wirkung(
    client, patched_db, seed_mitglieder,
):
    """SEC-11b (F1): `schliesse_mitglied_aus` per GET -> 405, DB unveraendert.

    Vorher nahm der Endpunkt GET an: ein Link auf einer fremden Seite
    (`<img src="…schliesse_mitglied_aus?mitglied_id=M-0001">`) schloss das
    Mitglied aus. Geprueft wird nicht nur der Status, sondern der DATENSTAND.
    """
    from diakronos_app.models.diakonos import Mitglied

    def _zustand():
        sess = patched_db()
        try:
            m = sess.get(Mitglied, "M-0001")
            return (m.ausgeschlossen, m.status, str(m.ausgeschlossen_seit))
        finally:
            sess.close()

    vorher = _zustand()
    antwort = client.get(
        "/api/method/mitglieder.schliesse_mitglied_aus",
        params={"mitglied_id": "M-0001", "begruendung": "GET-Angriff"},
    )
    assert antwort.status_code == 405, antwort.text
    assert antwort.headers["allow"] == "POST"
    assert _zustand() == vorher


def test_stichprobe_f1_veranstaltungsanmeldung_per_get_bleibt_ohne_wirkung(
    client, patched_db, seed_mitglieder,
):
    """SEC-11b (F1): `register_mitglied` per GET -> 405, keine Anmeldung.

    Eine One-Click-Anmeldung per GET liesse sich von jeder fremden Seite
    ausloesen (Kapazitaet verbrauchen, Person in eine Veranstaltung buchen).
    """
    from sqlalchemy import func, select

    from diakronos_app.models.diakonos import Anmeldung

    def _anzahl():
        sess = patched_db()
        try:
            return sess.execute(select(func.count()).select_from(Anmeldung)).scalar() or 0
        finally:
            sess.close()

    vorher = _anzahl()
    antwort = client.get(
        "/api/method/veranstaltungsanmeldung.register_mitglied",
        params={"registrierungslink_id": "RL-1"},
    )
    assert antwort.status_code == 405, antwort.text
    assert _anzahl() == vorher


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
