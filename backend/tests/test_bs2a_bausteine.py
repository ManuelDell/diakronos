"""BS-2a — Baustein-Bibliothek: Quellen, ZIP-Bau und Installer.

Was hier festgehalten wird
==========================
1. **Quellen und Spiegelung.** ``deploy/primo/bausteine/`` ist die Quelle, das
   Python-Paket die Laufzeitkopie (``importlib.resources``); beide müssen
   gleich sein (``tools/bausteine_sync.py --pruefen``). Sonst ändert jemand
   eine Datei und das Image liefert eine andere aus.
2. **ZIP-Format** = das, was ``export-library`` schreibt (im Wegwerf-Primo
   belegt: ``library/groups.yaml`` + ``library/diakronos/<kennung>/
   {component.svelte,config.yaml,fields.yaml,content.yaml}``).
3. **Idempotenz und „keine Überschreibung angepasster Kopien"** — gegen eine
   GEMOCKTE Primo-API (``httpx.MockTransport``) und zusätzlich gegen einen
   echten Wegwerf-Primo, wenn ``BS2A_PROMO_URL`` gesetzt ist (Abnahme; im
   normalen Testlauf übersprungen, weil dieser Lauf ``--network none`` läuft).
4. **Der Login-Übergang darf nicht scheitern**, wenn das Nachziehen Fehler
   wirft.
5. **Whitelist-Vertrag**: Status ist GET/lesend, Installieren ist POST/allow_guest=False.

Kein Test greift auf die Betriebsdatenbank zu (Karten-Nachtrag 11): die
Primo-Aufrufe gehen an MockTransport bzw. an eine Wegwerf-URL.
"""

from __future__ import annotations

import io
import json
import os
import re
import zipfile
from pathlib import Path

import httpx
import pytest

from diakronos_app.website import bausteine as bibliothek

REPO = Path(__file__).resolve().parents[2]
QUELLE_REPO = REPO / "deploy" / "primo" / "bausteine"
QUELLE_PAKET = (
    REPO / "backend" / "src" / "diakronos_app" / "website" / "bausteine" / "quellen"
)

#: Alle mitgelieferten Bausteine, in der Reihenfolge von `block.json:index`.
#: BS-2c: um Gruppen-Übersicht, Gruppen-Steckbrief, Neuigkeiten und Anmeldung
#: erweitert. BS-2b hat kalender, naechster-gottesdienst und kalender-abo
#: ergaenzt (index 21/22/23). Weitere BS-Karten erweitern NUR diese eine Liste.
BAUSTEINE = (
    "kontakt",
    "termine-liste",
    "kalender",
    "naechster-gottesdienst",
    "kalender-abo",
    "gruppen",
    "gruppe-steckbrief",
    "neuigkeiten",
    "anmeldung",
    # BS-3a: Ansprechpartner mit Einwilligung.
    "ansprechpartner",
)


# ── 1. Quellen und Spiegelung ───────────────────────────────────────────────


def test_paketkopie_ist_aktuell():
    """Quelle (deploy/…) und Laufzeitkopie (Paket) sind identisch.

    Das Werkzeug liegt unter ``tools/`` (nicht im Paket): im Repo eine Ebene
    ueber ``backend/``, im Image unter ``/app/tools``. Der Pfad wird hier
    gesetzt, weil dieser Test der einzige ist, der es braucht.
    """
    import importlib.util
    import sys

    werkzeug = None
    for kandidat in (
        REPO / "tools" / "bausteine_sync.py",
        Path(__file__).resolve().parent.parent / "tools" / "bausteine_sync.py",
    ):
        if kandidat.is_file():
            werkzeug = kandidat
            break
    if werkzeug is None:
        pytest.skip("tools/bausteine_sync.py liegt nicht im Build-Kontext (deploy/ fehlt im Image)")

    spec = importlib.util.spec_from_file_location("bausteine_sync", werkzeug)
    sync = importlib.util.module_from_spec(spec)
    sys.modules["bausteine_sync"] = sync
    spec.loader.exec_module(sync)

    fehlend = sync._fehlend()
    assert not fehlend, f"Quelldatei fehlt: {[str(p) for p in fehlend]}"
    abweichungen = sync.vergleiche()
    assert not abweichungen, (
        "Paketkopie der Bausteine weicht ab — `python tools/bausteine_sync.py` "
        f"ausführen. Unterschiede: {abweichungen}"
    )


def test_version_ist_ganze_zahl():
    assert bibliothek.mitgelieferte_version() >= 1
    assert (QUELLE_REPO / "VERSION").read_text(encoding="utf-8").strip().isdigit()


def test_beide_bausteine_sind_da_und_lesbar():
    liste = bibliothek.bausteine_lesen()
    kennungen = [b.kennung for b in liste]
    assert kennungen == list(BAUSTEINE), kennungen
    for baustein in liste:
        assert baustein.name.startswith("Diakronos:"), baustein.name
        assert len(baustein.felder) >= 5
        assert len(baustein.sha256) == 64
        # Prop-Vertrag: jede Feldkennung steht im Quelltext.
        for feld in baustein.felder:
            assert feld["name"] in baustein.quelle


def test_bs2e_bestandsliste_ist_die_bausteinliste():
    """BS-2e: die Liste der Vertragsprüfungen (``BESTAND``) muss die der
    Bibliothek sein — gleiche Kennungen UND gleiche Reihenfolge.

    Vorher stand sie auf dem Stand von BS-2b (fünf statt neun, ``kalender``
    vor ``termine-liste``): die Prüfungen liefen grün, ohne die neuen
    Bausteine je zu sehen.
    """
    from tests.test_bs2a2_bausteine import BESTAND

    assert tuple(BESTAND) == tuple(BAUSTEINE), (BESTAND, BAUSTEINE)
    assert len(BESTAND) == len(set(BESTAND)), "doppelte Kennung in BESTAND"


