"""BS-2a2 — Nachbesserung der Baustein-Bibliothek (Befunde F1–F7).

Was hier festgehalten wird
==========================
F1  Mehrtägige/ganztägige Termine zeigen ihren Zeitraum
    („Fr., 07.11. – So., 09.11.") — und das Ende wird NICHT um einen Tag
    gekürzt, weil Diakronos das Ganztags-Ende einschließlich speichert.
F2  In-Prozess-Merker: eine bestätigt installierte Version wird je Prozess
    nur EINMAL geprüft (kein Superuser-Auth + Voll-Export bei jedem Login).
F3  Der Rückfallweg (Einzel-API) ist idempotent — Upsert über (Gruppe, Name)
    statt jedes Mal neuer Datensätze; fehlt der Import-Endpunkt, gibt es eine
    klare Meldung.
F4  Die SHA-Menge hängt an VERSION: Code geändert ohne VERSION-Erhöhung ->
    Test rot. Die Prüfsummen stehen dafür in ``quellen/PRUEFSUMMEN.json``.
F5  Funktionsname ``_superuser_token`` (nicht mehr ``_development_token``);
    ``lang="de"`` an den Wurzelelementen, soweit Primo das zulässt.
F6  Sichtbare Texte sind Felder des Bausteins; 400 auf ``postfach`` hat eine
    eigene Meldung.
F7  ``_export_zip`` gibt ``(bytes, revision)`` zurück.

Kein Test greift auf die Betriebsdatenbank zu (Karten-Nachtrag 11) und keiner
auf ein echtes Primo: der HTTP-Verkehr läuft über ``httpx.MockTransport``.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile

import httpx
import pytest

from diakronos_app.website import bausteine as bibliothek

# ── Hilfen ─────────────────────────────────────────────────────────────────


def quelle(kennung: str) -> str:
    """Der Quelltext eines Bausteins (aus dem PAKET, wie zur Laufzeit)."""
    for baustein in bibliothek.bausteine_lesen():
        if baustein.kennung == kennung:
            return baustein.quelle
    raise AssertionError(f"Baustein {kennung} fehlt")


def prüfsummen() -> dict[str, str]:
    """Der Inhalt von ``quellen/PRUEFSUMMEN.json`` (Kennung -> SHA-256)."""
    pfad = bibliothek._wurzel() / "PRUEFSUMMEN.json"  # noqa: SLF001 — Paketressource
    return json.loads(pfad.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def merker_leeren():
    """Jeder Test beginnt mit leerem Prozess-Merker (F2)."""
    bibliothek.merker_zuruecksetzen()
    yield
    bibliothek.merker_zuruecksetzen()


# ── F1: Zeitraum mehrtägiger Termine ───────────────────────────────────────


def test_f1_zeitraum_ist_im_baustein():
    """Der Baustein berechnet und zeigt den Zeitraum (F1)."""
    text = quelle("termine-liste")
    assert "function ende_text(" in text, "ende_text fehlt"
    assert "zeitraum: ende_text(beginn, eintrag.ende)" in text
    assert "{termin.zeitraum}" in text
    # Die Anzeige setzt den Zeitraum NEBEN den Beginn.
    assert "dk-termine__bis" in text


def test_f1_kein_tag_wird_abgezogen():
    """F1-Kern: das Ende kommt unverändert aus der Antwort.

    Diakronos speichert das Ganztags-Ende EINSCHLIESSLICH und die Lese-API
    gibt es so aus (``ende`` = letzter Tag). Ein ``- 1 Tag`` im Baustein wäre
    genau der Fehler, den die Karte verbietet.
    """
    text = quelle("termine-liste")
    block = text[text.index("function ende_text("):]
    block = block[: block.index("\n  }")]
    # Keine Tagesarithmetik im Zeitraum: kein getDate()-1, kein 86400000,
    # kein setDate, kein setHours(0,0,0,0)-Abzug.
    for verboten in ("86400000", "getDate() - 1", "getDate()-1", "setDate(", "minus"):
        assert verboten not in block, f"Tagesarithmetik im Zeitraum: {verboten!r}"


def test_f1_zeitraum_nur_bei_mehrtaegig():
    """Gleicher Kalendertag -> kein Zeitraum (sonst stünde „Fr. – Fr.“)."""
    text = quelle("termine-liste")
    block = text[text.index("function ende_text("):]
    assert "isodatum(beginn) === isodatum(ende_datum)" in block[:400]
    assert "return ''" in block[:400]


def test_f1_eintagiger_laufzeitfall():
    """Laufzeitprobe der F1-Regel in Node-freier Form (nachgerechnet).

    Die Zeitraum-Entscheidung hängt allein am Kalendertag des Endes; hier
    dieselbe Regel in Python gegen die Werte, die die Lese-API liefert.
    """

    def zeitraum(beginn: str, ende: str) -> str:
        # Regel wie im Baustein: verschiedene Kalendertage -> Zeitraum.
        return "ja" if beginn[:10] != ende[:10] else "nein"

    # Mehrtägig ganztägig: 07.11. bis einschließlich 09.11.
    assert zeitraum("2026-11-07T00:00:00+01:00", "2026-11-09T00:00:00+01:00") == "ja"
    # Eintägig mit Uhrzeit
    assert zeitraum("2026-11-07T10:00:00+01:00", "2026-11-07T11:30:00+01:00") == "nein"


# ── F2: In-Prozess-Merker ──────────────────────────────────────────────────


def test_f2_merker_startet_leer():
    assert bibliothek.bestaetigte_version() == 0
    assert bibliothek.steht_bereit() is False


def test_f2_merker_nur_aufwaerts():
    bibliothek.version_bestaetigen(2)
    assert bibliothek.steht_bereit(2) is True
    assert bibliothek.steht_bereit(3) is False
    bibliothek.version_bestaetigen(1)  # ältere Lesung darf nicht zurücksetzen
    assert bibliothek.bestaetigte_version() == 2
    bibliothek.version_bestaetigen("unbrauchbar")
    assert bibliothek.bestaetigte_version() == 2


def test_f2_nachziehen_ohne_zweiten_export(monkeypatch):
    """F2-Kern: der zweite Übergang im selben Prozess macht KEINEN HTTP-Call.

    Erster Lauf: Stand wird gelesen (Superuser-Auth + Export) und bestätigt.
    Zweiter Lauf: ``_bausteine_nachziehen`` kehrt sofort zurück.
    """
    from diakronos_app.api import website as api_website

    anfragen: list[str] = []

    def antwort(request: httpx.Request) -> httpx.Response:
        anfragen.append(request.url.path)
        if request.url.path.endswith("/api/collections/_superusers/auth-with-password"):
            return httpx.Response(200, json={"token": "t-1"})
        if request.url.path.endswith("/api/primo/export-library"):
            # Eine Bibliothek, die die MITGELIEFERTE Version schon enthaelt —
            # nur dann ist "nichts nachzuziehen" die richtige Antwort.
            version = bibliothek.mitgelieferte_version()
            speicher = io.BytesIO()
            with zipfile.ZipFile(speicher, "w") as archiv:
                archiv.writestr("library/groups.yaml", '- id: ""\n  name: "Diakronos"\n')
                for kennung in ("kontakt", "termine-liste"):
                    archiv.writestr(
                        f"library/diakronos/{kennung}/config.yaml",
                        f'name: "diakronos/{kennung}@v{version}"\n',
                    )
            return httpx.Response(
                200,
                content=speicher.getvalue(),
                headers={"X-Primo-Revision": "v1:abc"},
            )
        return httpx.Response(404, json={"message": "nicht da"})

    transport = httpx.MockTransport(antwort)

    def client():
        return httpx.Client(transport=transport, timeout=5.0, trust_env=False)

    monkeypatch.setattr(bibliothek, "_client", client)
    # Settings sind pydantic-Properties (`primo_konfiguriert` ist abgeleitet) —
    # gesetzt werden die ROHWERTE, wie im BS-2a-Test.
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "primo_url", "http://primo.test:8080", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_email", "su@example.org", raising=False)
    monkeypatch.setattr(
        settings, "primo_superuser_password", "geheim-fuer-den-test", raising=False
    )

    api_website._bausteine_nachziehen()  # noqa: SLF001 — genau das wird geprüft
    assert anfragen, "erster Lauf muss den Stand lesen"
    assert bibliothek.bestaetigte_version() >= bibliothek.mitgelieferte_version()
    erste_runde = list(anfragen)

    api_website._bausteine_nachziehen()  # noqa: SLF001
    assert anfragen == erste_runde, (
        f"zweiter Lauf hat Primo erneut gefragt: {anfragen[len(erste_runde):]}"
    )


def test_f2_fehler_verhindert_login_nicht(monkeypatch):
    """Ein Fehler im Nachziehen bleibt folgenlos (Kartenvorgabe)."""
    from diakronos_app.api import website as api_website

    def platzt(*_args, **_kwargs):
        raise RuntimeError("Primo weg")

    monkeypatch.setattr(bibliothek, "bibliothek_stand", platzt)
    api_website._bausteine_nachziehen()  # noqa: SLF001 — darf NIE werfen
    assert bibliothek.bestaetigte_version() == 0


# ── F3: Rückfallweg idempotent ─────────────────────────────────────────────


def test_f3_einzelweg_ist_upsert():
    """F3: der Einzelweg sucht VOR dem Anlegen (Upsert über Gruppe + Name)."""
    import inspect

    einzelweg = inspect.getsource(bibliothek._import_einzeln)  # noqa: SLF001
    upsert = inspect.getsource(bibliothek._upsert)  # noqa: SLF001
    suche = inspect.getsource(bibliothek._finde_eintrag)  # noqa: SLF001
    # Der Einzelweg schreibt JEDE Sammlung über den Upsert (Gruppe, Block,
    # Feld, Vorgabe) — kein blankes POST mehr.
    assert einzelweg.count("_upsert(") >= 4, "Gruppe, Block, Feld und Vorgabe per Upsert"
    assert "client.post(" not in einzelweg, "kein direktes Anlegen mehr im Einzelweg"
    # Der Upsert sucht ZUERST (GET mit Filter) und entscheidet dann PATCH/POST.
    assert "client.patch(" in upsert
    assert "client.post(" in upsert
    assert "_finde_eintrag(" in upsert
    assert '"filter": filter_' in suche
    for sammlung in (
        "library_symbol_groups",
        "library_symbols",
        "library_symbol_fields",
        "library_symbol_entries",
    ):
        assert sammlung in einzelweg, f"{sammlung} fehlt im Einzelweg"


def test_f3_import_endpunkt_fehlt_klare_meldung(monkeypatch):
    """F3: fehlt der Import-Endpunkt, meldet der Installer den Rückfallweg."""
    meldungen: list[str] = []

    class FakeLogger:
        def info(self, text, *args, **kwargs):
            meldungen.append(text % args if args else text)

        def warning(self, text, *args, **kwargs):
            meldungen.append(text % args if args else text)

        def debug(self, *_a, **_k):
            pass

    monkeypatch.setattr(bibliothek, "logger", FakeLogger())
    monkeypatch.setattr(bibliothek, "_superuser_token", lambda: "t-1")
    monkeypatch.setattr(bibliothek, "revision_holen", lambda token: "v1:x")

    def kein_import(token, paket, revision):
        raise bibliothek.PrimoSyncAbgelehnt(404, "kein Endpunkt")

    monkeypatch.setattr(bibliothek, "_import_zip", kein_import)
    monkeypatch.setattr(
        bibliothek, "_import_einzeln", lambda *a, **k: "einzeln"
    )
    ergebnis = bibliothek.sync()
    assert ergebnis.weg == "einzeln"
    assert any("Einzelweg" in text for text in meldungen), meldungen


# ── F4: SHA-Menge hängt an VERSION ─────────────────────────────────────────


def test_f4_pruefsummendatei_passt_zu_version():
    """F4-Kern: Prüfsummen tragen die VERSION, zu der sie gebildet wurden."""
    daten = prüfsummen()
    assert int(daten["version"]) == bibliothek.mitgelieferte_version(), (
        "PRUEFSUMMEN.json gehört zu einer anderen VERSION — `python "
        "tools/bausteine_sync.py` ausführen und VERSION erhöhen"
    )


def test_f4_sha_je_baustein_aktuell():
    """F4: je Baustein steht die SHA der aktuellen Quellen in der Datei."""
    daten = prüfsummen()
    aktuell = {b.kennung: b.sha256 for b in bibliothek.bausteine_lesen()}
    assert set(aktuell) == set(daten["bausteine"]), "andere Bausteinmenge als geprüft"
    for kennung, sha in aktuell.items():
        assert daten["bausteine"][kennung] == sha, (
            f"{kennung}: Code/Felder geändert, aber VERSION {daten['version']} "
            "nicht erhöht (PRUEFSUMMEN.json neu schreiben)"
        )


def test_f4_code_aenderung_ohne_version_wird_erkannt():
    """F4: eine geänderte Quelle fällt gegen die Prüfsumme auf (Gegenprobe)."""
    baustein = bibliothek.bausteine_lesen()[0]
    geaendert = baustein.quelle + "\n<!-- Teständerung -->\n"
    sha = hashlib.sha256(
        (
            geaendert
            + "\n#felder\n"
            + json.dumps(list(baustein.felder), ensure_ascii=False, sort_keys=True)
        ).encode("utf-8")
    ).hexdigest()
    assert sha != prüfsummen()["bausteine"][baustein.kennung]


# ── F5: Name und Sprache ───────────────────────────────────────────────────


def test_f5_tokenfunktion_heisst_superuser_token():
    import inspect

    assert hasattr(bibliothek, "_superuser_token")
    assert not hasattr(bibliothek, "_development_token")
    assert "auth-with-password" in inspect.getsource(bibliothek._superuser_token)


def test_f5_wurzelelement_traegt_sprache():
    """F5: die Wurzelelemente nennen die Sprache (sofern Primo das zulässt).

    Primo setzt ``<html lang>`` der Site; ein Baustein darf kein zweites
    ``<html>`` erzeugen. Er setzt die Sprache deshalb am eigenen
    Wurzelelement — das ist gültiges HTML und vererbt an alle Kinder.
    """
    for kennung in ("kontakt", "termine-liste"):
        text = quelle(kennung)
        erste_zeile = text.splitlines()[0]
        assert erste_zeile.startswith("<section"), f"{kennung}: Wurzel ist kein <section>"
        assert 'lang="de"' in erste_zeile, f"{kennung}: lang=\"de\" fehlt"
        assert "<html" not in text, f"{kennung}: zweites <html> wäre ungültig"


# ── F6: Texte als Felder, Postfach-Meldung ─────────────────────────────────


def test_f6_sichtbare_texte_sind_felder():
    """F6: die früher fest verdrahteten Texte kommen aus Feldern."""
    kontakt = {f["name"]: f for b in bibliothek.bausteine_lesen()
               if b.kennung == "kontakt" for f in b.felder}
    termine = {f["name"]: f for b in bibliothek.bausteine_lesen()
               if b.kennung == "termine-liste" for f in b.felder}
    for name in (
        "text_name",
        "text_email",
        "text_nachricht",
        "text_sendet",
        "text_postfach",
        "text_postfach_fehler",
        "text_rate_limit",
        "text_adresse_fehlt",
    ):
        assert name in kontakt, f"Feld {name} fehlt (F6)"
    for name in ("text_ganztaegig", "text_laedt", "text_anmeldung"):
        assert name in termine, f"Feld {name} fehlt (F6)"

    # Die Texte stehen NICHT mehr fest im Markup.
    kontakt_text = quelle("kontakt")
    assert ">Ihr Name<" not in kontakt_text
    assert ">Wird gesendet …<" not in kontakt_text
    assert ">Zur Anmeldung<" not in quelle("termine-liste")
    assert ">Termine werden geladen …<" not in quelle("termine-liste")


def test_f6_postfach_400_hat_eigene_meldung():
    """F6: eine 400-Antwort auf ``postfach`` wird am Feld gezeigt."""
    text = quelle("kontakt")
    assert "schluessel === 'postfach'" in text
    assert "id_postfach + '-fehler'" in text
    assert "text_postfach_fehler_server" in text


# ── F7: Rückgabetyp ────────────────────────────────────────────────────────


def test_f7_export_zip_gibt_tupel():
    """F7: ``_export_zip`` liefert ``(zip_bytes, revision)`` — nicht nur Bytes."""
    import inspect
    import typing

    # `from __future__ import annotations` macht die Annotation zum String —
    # geprueft wird die Typaufloesung (get_type_hints), nicht der Rohtext.
    hinweise = typing.get_type_hints(bibliothek._export_zip)  # noqa: SLF001
    assert hinweise["return"] == tuple[bytes, str], hinweise["return"]
    quelle_text = inspect.getsource(bibliothek._export_zip)  # noqa: SLF001
    assert "return antwort.content or b\"\", revision" in quelle_text
    # Und der Aufrufer packt beide Werte aus.
    assert "roh, revision = _export_zip(token)" in inspect.getsource(
        bibliothek.bibliothek_stand
    )


# ── Import-Vertrag der Endpunkte (BS-2a2, aus der Abnahme) ────────────────


def test_endpunkt_importiert_nur_vorhandene_ausnahmen():
    """Beim ersten Fehlerfall brach `bausteine_installieren` mit ImportError ab.

    Gefunden in der Abnahme 2026-11-03: `from …frappe_compat.exceptions import
    Error as FrappeError` — die Compat-Schicht hat kein `Error`, die Ausnahme
    heisst `FrappeCompatError`. Folge: statt der generischen Meldung kam ein
    500 mit Interna. Dieser Test haelt ALLE Namen fest, die das Modul aus
    `frappe_compat.exceptions` importiert.
    """
    import importlib
    import re
    from pathlib import Path

    from diakronos_app.frappe_compat import exceptions as compat

    quelle = Path(bibliothek.__file__).resolve().parents[1] / "api" / "website.py"
    text = quelle.read_text(encoding="utf-8")
    bloecke = re.findall(
        r"from diakronos_app\.frappe_compat\.exceptions import \(([^)]*)\)",
        text,
    ) + re.findall(
        r"from diakronos_app\.frappe_compat\.exceptions import ([^\n(]+)",
        text,
    )
    assert bloecke, "kein Import aus frappe_compat.exceptions gefunden"
    for block in bloecke:
        for name in re.split(r",\s*", block.strip()):
            name = name.split(" as ")[0].strip()
            if not name:
                continue
            assert hasattr(compat, name), f"frappe_compat.exceptions hat kein {name!r}"
    importlib.import_module("diakronos_app.api.website")


def test_kein_onmount_im_baustein():
    """BS-2a2 (Abnahme-Befund): `onMount` bricht den Publish ab.

    Primo rendert Abschnitte mit `svelte/server` (`render(App, …)`, siehe
    `src/lib/compiler/processors.js`). Dort wirft `onMount` die Ausnahme
    `lifecycle_outside_component` — der Fehler landet als „Render error" im
    Publish und die Site bleibt leer. Abschnitte sind SERVER-Komponenten; der
    Abruf gehoert in `$effect`, das bei SSR nicht laeuft.

    Geprueft wird der CODE, nicht die Kommentare: der Befund steht als
    Kommentar im Baustein (mit Namen), ausgefuehrt werden darf er nie.
    """
    for kennung in ("kontakt", "termine-liste"):
        text = quelle(kennung)
        # Nur der <script>-Teil zaehlt; Kommentarzeilen darin werden entfernt.
        skript = text.split("<script>", 1)[1].split("</script>", 1)[0]
        code = "\n".join(
            zeile for zeile in skript.splitlines() if not zeile.strip().startswith("//")
        )
        assert "onMount(" not in code, f"{kennung}: onMount ist im Primo-Render verboten"
        assert "import { onMount }" not in code, f"{kennung}: onMount importiert"
        assert "$effect(" in code, f"{kennung}: der Abruf muss in $effect laufen"


# ── Postfach-Liste: der Pfad, den der Baustein ruft ───────────────────────


def test_postfaecher_liegt_auf_der_leseroute():
    """Der Kontakt-Baustein holt `{Basis}/website/oeffentlich/postfaecher`.

    Abnahmebefund BS-2a2: der Name fehlte in `_PARAMETER`/`_funktionen` der
    Leseroute — der Baustein bekam 404 und zeigte die Postfach-AUSWAHL nie an,
    obwohl `/api/method/website.oeffentlich.postfaecher` die Liste lieferte
    (die Auswahl „fehlte im Build", ohne dass es auffiel). Der Baustein darf
    hier nicht auf die Frappe-Bahn ausweichen: er laeuft auf einer fremden
    Herkunft und braucht die CORS-Fassung.

    Geprueft wird die ROUTE (echter Pfad, echter Dispatcher), nicht nur die
    Tabelle — sonst waere ein Name ohne Funktion erneut still.
    """
    from diakronos_app.website import oeffentlich_api

    assert "postfaecher" in oeffentlich_api._PARAMETER
    fn = oeffentlich_api._funktionen()["postfaecher"]
    assert fn.__name__ == "postfaecher_oeffentlich"

    # Der Dispatcher loest den Pfad auf DIESE Funktion auf (kein 404).
    from starlette.requests import Request

    bereich = {"type": "http", "method": "GET",
               "path": "/website/oeffentlich/postfaecher",
               "raw_path": b"/website/oeffentlich/postfaecher",
               "query_string": b"", "headers": [], "scheme": "http",
               "server": ("test", 80), "client": ("127.0.0.1", 1),
               "root_path": "", "http_version": "1.1"}
    request = Request(bereich)
    assert oeffentlich_api._funktionen().get(
        [t for t in request.url.path.split("/") if t][-1]
    ) is fn


def test_postfaecher_leseroute_antwortet_liste(guest_client):
    """End-to-End: die Leseroute liefert die Postfach-Liste (200), keine 404.

    Ohne Postfaecher-Zeile ist die Liste leer — die Antwort bleibt 200 (Zustand
    vor der Einrichtung), aber sie kommt von der RICHTIGEN Funktion. Genau das
    war vorher nicht der Fall: die Route kannte den Namen nicht und antwortete
    404 „Nicht gefunden".
    """
    antwort = guest_client.get("/website/oeffentlich/postfaecher")
    assert antwort.status_code == 200, antwort.text
    # Frappe-Huelle wie bei allen anderen Endpunkten: `{"message": {...}}`.
    rumpf = antwort.json()["message"]
    assert "postfaecher" in rumpf, rumpf
    assert isinstance(rumpf["postfaecher"], list)


def test_kontakt_touch_ziel_mindestens_44_px():
    """Jedes Bedienelement des Kontaktformulars ist >= 44 px hoch (UI-Prinzip K4).

    Abnahmebefund BS-2a2: `min-height: 2.5rem` sind 40 px — die Postfach-AUSWAHL
    (`select`) blieb bei 375 px genau auf dieser Hoehe, die Textfelder kamen
    durch Innenabstand zufaellig auf 44 px. Auf dem Telefon ist das zu knapp.

    Geprueft wird, dass kein Eingabeelement unter 44 px (= 2.75rem) liegen kann:
    die Mindesthoehe steht auf der gemeinsamen Regel UND auf `select`.
    """
    import re

    text = quelle("kontakt")
    css = text.split("<style>", 1)[1].split("</style>", 1)[0]

    treffer = re.search(
        r"\.dk-kontakt__eingabe\s*\{[^}]*?min-height:\s*([^;]+);", css, re.S
    )
    assert treffer, "die gemeinsame Eingabe-Regel hat keine min-height"
    wert = treffer.group(1).strip()
    assert "2.75rem" in wert, f"min-height zu klein: {wert}"

    select = re.search(
        r"select\.dk-kontakt__eingabe\s*\{[^}]*?min-height:\s*([^;]+);", css, re.S
    )
    assert select, "dem select fehlt die ausdrueckliche Mindesthoehe"
    assert "2.75rem" in select.group(1), (
        f"select-Mindesthoehe zu klein: {select.group(1)}"
    )
    # Altwert darf nirgends mehr stehen (sonst gilt er fuer einzelne Selektoren).
    assert "min-height: 2.5rem" not in css, "2.5rem (40 px) steckt noch in der Regel"


# ── Dunkelmodus: Bausteine erben von der Site (Entscheidung 2026-11-04) ─────


def _css(kennung: str) -> str:
    return quelle(kennung).split("<style>", 1)[1].split("</style>", 1)[0]


def test_dunkel_keine_hexfarbe_als_textfarbe():
    """Befund der Abnahme 2026-11-03: ``color: var(--dk-farbe-text, #1f2933)``
    blieb im ``prefers-color-scheme: dark`` auf dunklem Primo-Grund stehen
    (Kontrast ~1,3:1, unlesbar). Eine feste Farbe darf die geerbte Textfarbe
    der Site nicht mehr ueberschreiben.

    Ausnahme: ``color`` INNERHALB des Knopf-Blocks. Dort traegt der Akzent die
    FLAECHE, und auf einer gefuellten Flaeche ist geerbte Schrift falsch.
    """
    for kennung in ("kontakt", "termine-liste"):
        im_knopf = False
        for zeile in _css(kennung).splitlines():
            if zeile.rstrip().endswith("{"):
                im_knopf = "__knopf" in zeile
            elif zeile.strip() == "}":
                im_knopf = False
            if im_knopf or not re.match(r"^\s*color\s*:", zeile):
                continue
            assert not re.search(r"#[0-9a-fA-F]{3,8}\b", zeile), (
                f"{kennung}: Hexfarbe als Textfarbe -> {zeile.strip()}"
            )


def test_dunkel_text_und_flaeche_erben():
    """Text erbt, Flaeche bleibt durchsichtig, gedaempft/Rahmen folgen der
    geerbten Farbe (``color-mix``) — so stimmt der Kontrast in beiden Modi."""
    for kennung in ("kontakt", "termine-liste"):
        css = _css(kennung)
        assert re.search(r"color:\s*var\(--dk-farbe-text,\s*inherit\)", css), (
            f"{kennung}: Text muss erben (Fallback inherit)"
        )
        assert re.search(
            r"background:\s*var\(--dk-farbe-flaeche,\s*transparent\)", css
        ), f"{kennung}: Flaeche muss transparent bleiben"
        assert "color-mix(in srgb, currentColor 70%, transparent)" in css, (
            f"{kennung}: gedaempfte Schrift folgt currentColor"
        )
        assert "color-mix(in srgb, currentColor 25%, transparent)" in css, (
            f"{kennung}: Rahmen folgt currentColor"
        )


def test_dunkel_akzent_nur_als_flaeche_und_kontur():
    """Der Akzent darf Flaeche/Kontur/Rahmen sein, nie Textfarbe; Warnungen
    werden ueber den Rahmen gezeigt, nicht ueber eine Hex-Textfarbe."""
    for kennung in ("kontakt", "termine-liste"):
        for zeile in _css(kennung).splitlines():
            if not re.match(r"^\s*color\s*:", zeile):
                continue
            assert "--dk-farbe-akzent" not in zeile, (
                f"{kennung}: Akzent als Textfarbe -> {zeile.strip()}"
            )
            assert "--dk-farbe-warnung" not in zeile, (
                f"{kennung}: Warnung als Textfarbe (Warn-Rahmen genuegt) -> {zeile.strip()}"
            )