def test_felder_haben_vorgabewerte_und_bekannte_typen():
    """Primo legt Vorgaben als Eintrag ab; ein Feld ohne Vorgabe bricht den Build."""
    for baustein in bibliothek.bausteine_lesen():
        for feld in baustein.felder:
            assert "default" in feld, f"{baustein.kennung}/{feld['name']}"
            assert feld["type"] in bibliothek.FELD_TYPEN, feld
            if feld["type"] == "select":
                optionen = (feld.get("config") or {}).get("options") or []
                assert optionen, f"{baustein.kennung}/{feld['name']} ohne Optionen"
                werte = [str(o.get("value")) for o in optionen]
                assert str(feld["default"]) in werte, (
                    f"{baustein.kennung}/{feld['name']}: Vorgabe {feld['default']!r} "
                    "ist keine Option"
                )


def test_kontakt_hat_die_geforderten_felder():
    """B3: Überschrift, Einleitung, Postfach (+Auswahl), Einwilligungstext,
    Datenschutz-Link, Button-, Erfolgs- und Fehlertext."""
    felder = {f["name"] for f in _baustein("kontakt").felder}
    erwartet = {
        "ueberschrift", "einleitung", "basisadresse", "postfach",
        "postfach_auswahl", "einwilligung", "datenschutz_url",
        "datenschutz_text", "button_text", "erfolgstext", "fehlertext",
    }
    assert erwartet <= felder, erwartet - felder


def test_termine_liste_hat_die_geforderten_felder():
    """B4: Überschrift, Kalender, Kategorie, Gruppe, Anzahl, Zeitraum,
    Darstellung, Mehr-Link, Leertext."""
    felder = {f["name"] for f in _baustein("termine-liste").felder}
    erwartet = {
        "ueberschrift", "kalender", "kategorie", "gruppe", "anzahl",
        "zeitraum", "darstellung", "mehr_link", "leertext", "basisadresse",
    }
    assert erwartet <= felder, erwartet - felder


def test_keine_gemeinde_spezifischen_inhalte():
    """G2: keine Gemeindenamen, keine Farbwerte, kein externes CDN im Code.

    ``esm.sh``/Google-Fonts sind verboten; ``svelte`` als Import ist erlaubt
    (Primo löst ihn über seine eigene CDN-Auflösung auf).
    """
    verboten = ("Musterhausen", "ECG", "esm.sh", "fonts.googleapis", "cdn.jsdelivr")
    for baustein in bibliothek.bausteine_lesen():
        for wort in verboten:
            assert wort not in baustein.quelle, f"{baustein.kennung}: {wort}"
        # Keine hartkodierten Hexfarben ausserhalb von var()-Fallbacks.
        for treffer in re.findall(r"#[0-9a-fA-F]{3,8}\b", baustein.quelle):
            # Erlaubt nur als Fallback INNERHALB eines var()-Aufrufs.
            assert re.search(r"var\(--dk-[a-z-]+,\s*" + re.escape(treffer), baustein.quelle), (
                f"{baustein.kennung}: Farbe {treffer} steht nicht als var()-Fallback"
            )


def test_dk_tokens_werden_nur_gelesen():
    """BS-0 F5: ein Block darf ``--dk-*`` nie selbst deklarieren.

    ``--dk-x: var(--dk-x, …)`` ist nach CSS ungültig und fällt auf „unset"
    zurück (gemessener ``padding: 0``). Deklarationen sind deshalb verboten —
    nur ``var(--dk-…)``.
    """
    for baustein in bibliothek.bausteine_lesen():
        for zeile in baustein.quelle.splitlines():
            if re.match(r"^\s*--dk-[a-z-]+\s*:", zeile):
                raise AssertionError(
                    f"{baustein.kennung}: --dk-Token wird deklariert: {zeile.strip()}"
                )
        assert "var(--dk-" in baustein.quelle


def test_basisadresse_wird_absolut_erwartet():
    """Das Feld „Diakronos-Adresse" ist absolut (BS-0 F4: relativ scheitert)."""
    for baustein in bibliothek.bausteine_lesen():
        assert "nur_webadresse" in baustein.quelle
        assert "/^https?:\\/\\//i" in baustein.quelle or "^https?:" in baustein.quelle
        assert "basisadresse" in baustein.quelle


def _baustein(kennung: str) -> bibliothek.Baustein:
    return next(b for b in bibliothek.bausteine_lesen() if b.kennung == kennung)


# ── 2. ZIP-Format ───────────────────────────────────────────────────────────


def test_zip_hat_die_struktur_von_export_library():
    roh = bibliothek.build_zip(version=7, basisadresse="https://gem.example/diakronos")
    with zipfile.ZipFile(io.BytesIO(roh)) as archiv:
        namen = set(archiv.namelist())
        assert "library/groups.yaml" in namen
        for kennung in BAUSTEINE:
            for datei in ("component.svelte", "config.yaml", "fields.yaml", "content.yaml"):
                assert f"library/diakronos/{kennung}/{datei}" in namen
        gruppen = archiv.read("library/groups.yaml").decode("utf-8")
        assert "name: \"Diakronos\"" in gruppen
        assert "folder: \"diakronos\"" in gruppen
        config = archiv.read("library/diakronos/kontakt/config.yaml").decode("utf-8")
        assert "diakronos/kontakt@v7" in config


def test_zip_setzt_nur_eine_absolute_basisadresse_vor():
    """Eine unbrauchbare Adresse wird NICHT erfunden — das Feld bleibt leer."""
    for adresse in ("", "gem.example", "/diakronos", "javascript:alert(1)"):
        roh = bibliothek.build_zip(version=1, basisadresse=adresse)
        with zipfile.ZipFile(io.BytesIO(roh)) as archiv:
            inhalt = archiv.read("library/diakronos/kontakt/content.yaml").decode("utf-8")
            # Leer = YAML-null (`~`), nicht `""` — Primo nimmt `""` aus der
            # Prop-Liste heraus (siehe test_content_yaml_ist_eine_map_key_zu_vorgabe).
            assert "basisadresse: ~" in inhalt, adresse

    roh = bibliothek.build_zip(version=1, basisadresse="https://gem.example/")
    with zipfile.ZipFile(io.BytesIO(roh)) as archiv:
        inhalt = archiv.read("library/diakronos/termine-liste/content.yaml").decode("utf-8")
        assert 'basisadresse: "https://gem.example"' in inhalt  # ohne Schluss-Schrägstrich


def _yaml_parser():
    """``yaml.safe_load`` — übersprungen, wenn PyYAML fehlt (Backend-Image)."""
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load


def test_content_yaml_ist_eine_map_key_zu_vorgabe():
    """``content.yaml`` MUSS eine Map ``key: Vorgabe`` sein (BS-2e).

    Primo liest sie mit ``yaml.Unmarshal(data, &contentMap)`` in
    ``map[string]interface{}`` (``internal/import_library.go``,
    ``importLibraryBlockContent``) und schreibt sie in
    ``internal/export_library.go`` genauso. Eine Liste (``- key: …``) bricht
    den Import mit HTTP 500 ab („cannot unmarshal !!seq into
    map[string]interface{}", am Wegwerf-Primo wörtlich belegt).
    """
    pruefe_yaml = _yaml_parser()

    roh = bibliothek.build_zip(version=1, basisadresse="https://gem.example")
    with zipfile.ZipFile(io.BytesIO(roh)) as archiv:
        for kennung in BAUSTEINE:
            text = archiv.read(f"library/diakronos/{kennung}/content.yaml").decode("utf-8")
            daten = pruefe_yaml(text)
            assert isinstance(daten, dict), f"{kennung}: content.yaml ist keine Map"
            felder = json.loads(
                (QUELLE_REPO / kennung / "fields.json").read_text(encoding="utf-8")
            )
            # Jedes Feld steht drin — vollständig und in Feldreihenfolge.
            assert list(daten) == [f["name"] for f in felder], kennung
            for feld in felder:
                vorgabe = feld["default"]
                if feld["name"] == "basisadresse":
                    vorgabe = "https://gem.example"
                # Leere Vorgabe steht als `~` in der Datei und kommt als
                # `None` zurück (YAML-null) — nicht als `""`.
                soll = None if vorgabe == "" else vorgabe
                assert daten[feld["name"]] == soll, (kennung, feld["name"])
            # Leere Vorgabe = `~` (null), NICHT `""`: Primo legt für leere
            # Werte zwar einen Eintrag an, nimmt das Feld danach aber aus der
            # Prop-Liste des veröffentlichten Builds heraus — eine Vorgabe im
            # Quelltext ginge verloren (BS-2e Runde 3, am Wegwerf-Primo
            # gemessen; heute sind alle Vorgaben nicht-leer).
            ohne_null = [f["name"] for f in felder if f["default"] == ""]
            for name in ohne_null:
                assert f'"{name}": ""' not in text, (kennung, name)


def test_zip_yaml_ist_wohlgeformt():
    """Struktur (Einzug!) prüfen: PyYAML ist im Image nicht installiert,
    deshalb hier eine kleine Prüfung der kritischen Stellen statt eines
    Parsers (der Abgleich mit einem ECHTEN Primo steht in der Abnahme)."""
    roh = bibliothek.build_zip(version=1, basisadresse="")
    with zipfile.ZipFile(io.BytesIO(roh)) as archiv:
        felder = archiv.read("library/diakronos/termine-liste/fields.yaml").decode()
        # Jedes Feld beginnt mit genau zwei Leerzeichen und "- name:".
        assert re.search(r"^  - name: \"ueberschrift\"$", felder, re.M)
        assert re.search(r"^    label: \"Überschrift\"$", felder, re.M)
        # config steht unter dem Feld, die Optionen darunter.
        block = felder.split('name: "darstellung"')[1].split("- name:")[0]
        assert re.search(r"^    config:$", block, re.M)
        assert re.search(r"^      options:$", block, re.M)
        assert re.search(r'^        - value: "liste"$', block, re.M)
        # Kein Feld beginnt ohne Einzug (das wäre die Bare-Liste kaputt).
        for zeile in felder.splitlines():
            if zeile.startswith("- name:"):
                raise AssertionError(f"Feld ohne Einzug: {zeile}")


def test_blockname_traegt_die_version():
    """Primo hat keine Versionierung (BS-0 F2b): der Name ist der Zustand."""
    assert bibliothek.blockname_mit_version("kontakt", 3) == "diakronos/kontakt@v3"
    assert bibliothek.version_aus_blockname("diakronos/kontakt@v3") == ("kontakt", 3)
    assert bibliothek.version_aus_blockname("diakronos/kontakt") == ("kontakt", 0)
    assert bibliothek.version_aus_blockname("fremd/kontakt@v3") is None
    assert bibliothek.version_aus_blockname("diakronos/Kontakt!") is None


def test_kennung_wird_streng_geprueft():
    assert bibliothek.kennung_pruefen("termine-liste") == "termine-liste"
    for boese in ("../etc", "Kontakt", "a b", "", "a/b", "-x"):
        with pytest.raises(bibliothek.BausteinQuelleFehler):
            bibliothek.kennung_pruefen(boese)


# ── 3. Installer gegen eine gemockte Primo-API ──────────────────────────────


class PrimoAttrappe:
    """Minimaler Primo, der genau die benutzten Endpunkte nachbildet.

    * ``GET  /api/collections/_superusers/auth-with-password`` -> Token
    * ``GET  /api/primo/export-library``                        -> ZIP + Revision
    * ``POST /api/primo/import-library``                        -> Upsert, 428 ohne
      ``expected_revision`` (wie der echte Server), zählt Aufrufe.
    """

    def __init__(self, revision: str = "v1:abc", bloecke: list[str] | None = None):
        self.revision = revision
        self.bloecke = list(bloecke or [])
        self.imports: list[dict] = []
        self.export_aufrufe = 0
        self.erzwinge_status: int | None = None
        #: Timeouts, mit denen `_client(...)` aufgerufen wurde (BS-2d3).
        self.timeouts: list[float | None] = []
        #: Anzahl der Anmeldungen am Superuser-Endpunkt (BS-2d3: 429-Bremse).
        self.anmeldungen = 0
        #: Jedes gelieferte Token (Reihenfolge = Anmeldereihenfolge).
        self.tokens: list[str] = []
        #: Status, mit dem Export/Import antworten sollen, solange er > 0 ist
        #: (BS-2d3-Nacharbeit: 401 -> genau eine neue Anmeldung). Einmalig:
        #: danach wird zurueckgesetzt, wie es ein abgelaufenes Token tut.
        self.ablehnung_status: int = 0
        self.ablehnungen = 0
        #: Aufrufe, die mit dem jeweiligen Authorization-Kopf kamen.
        self.auth_koepfe: list[str] = []

    def zip_bauen(self) -> bytes:
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as archiv:
            archiv.writestr("library/groups.yaml", "- id: \"\"\n  name: \"Diakronos\"\n")
            for name in self.bloecke:
                kennung = name.split("/")[-1].split("@")[0]
                archiv.writestr(
                    f"library/diakronos/{kennung}/config.yaml", f'name: "{name}"\n'
                )
        return puffer.getvalue()

    def handler(self, request: httpx.Request) -> httpx.Response:
        pfad = request.url.path
        self.auth_koepfe.append(str(request.headers.get("authorization") or ""))
        if pfad.endswith("/auth-with-password"):
            self.anmeldungen += 1
            # Jedes Token ist neu — sonst liesse sich "wurde neu angemeldet"
            # nicht von "hat das alte Token weiterbenutzt" unterscheiden.
            token = f"superuser-token-{self.anmeldungen}"
            self.tokens.append(token)
            return httpx.Response(200, json={"token": token})
        if self.ablehnung_status and not pfad.endswith("/auth-with-password"):
            # Genau EINMAL: wie ein abgelaufenes Token, das nach neuer
            # Anmeldung wieder gilt.
            self.ablehnungen += 1
            self.ablehnung_status = 0
            return httpx.Response(401, json={"message": "token expired"})
        if pfad.endswith("/export-library"):
            self.export_aufrufe += 1
            return httpx.Response(
                200,
                content=self.zip_bauen(),
                headers={"X-Primo-Revision": self.revision},
            )
        if pfad.endswith("/import-library"):
            if self.erzwinge_status is not None:
                return httpx.Response(self.erzwinge_status, json={"message": "nope"})
            rumpf = request.content
            self.imports.append({"rumpf": rumpf, "kopf": dict(request.headers)})
            # Der Import legt die Blöcke an (Upsert über den Namen).
            # BS-2a2 (F4): Primo legt die Bloecke mit der Version des Aufrufs an.
            version = bibliothek.mitgelieferte_version()
            self.bloecke = sorted(set(self.bloecke) | {
                *[f"diakronos/{kennung}@v{version}" for kennung in BAUSTEINE],
            })
            self.revision = "v1:neu"
            return httpx.Response(200, json={"success": True, "summary": {"groups": 1, "blocks": 2},
                                            "revision": self.revision})
        return httpx.Response(404, json={"message": "nicht nachgebildet"})


@pytest.fixture(autouse=True)
def merker_leeren():
    """BS-2a2 (F2): jeder Test beginnt mit leerem Prozess-Merker.

    Ohne das haengt "wird nachgezogen?" davon ab, welcher Test vorher lief —
    der Merker ueberlebt innerhalb eines Prozesses.
    """
    bibliothek.merker_zuruecksetzen()
    yield
    bibliothek.merker_zuruecksetzen()


@pytest.fixture()
def primo(monkeypatch):
    """Setzt einen konfigurierten Primo + MockTransport (kein Netzzugriff)."""
    from diakronos_app.settings import settings

    attrappe = PrimoAttrappe()
    monkeypatch.setattr(settings, "primo_url", "http://primo.test:8080", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_email", "su@example.org", raising=False)
    monkeypatch.setattr(
        settings, "primo_superuser_password", "geheim-fuer-den-test", raising=False
    )
    transport = httpx.MockTransport(attrappe.handler)

    # BS-2d3: der Import-Weg ruft `_client(timeout)` mit eigenem Budget auf.
    # Die Attrappe nimmt den Wert an und protokolliert ihn, damit der Test
    # unten nachweisen kann, dass NICHT der kurze Lesetimeout benutzt wird.
    def client(timeout: float | None = None):
        attrappe.timeouts.append(timeout)
        return httpx.Client(
            transport=transport,
            timeout=timeout if timeout is not None else 5.0,
            trust_env=False,
        )

    monkeypatch.setattr(bibliothek, "_client", client)
    # BS-2d3-Nacharbeit: der Superuser-Merker steht im Adapter — also muss
    # auch der Adapter die Attrappe sehen (sonst echter Netzversuch).
    from diakronos_app.website import primo as prima_adapter

    prima_adapter._token_merker_leeren()
    monkeypatch.setattr(prima_adapter, "_client", client)
    # Ohne ``exp`` im Token gilt die Einstellung; 4 h wuerden den Merker ueber
    # den ganzen Testlauf halten. 300 s genuegt und ist der PocketBase-Default.
    monkeypatch.setattr(settings, "primo_token_sekunden", 300, raising=False)
    return attrappe


def test_installieren_spielt_das_zip_mit_revision_ein(primo):
    ergebnis = bibliothek.sync(basis="https://gem.example/diakronos")
    assert ergebnis.weg == "zip"
    assert ergebnis.version == bibliothek.mitgelieferte_version()
    assert ergebnis.bausteine == list(BAUSTEINE)
    assert len(primo.imports) == 1
    # Der Import ist multipart mit `file` (ZIP) und `expected_revision`.
    rumpf = primo.imports[0]["rumpf"]
    assert b'name="file"; filename="diakronos-bausteine.zip"' in rumpf
    assert b'name="expected_revision"' in rumpf
    assert b"v1:abc" in rumpf

    # Und das ZIP selbst ist die Bibliothek (aus dem Rumpf herausgelesen).
    ritze = rumpf.index(b"PK\x03\x04")
    zip_roh = rumpf[ritze:]
    # ... bis zum Multipart-Rand am Ende abschneiden.
    ende = zip_roh.rfind(b"PK\x05\x06")
    zip_roh = zip_roh[: ende + 22]
    with zipfile.ZipFile(io.BytesIO(zip_roh)) as archiv:
        namen = set(archiv.namelist())
        assert "library/diakronos/kontakt/component.svelte" in namen
        assert "library/diakronos/termine-liste/content.yaml" in namen
        config = archiv.read("library/diakronos/kontakt/config.yaml").decode("utf-8")
        # BS-2a2 (F4): der Blockname traegt die AUSLIEFERUNGSVERSION — nicht
        # hart "v1", sonst bricht jede Nachbesserung diesen Test.
        assert f"diakronos/kontakt@v{bibliothek.mitgelieferte_version()}" in config
        inhalt = archiv.read("library/diakronos/kontakt/content.yaml").decode("utf-8")
        assert 'basisadresse: "https://gem.example/diakronos"' in inhalt


def test_zweiter_lauf_ist_idempotent(primo):
    """Zwei Läufe hintereinander ändern nichts an der Blockliste (Upsert)."""
    bibliothek.sync(basis="https://gem.example/diakronos")
    stand_nach_eins = sorted(primo.bloecke)
    bibliothek.sync(basis="https://gem.example/diakronos")
    assert sorted(primo.bloecke) == stand_nach_eins
    assert len(primo.imports) == 2  # zwei Aufrufe, aber dieselbe Blockmenge


def test_import_wird_mit_der_export_revision_abgesichert(primo):
    """Ohne Sync-Basis antwortet der echte Primo 428 — wir holen sie vorher."""
    bibliothek.sync(basis="https://gem.example/diakronos")
    assert primo.export_aufrufe == 1
    # Die Revision steht als Formularfeld im Import-Rumpf (nicht im ZIP).
    assert b"v1:abc" in primo.imports[0]["rumpf"]



def test_ablehnung_wird_als_fehler_gemeldet(primo):
    primo.erzwinge_status = 409
    with pytest.raises(bibliothek.PrimoSyncAbgelehnt) as fehler:
        bibliothek.sync(basis="https://gem.example/diakronos")
    assert fehler.value.status == 409
    # Kein Secret und kein Token im Text.
    assert "superuser-token" not in str(fehler.value)
    assert "geheim-fuer-den-test" not in str(fehler.value)


def test_anmeldung_wird_gemerkt_statt_je_aufruf_wiederholt(primo):
    """BS-2d3: EINE Anmeldung fuer mehrere Zugriffe (PocketBase bremst 429).

    Befund aus der Browser-Abnahme: ein Stand-Lesen und der Klick
    „einspielen“ meldeten sich kurz hintereinander zweimal an; Primo
    antwortete mit 429 und die Oberflaeche meldete „die Website hat den
    Zugriff abgelehnt“, obwohl die Anbindung in Ordnung war.

    Nacharbeit (Sicherheits-Review): der Merker steht an EINER Stelle —
    ``primo.superuser_token()``. Beide Wege (Bausteine und Primo-Adapter)
    muessen deshalb dasselbe Token sehen und sich nicht doppelt anmelden.
    """
    from diakronos_app.website import primo as prima_adapter

    erst = bibliothek._superuser_token()
    zweit = prima_adapter.superuser_token()  # der Weg von login_uebergabe
    dritt = bibliothek._superuser_token()
    assert primo.anmeldungen == 1
    assert erst == zweit == dritt


def test_merker_gilt_nur_fuer_dieselbe_url_und_mail(primo, monkeypatch):
    """Review-Punkt 1: Bindung an (URL, E-Mail) — kein Token von Instanz A."""
    from diakronos_app.settings import settings
    from diakronos_app.website import primo as prima_adapter

    prima_adapter.superuser_token()
    # Andere E-Mail = anderer Zugang: es MUSS neu angemeldet werden.
    monkeypatch.setattr(settings, "primo_superuser_email", "zweiter@example.org", raising=False)
    prima_adapter.superuser_token()
    assert primo.anmeldungen == 2
    # Dieselbe E-Mail danach wieder gemerkt (kein dritter Login).
    prima_adapter.superuser_token()
    assert primo.anmeldungen == 2
    # Andere URL (Instanzwechsel) ebenso.
    monkeypatch.setattr(settings, "primo_url", "http://andere-primo.test:8080", raising=False)
    prima_adapter.superuser_token()
    assert primo.anmeldungen == 3


def test_ablehnung_401_meldet_genau_einmal_neu_an(primo):
    """Review-Punkt 2: 401 auf Export/Import -> Token verwerfen, EIN neuer Login.

    Die Attrappe antwortet genau einmal mit 401 (abgelaufenes Token) und
    danach normal. Erwartet: der Vorgang gelingt, und es gibt genau ZWEI
    Anmeldungen (die erste plus die Erneuerung) — nicht drei.
    """
    from diakronos_app.website import primo as prima_adapter

    prima_adapter.superuser_token()  # Ausgangslage: ein gemerktes Token
    assert primo.anmeldungen == 1

    primo.ablehnung_status = 401
    stand = bibliothek.bibliothek_stand()
    assert stand.erreichbar is True, stand.als_dict()
    assert primo.ablehnungen == 1
    assert primo.anmeldungen == 2
    # Der zweite Export lief mit dem FRISCHEN Token.
    assert primo.auth_koepfe[-1] == "superuser-token-2"


def test_zweites_401_geht_durch_ohne_weitere_anmeldung(primo, monkeypatch):
    """Review-Punkt 2: nur EINE Wiederholung — sonst waere ein 401 eine Schleife."""
    from diakronos_app.website import primo as prima_adapter

    prima_adapter.superuser_token()
    aufrufe = {"n": 0}

    def immer_401(_token):
        aufrufe["n"] += 1
        raise bibliothek.PrimoSyncAbgelehnt(401, "abgelaufen")

    monkeypatch.setattr(bibliothek, "revision_holen", immer_401)
    with pytest.raises(bibliothek.PrimoSyncAbgelehnt) as fehler:
        bibliothek._sync_echt(basis="https://gem.example/diakronos")
    assert fehler.value.status == 401
    # Erster Aufruf + genau eine Wiederholung, danach durchgereicht.
    assert aufrufe["n"] == 2
    assert primo.anmeldungen == 2


def test_merker_faellt_nach_jwt_exp_ab(primo, monkeypatch):
    """Review-Punkt 3: Merkdauer kommt aus ``exp`` des Tokens, nicht aus 4 h.

    ``exp`` steht im JWT-Rumpf (base64, ohne Signaturpruefung). Der Merker
    laeuft auf der monotonen Uhr; wird sie vorgestellt, faellt er ab.
    """
    import base64
    import json as _json
    import time as _time

    from diakronos_app.website import primo as prima_adapter

    exp = _time.time() + 3600
    rumpf = base64.urlsafe_b64encode(
        _json.dumps({"exp": int(exp)}).encode()
    ).decode().rstrip("=")
    token = f"kopf.{rumpf}.sig"
    anmeldungen = {"n": 0}

    gueltig = prima_adapter._gueltigkeit_sekunden(token)

    def anmelden():
        anmeldungen["n"] += 1
        return token, gueltig

    monkeypatch.setattr(prima_adapter, "_anmelden", anmelden)
    jetzt = _time.monotonic()
    # Der Merker laeuft auf der monotonen Uhr — Bezugspunkt ist ``jetzt``.
    monkeypatch.setattr(_time, "monotonic", lambda: jetzt)
    assert prima_adapter.superuser_token() == token
    # Innerhalb der Merkdauer: gemerkt, keine Anmeldung.
    monkeypatch.setattr(_time, "monotonic", lambda: jetzt + 200)
    assert prima_adapter.superuser_token() == token
    assert anmeldungen["n"] == 1, f"gilt noch 300 s, nach 200 s keine Anmeldung: {anmeldungen}"
    # Später als die Merkdauer (min(exp-60, PRIMO_TOKEN_SEKUNDEN)=300 s):
    # genau eine neue Anmeldung.
    monkeypatch.setattr(_time, "monotonic", lambda: jetzt + 400)
    assert prima_adapter.superuser_token() == token
    assert anmeldungen["n"] == 2


def test_import_timeout_ist_einstellbar_und_hat_untergrenze(primo, monkeypatch):
    """Review-Punkt 4: Schreib-Budget ~30 s, per Einstellung erhoehbar."""
    from diakronos_app.settings import settings

    assert bibliothek.import_timeout_sekunden() >= 30.0
    monkeypatch.setattr(settings, "bausteine_import_timeout_sekunden", 90.0, raising=False)
    assert bibliothek.import_timeout_sekunden() == 90.0
    # Unsinnige kleine Werte werden angehoben, nie durchgereicht.
    monkeypatch.setattr(settings, "bausteine_import_timeout_sekunden", 1.0, raising=False)
    assert bibliothek.import_timeout_sekunden() >= 30.0


def test_anfrage_grenze_folgt_dem_schreib_budget(monkeypatch):
    """Review-Punkt 4: die Anfrage-Grenze ist NICHT ``primo_timeout*4+5`` (25 s).

    Vorher kappte ``_im_thread`` bei 25 s, waehrend das Schreib-Budget des
    Imports schon 30 s betraegt — die Anfrage waere abgebrochen, obwohl der
    Import noch lief. Nach Ablauf darf die Anfrage auch nicht auf den Thread
    warten (Pool-Abbau ohne Warten).
    """
    import threading
    import time as _time

    from diakronos_app.api import website as api_website
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "primo_timeout_sekunden", 5.0, raising=False)
    monkeypatch.setattr(settings, "bausteine_import_timeout_sekunden", 0.0, raising=False)

    # Die Grenze der Installations-Anfrage: aus dem Schreib-Budget abgeleitet.
    grenze = (
        bibliothek.import_timeout_sekunden()
        + 2.0 * float(settings.primo_timeout_sekunden)
        + 5.0
    )
    assert grenze > 25.0
    assert grenze >= bibliothek.import_timeout_sekunden()

    # Kurzes Limit: die Anfrage bricht ab, ohne auf den Thread zu warten.
    laeuft = threading.Event()
    fertig = threading.Event()

    def langsam():
        laeuft.set()
        _time.sleep(1.5)
        fertig.set()

    start = _time.monotonic()
    with pytest.raises(TimeoutError):
        api_website._im_thread(langsam, limit=0.2)
    gedauert = _time.monotonic() - start
    assert laeuft.is_set()
    # Rueckkehr deutlich vor dem Ende des Aufrufs.
    assert gedauert < 1.0, gedauert
    assert fertig.wait(3.0)  # der Thread laeuft zu Ende


def test_token_erscheint_nicht_in_fehlertext_oder_log(primo, caplog, monkeypatch):
    """Review-Punkt 5: das Superuser-Token leakt nicht (Text, Grund, Log)."""
    from diakronos_app.website import primo as prima_adapter

    token = prima_adapter.superuser_token()
    assert token

    def zwei_401(_token):
        raise bibliothek.PrimoSyncAbgelehnt(401, "abgelaufen")

    caplog.set_level(10)
    monkeypatch.setattr(bibliothek, "revision_holen", zwei_401)
    with pytest.raises(bibliothek.PrimoSyncAbgelehnt) as fehler:
        bibliothek._sync_echt(basis="https://gem.example/diakronos")
    assert token not in str(fehler.value)
    assert token not in (fehler.value.grund or "")
    for satz in caplog.records:
        assert token not in satz.getMessage()


# Wiederhergestellt bei der Integration (Review 09.11.: ersatzlos gelöscht in 2379c1d3)

def test_rueckfall_auf_einzelweg_ohne_import_endpunkt(primo, monkeypatch):
    """Kennt Primo den Import-Endpunkt nicht (404), wird einzeln geschrieben.

    Geprüft wird der AUFRUF (Gruppe + Block + Feld + Eintrag), nicht die
    Primo-Datenbank — der echte Weg steht in der Abnahme.
    """
    primo.erzwinge_status = 404
    aufrufe: list[str] = []

    class EinzelAttrappe:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            aufrufe.append("GET " + url)
            return httpx.Response(200, json={"items": []})

        def post(self, url, **kwargs):
            aufrufe.append("POST " + url)
            if url.endswith("/auth-with-password"):
                return httpx.Response(200, json={"token": "superuser-token"})
            if url.endswith("/library_symbol_groups/records"):
                return httpx.Response(200, json={"id": "gruppe1"})
            if url.endswith("/library_symbols/records"):
                return httpx.Response(200, json={"id": "symbol1"})
            if url.endswith("/library_symbol_fields/records"):
                return httpx.Response(200, json={"id": "feld1"})
            if url.endswith("/library_symbol_entries/records"):
                return httpx.Response(200, json={"id": "eintrag1"})
            return httpx.Response(404, json={"message": "?"})

    monkeypatch.setattr(bibliothek, "_client", EinzelAttrappe)
    ergebnis = bibliothek.sync(basis="https://gem.example/diakronos")
    assert ergebnis.weg == "einzeln"
    assert any("library_symbol_groups/records" in a for a in aufrufe)
    assert any("library_symbols/records" in a for a in aufrufe)
    assert any("library_symbol_fields/records" in a for a in aufrufe)
    assert any("library_symbol_entries/records" in a for a in aufrufe)
    # Die Vorgabe der Basisadresse steht im Eintrag (B2).
    assert ergebnis.bausteine == list(BAUSTEINE)


def test_stand_liest_versionen_aus_der_bibliothek(primo):
    """``bibliothek_stand`` meldet „veraltet", solange nichts installiert ist."""
    stand = bibliothek.bibliothek_stand()
    assert stand.erreichbar is True
    assert stand.mitgeliefert == bibliothek.mitgelieferte_version()
    assert stand.installiert == 0
    assert stand.veraltet is True

    bibliothek.sync(basis="https://gem.example/diakronos")
    # BS-2a2 (F4): die installierte Version ist die AUSLIEFERUNGSVERSION —
    # nicht mehr hart 1 (jede Nachbesserung erhoeht sie).
    assert bibliothek.mitgelieferte_version() >= 2
    stand = bibliothek.bibliothek_stand()
    assert stand.installiert == bibliothek.mitgelieferte_version()
    assert stand.veraltet is False
    assert {e["kennung"] for e in stand.bausteine} == set(BAUSTEINE)


def test_stand_wirft_nie(monkeypatch):
    """Nicht erreichbares Primo ist ein Zustand, keine Ausnahme."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "primo_url", "http://primo.test:8080", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_email", "su@example.org", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_password", "x", raising=False)

    def platzt(*args, **kwargs):
        raise httpx.ConnectError("kaputt")

    class Kaputt:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return platzt()

        def post(self, *a, **k):
            return platzt()

    monkeypatch.setattr(bibliothek, "_client", Kaputt)
    stand = bibliothek.bibliothek_stand()
    assert stand.erreichbar is False
    assert stand.hinweis
    assert stand.mitgeliefert == bibliothek.mitgelieferte_version()


def test_nachziehen_stoert_den_login_nicht(monkeypatch):
    """B2: ein Fehler beim Nachziehen wird geschluckt und protokolliert."""
    from diakronos_app.api import website as api_website

    aufgerufen = {"sync": 0}

    class Veraltet:
        erreichbar = True
        installiert = 0
        mitgeliefert = 9
        veraltet = True

    class Boese:
        @staticmethod
        def bibliothek_stand():
            return Veraltet()

        @staticmethod
        def sync(**kwargs):
            aufgerufen["sync"] += 1
            raise RuntimeError("Primo kaputt")

    monkeypatch.setattr(
        "diakronos_app.website.bausteine.bibliothek_stand", Boese.bibliothek_stand
    )
    monkeypatch.setattr("diakronos_app.website.bausteine.sync", Boese.sync)

    # Darf NICHT werfen.
    api_website._bausteine_nachziehen()
    assert aufgerufen["sync"] == 1


def test_nachziehen_schreibt_nur_wenn_veraltet(monkeypatch):
    from diakronos_app.api import website as api_website

    aufgerufen = {"sync": 0}

    class Aktuell:
        erreichbar = True
        installiert = 2
        mitgeliefert = 2
        veraltet = False

    def zaehle(**kwargs):
        aufgerufen["sync"] += 1

    monkeypatch.setattr(
        "diakronos_app.website.bausteine.bibliothek_stand", lambda: Aktuell()
    )
    monkeypatch.setattr("diakronos_app.website.bausteine.sync", zaehle)
    api_website._bausteine_nachziehen()
    assert aufgerufen["sync"] == 0


def test_login_uebergabe_ruft_das_nachziehen_nach_der_url(monkeypatch):
    """Die Reihenfolge steht im Quelltext: erst die URL, dann das Nachziehen.

    Ein Fehler VOR der URL würde die Anmeldung kippen — nach der URL nicht
    mehr. Der Test hält die Reihenfolge fest, damit sie nicht „aufgeräumt"
    wird.
    """
    quelle = (REPO / "backend" / "src" / "diakronos_app" / "api" / "website.py").read_text(
        encoding="utf-8"
    )
    abschnitt = quelle.split("def login_uebergabe")[1].split("\ndef ")[0]
    # B2: das Nachziehen haengt als Hintergrundaufgabe AN der Antwort
    # (`_mit_nachziehen` -> BackgroundTask) — es laeuft also NACH dem Senden.
    assert "_mit_nachziehen(" in abschnitt, "Nachziehen fehlt"
    assert 'return {"url": url}' not in abschnitt, "antwortet noch ohne Hintergrundaufgabe"
    helfer = quelle.split("def _mit_nachziehen")[1]
    assert "BackgroundTask(_bausteine_nachziehen)" in helfer


def test_status_ist_lesend_und_installieren_ist_post():
    from diakronos_app.frappe_compat.registry import options_for

    from diakronos_app.api import website as api_website

    status_optionen = options_for(api_website.bausteine_status) or {}
    assert status_optionen.get("allow_guest") is False
    assert status_optionen.get("methods") in (None, ["GET"], "GET")

    install_optionen = options_for(api_website.bausteine_installieren) or {}
    assert install_optionen.get("allow_guest") is False
    assert list(install_optionen.get("methods") or []) == ["POST"]


def test_installieren_ist_im_inventar_schreibend():
    """Das Inventar (tools/whitelist_inventar.py) muss den Endpunkt als
    schreibend führen — er legt Datensätze in einem Fremdsystem an."""
    inventar = json.loads(
        (REPO / "backend" / "src" / "diakronos_app" / "frappe_compat" / "inventar"
         / "whitelist.json").read_text(encoding="utf-8")
    )
    eintraege = inventar.get("eintraege") or []
    treffer = [e for e in eintraege if e.get("name") == "bausteine_installieren"]
    assert treffer, (
        "bausteine_installieren fehlt im Inventar — `tools/whitelist_inventar.py` "
        "neu laufen lassen"
    )
    assert any(e.get("einstufung") == "schreibend" for e in treffer), treffer


ECHTER_PRIMO = os.environ.get("BS2A_PROMO_URL", "").strip()


@pytest.mark.skipif(
    not ECHTER_PRIMO,
    reason="Abnahme gegen einen echten Wegwerf-Primo: BS2A_PROMO_URL setzen",
)
def test_echter_primo_nimmt_die_bibliothek_an():  # pragma: no cover — Abnahme
    """Installieren, zweimal (idempotent), Stand lesen — gegen echtes Primo.

    Läuft nur in der Abnahme (eigener Wegwerf-Stack, eigenes Netz). Der
    normale Testlauf ist ``--network none`` und überspringt diesen Test.
    """
    from diakronos_app.settings import settings

    settings.primo_url = ECHTER_PRIMO
    settings.primo_superuser_email = os.environ["BS2A_PROMO_EMAIL"]
    settings.primo_superuser_password = os.environ["BS2A_PROMO_PASSWORT"]

    erst = bibliothek.sync(basis="https://gem.example/diakronos")
    assert erst.weg == "zip", erst
    zweit = bibliothek.sync(basis="https://gem.example/diakronos")
    assert sorted(zweit.bausteine) == sorted(erst.bausteine)

    stand = bibliothek.bibliothek_stand()
    assert stand.erreichbar is True
    assert stand.installiert == bibliothek.mitgelieferte_version()
    assert stand.veraltet is False
    assert {e["kennung"] for e in stand.bausteine} == set(BAUSTEINE)

