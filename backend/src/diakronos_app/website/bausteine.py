"""BS-2a — Baustein-Bibliothek: Quellen, ZIP-Bau und Auslieferung an Primo.

Was dieses Modul tut
====================
Diakronos liefert eine kleine Bibliothek fertiger Website-Bausteine mit, die in
der angebundenen Primo-Instanz als Bibliotheksblöcke erscheinen (Gruppe
``Diakronos``, Blockname ``diakronos/<kennung>``). Die Quellen liegen IM
Python-Paket (``diakronos_app/website/bausteine/quellen/``) und werden über
:mod:`importlib.resources` gelesen — nie über Pfade relativ zum Repo und nie
über absolute Host-Pfade (NACHTRAG DOCKER Punkt 1; dasselbe Muster wie
``planrahmen/ressourcen.py``). Die Dateien im Repo unter
``deploy/primo/bausteine/`` sind die QUELLE, aus der das Paket gefüllt wird
(``tools/bausteine_sync.py``); maßgeblich zur Laufzeit ist der Paketpfad.

Auslieferungsweg (BS-0, „Empfohlene Auslieferungsstrategie" — verbindlich)
--------------------------------------------------------------------------
1. **ZIP, nicht Einzelaufruf.** Die Bausteine werden als ZIP in der
   ``library/``-Struktur gebaut und über ``POST /api/primo/import-library``
   mit ``expected_revision`` eingespielt (ein Vorgang, serverseitig atomar,
   Revision eingebaut). Der Einzelweg (PocketBase-REST) bleibt Rückfallebene
   für den Fall, dass Primo den Import-Endpunkt nicht kennt.
2. **Version je Baustein in Diakronos.** Primo hat keine Versionierung
   (BS-0 F2b): die Version steht deshalb in ``VERSION`` (Auslieferung) und der
   SHA-256 je Block wird hier über die Quellen gebildet. Primo bekommt die
   Version im Blocknamen mit — nicht als Schmuck, sondern damit die
   installierte Fassung am Namen ablesbar ist, ohne dass Diakronos eine
   Zuordnungstabelle führen muss.
3. **Eingesetzte Site-Kopien werden NICHT automatisch nachgezogen.** Primo
   kopiert einen Bibliotheksblock beim Einsetzen; die Kopie gehört danach dem
   Redakteur. Automatisch würde Diakronos jede Anpassung überschreiben
   (BS-0 F2c). Das Nachziehen ist eine eigene, ausgelöste Aktion — die gibt es
   in BS-2a noch nicht (eigene Karte), sie wird hier auch nicht angedeutet.

Zustand ohne eigene Tabelle
---------------------------
Der Installer schreibt keinen Zustand in die Diakronos-Datenbank: was
installiert ist, steht IN Primo (Blockname samt Version, Revisionskopf der
Import-Antwort). Damit kann der Stand nicht auseinanderlaufen, und eine
Migration ist für BS-2a nicht nötig.

Secrets
-------
Das Superuser-Token wird nur im Aufruf benutzt, nie protokolliert und nie in
einer Antwort ausgegeben. Fehlermeldungen nennen höchstens Statuscode und
einen Kurzgrund (``website/primo.py::_fehlertext``).

Freigaben je Baustein (BS-2d1)
------------------------------
Welche Freigabe-Gruppen ein Baustein liest (G1: „Daten nur, wo es auch gewollt
ist"), steht als ``"freigaben": [...]`` in seiner ``block.json`` — bei der
Quelle, nicht in der Oberfläche. Die Namen sind die WIRKLICH angesprochenen
Endpunkte:

  ``termine``          → ``website.oeffentlich.termine`` /
                         ``naechster_termin`` (gesperrt über die Kalender- und
                         Kategorie-Freigabe, BS-1b/BS-1c)
  ``kalender``         → ``website.oeffentlich.kalender`` (Auswahl + Abo)
  ``gruppen``          → ``website.oeffentlich.gruppen`` / ``gruppe``
  ``beitraege``        → ``website.oeffentlich.beitraege``
  ``kontaktpostfaecher`` → ``website.oeffentlich.postfaecher`` +
                         ``website.kontakt_senden``

Eine leere Liste heißt: der Baustein fragt KEINE Freigabe-Daten ab. :data:`FREIGABEN` ist die Positivliste der bekannten Namen — ein
Tippfehler in ``block.json`` bricht das Lesen, statt still eine unbekannte
Freigabe auszuliefern. ``bausteine_status`` liefert die Liste je Baustein mit
(``mitgeliefert[].freigaben``); die Oberfläche zeigt sie an, statt sie zu
erfinden (BS-2d Nacharbeit Punkt 3).

"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Iterable

import httpx

from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.website.bausteine")

__all__ = [
    "GRUPPE_NAME",
    "GRUPPE_ORDNER",
    "Baustein",
    "Installationsergebnis",
    "Stand",
    "basisadresse",
    "bibliothek_stand",
    "build_zip",
    "bausteine_lesen",
    "freigaben_lesen",
    "kennung_pruefen",
    "mitgelieferte_version",
    "primo_blockname",
    "revision_holen",
    "sync",
    "version_aus_blockname",
]

#: Anzeigename der Bibliotheksgruppe in Primo und ihr Ordnername im ZIP.
GRUPPE_NAME = "Diakronos"
GRUPPE_ORDNER = "diakronos"
#: Präfix im Blocknamen: ``diakronos/kontakt``.
NAMENS_PRAEFIX = "diakronos/"

#: Erlaubte Kennungen (auch: Verzeichnisnamen im ZIP). Bewusst eng: der Name
#: landet in einem Dateipfad und in einem Primo-Datensatz.
KENNUNG_MUSTER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: Versionsmuster im Blocknamen: ``diakronos/kontakt@v1``.
VERSION_MUSTER = re.compile(r"^(?P<kennung>[a-z0-9-]+)@v(?P<version>\d+)$")

#: Feldname, den der Installer mit der öffentlichen Diakronos-Basis vorbelegt.
FELD_BASISADRESSE = "basisadresse"

#: Grenzen für Antworten von Primo (Bibliotheks-Export ist ein ZIP, kein
#: Grossdokument; ein Revisionskopf ist kurz).
MAX_KOPF_BYTES = 4096

#: Schreibe-Timeout für ``POST /api/primo/import-library`` in Sekunden.
#:
#: ``PRIMO_TIMEOUT_SEKUNDEN`` (Default 5) ist ein LESETIMEOUT für kleine
#: Abfragen wie ``/api/primo/info``. Der Bibliotheks-Import schreibt dagegen
#: die ganze Bibliothek und braucht dafuer deutlich laenger: im Wegwerf-Stack
#: (BS-2d3) rund 5,2 s fuer zehn Bausteine — knapp am alten Timeout und unter
#: Docker-Last darueber. Folge im Betrieb: der Client bricht mit Status 0 ab,
#: waehrend Primo den Import fertig schreibt; die Oberflaeche meldet einen
#: Fehler, obwohl die Bausteine angekommen sind (Befund BS-2d3).
#: Der Schreibweg bekommt deshalb ein eigenes, groesseres Budget. Der Wert ist
#: die Vorgabe; ``import_timeout_sekunden()`` liest ihn aus den Einstellungen
#: (``BAUSTEINE_IMPORT_TIMEOUT_SEKUNDEN``), damit ein langsamer Betrieb ihn
#: ohne Codeaenderung anheben kann.
IMPORT_TIMEOUT_SEKUNDEN = 30.0

#: Untergrenze des Schreib-Budgets: darunter reicht die Zeit fuer eine
#: Bibliothek mit zehn Bausteinen auch im Normalfall nicht.
IMPORT_TIMEOUT_MINIMUM = 30.0


def import_timeout_sekunden() -> float:
    """Budget fuer den SCHREIBENDEN Bibliotheks-Import (Sekunden).

    Reihenfolge: Einstellung ``BAUSTEINE_IMPORT_TIMEOUT_SEKUNDEN`` (wenn
    gesetzt und > 0), sonst :data:`IMPORT_TIMEOUT_SEKUNDEN`. Nie unter
    :data:`IMPORT_TIMEOUT_MINIMUM` und nie unter ``2 * PRIMO_TIMEOUT_SEKUNDEN``
    -- sonst waere das Schreibbudget kleiner als zwei einfache Abfragen und
    der Import braeche wieder ab, waehrend Primo noch schreibt.
    """
    eingestellt = float(getattr(settings, "bausteine_import_timeout_sekunden", 0.0) or 0.0)
    wert = eingestellt if eingestellt > 0 else IMPORT_TIMEOUT_SEKUNDEN
    return max(wert, IMPORT_TIMEOUT_MINIMUM, 2.0 * float(settings.primo_timeout_sekunden or 5.0))

#: BS-2d3-Nacharbeit: der Superuser-Token-Merker lebt seit dem Sicherheits-
#: Review an EINER Stelle im Adapter -- `primo.superuser_token()`. Hier gibt es
#: bewusst keinen zweiten Merker mehr (sonst zwei Anmeldungen -> 429).


class BausteinFehler(Exception):
    """Basisfehler dieses Moduls — nie mit Secret- oder Inhalts-Echo."""


class BausteinQuelleFehler(BausteinFehler):
    """Die mitgelieferten Quellen sind unvollständig oder unbrauchbar.

    Das ist ein Fehler der AUSLIEFERUNG (Build), nicht der Installation: der
    Test ``tests/test_bs2a_bausteine.py`` hält das im Image fest.
    """


class PrimoSyncAbgelehnt(BausteinFehler):
    """Primo hat den Import abgelehnt (Status + Kurzgrund, ohne Interna)."""

    def __init__(self, status: int, grund: str):
        super().__init__(f"Primo antwortete {status}: {grund}")
        self.status = status
        self.grund = grund


# ── Quellen lesen (importlib.resources) ─────────────────────────────────────


def _wurzel() -> Any:
    """Das Ressourcenverzeichnis der Bausteine im Paket."""
    import diakronos_app.website

    return resources.files(diakronos_app.website) / "bausteine" / "quellen"


def _text(pfad: Any) -> str:
    return pfad.read_text(encoding="utf-8")


def kennung_pruefen(wert: object) -> str:
    """Kennung normalisieren; unbrauchbare Kennungen sind ein Quellenfehler."""
    text = str(wert or "").strip()
    if not KENNUNG_MUSTER.match(text):
        raise BausteinQuelleFehler(f"Ungültige Baustein-Kennung: {text!r}")
    return text


def mitgelieferte_version() -> int:
    """Versionsnummer der AUSLIEFERUNG (Inhalt von ``VERSION``).

    Eine ganze Zahl ≥ 1. Sie zählt die Auslieferung, nicht die einzelnen
    Bausteine: „installiert < mitgeliefert" ist die einzige Frage, die der
    Login-Übergang beantworten muss.
    """
    try:
        roh = _text(_wurzel() / "VERSION").strip()
    except (FileNotFoundError, OSError, ModuleNotFoundError) as exc:
        raise BausteinQuelleFehler("Die Bausteine sind im Paket nicht vorhanden.") from exc
    try:
        wert = int(roh)
    except ValueError as exc:
        raise BausteinQuelleFehler("Die Versionsdatei der Bausteine ist unbrauchbar.") from exc
    if wert < 1:
        raise BausteinQuelleFehler("Die Version der Bausteine muss mindestens 1 sein.")
    return wert


#: Positivliste der Freigabe-Gruppen, auf denen ein Baustein aufsetzen darf
#: (BS-2d1). Je Name: was er öffentlich sichtbar macht.
FREIGABE_TERMINE = "termine"
FREIGABE_KALENDER = "kalender"
FREIGABE_GRUPPEN = "gruppen"
FREIGABE_BEITRAEGE = "beitraege"
FREIGABE_KONTAKTPOSTFAECHER = "kontaktpostfaecher"

FREIGABEN: tuple[str, ...] = (
    FREIGABE_TERMINE,
    FREIGABE_KALENDER,
    FREIGABE_GRUPPEN,
    FREIGABE_BEITRAEGE,
    FREIGABE_KONTAKTPOSTFAECHER,
)

#: Schlüssel in ``block.json``, der die Freigaben eines Bausteins trägt.
FELD_FREIGABEN = "freigaben"


def freigaben_lesen(daten: Any, kennung: str) -> tuple[str, ...]:
    """Die ``freigaben`` aus einer ``block.json`` prüfen.

    Der Schlüssel ist PFLICHT (auch wenn die Liste leer ist) — sonst wäre
    „hat keine Freigaben" nicht von „niemand hat es hingeschrieben" zu
    unterscheiden. Jeder Name muss in :data:`FREIGABEN` stehen und darf nur
    einmal vorkommen; ein Tippfehler bricht die Auslieferung, statt still
    eine Freigabe zu verschweigen.
    """
    if not isinstance(daten, dict):
        raise BausteinQuelleFehler(f"{kennung}: block.json ist kein Objekt.")
    if FELD_FREIGABEN not in daten:
        raise BausteinQuelleFehler(f"{kennung}: block.json nennt keine freigaben.")
    roh = daten[FELD_FREIGABEN]
    if not isinstance(roh, list):
        raise BausteinQuelleFehler(f"{kennung}: freigaben ist keine Liste.")
    ergebnis: list[str] = []
    for wert in roh:
        name = str(wert or "").strip()
        if name not in FREIGABEN:
            raise BausteinQuelleFehler(
                f"{kennung}: unbekannte Freigabe {name!r} "
                f"(erlaubt: {', '.join(FREIGABEN)})."
            )
        if name in ergebnis:
            raise BausteinQuelleFehler(f"{kennung}: Freigabe {name} doppelt.")
        ergebnis.append(name)
    return tuple(ergebnis)


@dataclass(frozen=True)
class Baustein:
    """Ein mitgelieferter Baustein, vollständig aus den Quellen gelesen."""

    kennung: str
    name: str
    index: int
    beschreibung: str
    quelle: str
    felder: tuple[dict[str, Any], ...]
    sha256: str
    freigaben: tuple[str, ...] = ()

    @property
    def blockname(self) -> str:
        """Name des Blocks in Primo — ohne Version (die setzt der Aufrufer)."""
        return primo_blockname(self.kennung)

    def als_dict(self) -> dict[str, Any]:
        return {
            "kennung": self.kennung,
            "name": self.name,
            "beschreibung": self.beschreibung,
            "freigaben": list(self.freigaben),
            "sha256": self.sha256,
            "felder": [str(f.get("name")) for f in self.felder],
        }


def _feldliste(daten: Any, kennung: str) -> tuple[dict[str, Any], ...]:
    """Felddefinitionen prüfen (Name, Typ, Vorgabewert als Eintrag)."""
    if not isinstance(daten, list) or not daten:
        raise BausteinQuelleFehler(f"{kennung}: fields.json ist keine Liste.")
    felder: list[dict[str, Any]] = []
    gesehen: set[str] = set()
    for eintrag in daten:
        if not isinstance(eintrag, dict):
            raise BausteinQuelleFehler(f"{kennung}: Feld ist kein Objekt.")
        feld_name = str(eintrag.get("name") or "").strip()
        if not re.match(r"^[a-z][a-z0-9_]*$", feld_name):
            raise BausteinQuelleFehler(f"{kennung}: unbrauchbarer Feldname {feld_name!r}.")
        if feld_name in gesehen:
            raise BausteinQuelleFehler(f"{kennung}: Feldname doppelt ({feld_name}).")
        gesehen.add(feld_name)
        feld_typ = str(eintrag.get("type") or "").strip()
        if feld_typ not in FELD_TYPEN:
            raise BausteinQuelleFehler(
                f"{kennung}: Feld {feld_name} hat den unbekannten Typ {feld_typ!r}."
            )
        if "default" not in eintrag:
            # Primo legt Vorgaben NICHT am Feld ab, sondern als Eintrag
            # (content.yaml, BS-0 F3). Ein Feld ohne Vorgabe wäre im Editor
            # leer — das ist erlaubt, aber dann muss es ausdrücklich `null`
            # sein.
            raise BausteinQuelleFehler(f"{kennung}: Feld {feld_name} ohne Vorgabewert.")
        felder.append(dict(eintrag))
    return tuple(felder)


#: Feldtypen aus Primo v3.3.1 (BS-0 F3). Bewusst als Positivliste: ein Tippfehler
#: im Feldschema soll den Build brechen, nicht still ein Textfeld erzeugen.
FELD_TYPEN = frozenset(
    {
        "text",
        "rich-text",
        "markdown",
        "number",
        "date",
        "select",
        "switch",
        "slider",
        "image",
        "icon",
        "link",
        "url",
        "site-field",
        "page-field",
        "page",
        "page-list",
        "repeater",
        "group",
        "info",
    }
)


def bausteine_lesen() -> tuple[Baustein, ...]:
    """Alle mitgelieferten Bausteine (nach ``index``, dann Kennung sortiert)."""
    wurzel = _wurzel()
    gelesen: list[Baustein] = []
    try:
        eintraege = sorted(entry.name for entry in wurzel.iterdir() if entry.is_dir())
    except (FileNotFoundError, OSError, ModuleNotFoundError) as exc:
        raise BausteinQuelleFehler("Die Bausteine sind im Paket nicht vorhanden.") from exc

    for kennung in eintraege:
        if kennung.startswith("_") or kennung.startswith("."):
            continue
        kennung = kennung_pruefen(kennung)
        ordner = wurzel / kennung
        try:
            block = json.loads(_text(ordner / "block.json"))
            quelle = _text(ordner / "component.svelte")
            felder = _feldliste(json.loads(_text(ordner / "fields.json")), kennung)
        except FileNotFoundError as exc:
            raise BausteinQuelleFehler(
                f"{kennung}: block.json, component.svelte oder fields.json fehlt."
            ) from exc
        except ValueError as exc:
            raise BausteinQuelleFehler(f"{kennung}: eine Datei ist kein gültiges JSON.") from exc
        if not isinstance(block, dict):
            raise BausteinQuelleFehler(f"{kennung}: block.json ist kein Objekt.")
        if not quelle.strip():
            raise BausteinQuelleFehler(f"{kennung}: component.svelte ist leer.")
        # Prop-Vertrag: jede Feldkennung MUSS im Skriptteil vorkommen, sonst
        # zeigt der Editor ein Feld, das der Code nicht liest (die Vorgabewerte
        # kommen als Props).
        for feld in felder:
            if str(feld["name"]) not in quelle:
                raise BausteinQuelleFehler(
                    f"{kennung}: Feld {feld['name']} kommt im Baustein nicht vor."
                )
        gelesen.append(
            Baustein(
                kennung=kennung,
                name=str(block.get("name") or kennung),
                index=int(block.get("index") or 0),
                beschreibung=str(block.get("beschreibung") or ""),
                quelle=quelle,
                felder=felder,
                # Freigaben: welche öffentlichen Daten der Baustein liest
                # (BS-2d1). Bewusst NICHT im sha256 — die Summe deckt Code
                # und Feldschema (was in Primo ankommt); die Freigaben sind
                # eine Angabe über die Datenquelle für die Oberfläche und
                # ändern den Baustein selbst nicht.
                freigaben=freigaben_lesen(block, kennung),
                # Der Hash deckt Code UND Feldschema ab: eine Feldänderung ist
                # für eingesetzte Kopien genauso eine Änderung wie ein Codefix.
                sha256=hashlib.sha256(
                    (quelle + "\n#felder\n" + json.dumps(felder, ensure_ascii=False, sort_keys=True))
                    .encode("utf-8")
                ).hexdigest(),
            )
        )

    if not gelesen:
        raise BausteinQuelleFehler("Es sind keine Bausteine mitgeliefert.")
    return tuple(sorted(gelesen, key=lambda b: (b.index, b.kennung)))


# ── ZIP im Primo-Format ─────────────────────────────────────────────────────


def primo_blockname(kennung: str) -> str:
    """Blockname in Primo: ``diakronos/<kennung>``."""
    return NAMENS_PRAEFIX + kennung_pruefen(kennung)


def blockname_mit_version(kennung: str, version: int) -> str:
    """Blockname samt Versionsvermerk: ``diakronos/kontakt@v1``.

    Primo hat kein Versionsfeld (BS-0 F2b), und Diakronos will keine eigene
    Zuordnungstabelle führen. Der Vermerk im Namen ist der Zustand selbst: aus
    der Bibliothek gelesen, ohne Zusatzwissen ablesbar.
    """
    return f"{NAMENS_PRAEFIX}{kennung_pruefen(kennung)}@v{int(version)}"


def version_aus_blockname(name: str) -> tuple[str, int] | None:
    """``("kontakt", 3)`` aus ``diakronos/kontakt@v3`` — sonst ``None``.

    Bausteine ohne Versionsvermerk (ältere Auslieferung, von Hand im Editor
    angelegt) gelten als Version 0.
    """
    text = str(name or "").strip()
    if not text.startswith(NAMENS_PRAEFIX):
        return None
    rest = text[len(NAMENS_PRAEFIX):]
    treffer = VERSION_MUSTER.match(rest)
    if treffer is None:
        if KENNUNG_MUSTER.match(rest):
            return rest, 0
        return None
    return treffer.group("kennung"), int(treffer.group("version"))


def _yaml_wert(wert: Any) -> str:
    """Skalar für YAML ausgeben (JSON-Kommaschreibweise ist gültiges YAML)."""
    # json.dumps liefert für str/bool/int/float gültige YAML-Skalare; für
    # mehrzeilige Texte ist die Blockform nötig, sonst bricht YAML am
    # Zeilenumbruch.
    if wert is None:
        # `null` statt `""`: Primo legt für leere Werte gar keinen Eintrag an
        # (siehe ``_content_yaml``).
        return "~"
    if isinstance(wert, str) and ("\n" in wert or "\r" in wert):
        return "|\n" + "\n".join("  " + zeile for zeile in wert.splitlines())
    return json.dumps(wert, ensure_ascii=False)


def _yaml_liste(daten: dict[str, Any], *, tiefe: int = 0) -> list[str]:
    """Einfache, stabile YAML-Ausgabe für ``Schlüssel: Skalar``-Maps."""
    einzug = "  " * tiefe
    zeilen: list[str] = []
    for schluessel, wert in daten.items():
        if isinstance(wert, dict):
            zeilen.append(f"{einzug}{schluessel}:")
            zeilen.extend(_yaml_liste(wert, tiefe=tiefe + 1))
        elif isinstance(wert, list):
            zeilen.append(f"{einzug}{schluessel}:")
            zeilen.extend(_yaml_eintraege(wert, tiefe=tiefe + 1))
        else:
            zeilen.append(f"{einzug}{schluessel}: {_yaml_wert(wert)}")
    return zeilen


def _yaml_eintraege(eintraege: list[Any], *, tiefe: int) -> list[str]:
    """Listeneinträge als ``- schluessel: wert`` mit richtigem Einzug.

    Ein Objekt in einer Liste wird als ``- key: wert`` geschrieben, seine
    weiteren Schlüssel auf derselben Ebene (``  key2: wert``) — genau die Form,
    die ``export-library`` liefert (im Wegwerf-Primo belegt).
    """
    einzug = "  " * tiefe
    zeilen: list[str] = []
    for eintrag in eintraege:
        if isinstance(eintrag, dict):
            unter = _yaml_liste(eintrag, tiefe=tiefe + 1)
            if unter:
                unter[0] = f"{einzug}- " + unter[0].lstrip()
            zeilen.extend(unter)
        else:
            zeilen.append(f"{einzug}- {_yaml_wert(eintrag)}")
    return zeilen


def _feld_yaml(feld: dict[str, Any]) -> list[str]:
    """Eine Felddefinition als YAML-Listeneintrag (flache Schlüssel).

    Aufbau wie im Export: ``- name: …`` mit ``label``/``type`` auf derselben
    Ebene, ``config`` als Unterschlüssel (dort liegen die Optionen einer
    Auswahl).
    """
    einzug = "  "
    zeilen = [f"{einzug}- name: {_yaml_wert(feld['name'])}"]
    for schluessel in ("label", "type"):
        zeilen.append(f"{einzug}  {schluessel}: {_yaml_wert(feld.get(schluessel) or '')}")
    config = feld.get("config")
    if isinstance(config, dict) and config:
        zeilen.append(f"{einzug}  config:")
        # Der Inhalt von `config` steht eine Ebene TIEFER als `config:`.
        # (_yaml_liste(tiefe=3) ergaebe 6 Leerzeichen = Geschwister von
        # `config:` — YAML laese die Optionen dann auf die Feldebene.)
        zeilen.extend(
            stecke(_yaml_liste(config, tiefe=2), um=1)
        )
    return zeilen


def stecke(zeilen: list[str], *, um: int = 1) -> list[str]:
    """Rueckt nicht-leere Zeilen um ``um`` Ebenen (2 Leerzeichen) ein."""
    leerzeichen = "  " * um
    return [leerzeichen + zeile if zeile.strip() else zeile for zeile in zeilen]


def build_zip(
    *,
    version: int,
    basisadresse: str,
    bausteine: Iterable[Baustein] | None = None,
) -> bytes:
    """Die Bibliothek als ZIP in der Struktur von ``export-library``.

    Aufbau (im Wegwerf-Primo belegt, ``POST /api/primo/import-library``):

        library/groups.yaml
        library/diakronos/<kennung>/component.svelte
        library/diakronos/<kennung>/config.yaml
        library/diakronos/<kennung>/fields.yaml
        library/diakronos/<kennung>/content.yaml

    ``basisadresse`` belegt das Feld „Diakronos-Adresse" vor (B2). Sie wird nur
    gesetzt, wenn sie eine absolute ``http(s)``-Adresse ist — sonst bleibt das
    Feld leer und der Redakteur trägt sie ein. Eine erfundene Adresse wäre
    schlimmer als eine leere.
    """
    liste = tuple(bausteine) if bausteine is not None else bausteine_lesen()
    adresse = _absolute_adresse(basisadresse)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", compression=zipfile.ZIP_DEFLATED) as archiv:
        # `groups.yaml` ist eine BARE Liste (export-library schreibt genau das,
        # im Wegwerf-Primo belegt). Eine Gruppe ohne `id`: Primo vergibt sie.
        archiv.writestr(
            "library/groups.yaml",
            "\n".join(
                [
                    f"- id: {_yaml_wert('')}",
                    f"  name: {_yaml_wert(GRUPPE_NAME)}",
                    f"  folder: {_yaml_wert(GRUPPE_ORDNER)}",
                    "  index: 0",
                ]
            )
            + "\n",
        )

        for baustein in liste:
            basis = f"library/{GRUPPE_ORDNER}/{baustein.kennung}"
            archiv.writestr(f"{basis}/component.svelte", baustein.quelle)
            archiv.writestr(
                f"{basis}/config.yaml",
                "\n".join(
                    [
                        f"name: {_yaml_wert(blockname_mit_version(baustein.kennung, version))}",
                    ]
                )
                + "\n",
            )
            feld_zeilen: list[str] = []
            inhalt: list[dict[str, Any]] = []
            for feld in baustein.felder:
                feld_zeilen.extend(_feld_yaml(feld))
                vorgabe = feld.get("default")
                if feld["name"] == FELD_BASISADRESSE and adresse:
                    vorgabe = adresse
                inhalt.append({"key": str(feld["name"]), "value": vorgabe})
            archiv.writestr(f"{basis}/fields.yaml", "\n".join(feld_zeilen) + "\n")
            archiv.writestr(f"{basis}/content.yaml", _content_yaml(inhalt))
    return puffer.getvalue()


def _content_yaml(eintraege: list[dict[str, Any]]) -> str:
    """``content.yaml`` eines Bausteins — Abbild wie bei ``export-library``.

    Primo liest die Datei als **Map ``key -> Vorgabewert``**
    (``importLibraryBlockContent``: ``yaml.Unmarshal(data, &contentMap)`` mit
    ``map[string]interface{}``; ``export_library.go``/``buildSectionContent``
    schreiben genau diese Form). Eine Liste — wie sie für ``fields.yaml``
    richtig ist — scheitert dort am Typ; Primo meldet dann zwar keinen Fehler,
    die Blöcke bekommen aber LEERE Vorgaben. Am Wegwerf-Primo belegt: mit einer
    Liste (BS-2e, erster Lauf) kamen 93 von 128 Feldern leer im
    veröffentlichten Build an, darunter alle Beschriftungen.

    Geschrieben werden ALLE Felder in der Reihenfolge des Feldschemas (dieselbe
    Reihenfolge wie ``fields.yaml``), damit ein Mensch beide Dateien
    nebeneinander lesen kann.

    Leere Vorgaben werden als YAML-``null`` (``key: ~``) geschrieben, NICHT als
    ``""``: Primo überspringt beim Import Einträge, deren Wert leer ist, und
    dann fehlt dem Block das Feld ganz — sein `$props`-Vertrag liest den
    Vorgabewert aus dem Svelte-Quelltext, ein gesetzter Feldwert überschriebe
    ihn aber mit ``undefined`` (im Wegwerf-Primo belegt, BS-2e Runde 3: 22 von
    128 Feldern fehlten, u. a. ``kennung`` und ``gruppentyp``, die als
    Vorgabe ``""`` haben). ``null`` schreibt Primo als leeren Wert aus.
    """
    return (
        "\n".join(
            _yaml_liste(
                {
                    str(e["key"]): (
                        None if e["value"] == "" else e["value"]
                    )
                    for e in eintraege
                }
            )
        )
        + "\n"
    )


def _absolute_adresse(wert: object) -> str:
    """Nur eine absolute http(s)-Adresse; alles andere wird ``""``."""
    from urllib.parse import urlsplit

    text = str(wert or "").strip().rstrip("/")
    if not text or "://" not in text:
        return ""
    teile = urlsplit(text)
    if teile.scheme not in ("http", "https") or not teile.hostname:
        return ""
    return text


def basisadresse() -> str:
    """Öffentliche Diakronos-Basisadresse für das Feld „Diakronos-Adresse" (G3).

    Reihenfolge — gepflegte Adresse gewinnt vor der Konfiguration:

      1. ``Einstellungen → Gemeinde → Öffentliche Adresse``
         (``anmeldung.registrierungslink.oeffentliche_basis``): die Adresse,
         unter der die Gemeinde ihre Website/ihr Diakronos erreicht.
      2. ``APP_BASE_URL`` + ``DIAKRONOS_BASE_PATH`` (WEB-5a): dieselbe
         Zusammensetzung wie ``settings.oidc_redirect_ziel``.

    Ist beides leer, kommt ``""`` — der Installer setzt dann NICHT vor (der
    Redakteur trägt die Adresse im Feld ein).
    """
    from diakronos_app.base_path import normalisiere as praefix

    try:
        from diakronos_app.anmeldung.registrierungslink import oeffentliche_basis
        from diakronos_app.db import lesesitzung

        with lesesitzung() as sess:
            gepflegt = _absolute_adresse(oeffentliche_basis(sess))
        if gepflegt:
            return gepflegt
    except Exception as exc:  # noqa: BLE001 — fehlende Einstellung ist kein Fehler
        logger.debug("Bausteine: öffentliche Adresse nicht lesbar (%s).", type(exc).__name__)

    basis = str(getattr(settings, "app_base_url", "") or "").strip().rstrip("/")
    if not basis:
        return ""
    return _absolute_adresse(basis + praefix(getattr(settings, "diakronos_base_path", "")))


# ── Auslieferung an Primo ───────────────────────────────────────────────────


@dataclass
class Stand:
    """Was in Primo an Diakronos-Bausteinen liegt (gelesen, nicht geschrieben)."""

    erreichbar: bool = False
    mitgeliefert: int = 0
    installiert: int = 0
    bausteine: list[dict[str, Any]] = field(default_factory=list)
    revision: str = ""
    hinweis: str = ""

    @property
    def veraltet(self) -> bool:
        """True, wenn die installierte Fassung älter ist als die mitgelieferte."""
        return self.erreichbar and self.installiert < self.mitgeliefert

    def als_dict(self) -> dict[str, Any]:
        return {
            "erreichbar": self.erreichbar,
            "mitgeliefert_version": self.mitgeliefert,
            "installiert_version": self.installiert,
            "veraltet": self.veraltet,
            "revision": self.revision,
            "hinweis": self.hinweis,
            "bausteine": self.bausteine,
            "mitgeliefert": _mitgelieferte_liste(),
        }


def _mitgelieferte_liste() -> list[dict[str, Any]]:
    """Die mitgelieferten Bausteine für die Oberfläche (BS-2d1).

    ``[{kennung, name, beschreibung, freigaben, sha256, felder}, …]`` — auch
    dann, wenn in Primo NOCH NICHTS davon liegt: vor dem ersten Einspielen ist
    ``bausteine`` (der Primo-Stand) leer, und die Oberfläche soll trotzdem
    zeigen, was Diakronos mitbringt.

    Ein Fehler in den Quellen ist hier KEIN Fehler des Abrufs: die Antwort
    bleibt, ``mitgeliefert`` ist dann leer und ``hinweis`` sagt warum (dieselbe
    Regel wie beim nicht erreichbaren Primo: die Anzeige darf nie 500 ergeben).
    """
    try:
        return [b.als_dict() for b in bausteine_lesen()]
    except BausteinQuelleFehler as exc:
        logger.info("Bausteine: mitgelieferte Liste nicht lesbar (%s).", type(exc).__name__)
        return []


def _hinweis_fuer_quellen() -> str:
    """Klartext-Hinweis, wenn die Quellen der Bausteine unbrauchbar sind."""
    try:
        bausteine_lesen()
    except BausteinQuelleFehler:
        return "Die mitgelieferten Bausteine sind unvollständig."
    return ""


@dataclass
class Installationsergebnis:
    """Ergebnis eines Einspielvorgangs."""

    version: int
    bausteine: list[str]
    revision: str = ""
    weg: str = "zip"

    def als_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "bausteine": self.bausteine,
            "revision": self.revision,
            "weg": self.weg,
        }


def _client(timeout: float | None = None) -> Any:
    """HTTP-Client mit hartem Timeout (eigener Import: Zyklus vermeiden).

    ``timeout`` ueberschreibt den Lesetimeout aus den Einstellungen. Gebraucht
    wird das fuer den SCHREIBENDEN Bibliotheks-Import, der laenger dauern darf
    als eine kleine Abfrage (siehe :data:`IMPORT_TIMEOUT_SEKUNDEN`).
    """
    import httpx

    from diakronos_app.website import primo

    if timeout is None:
        return primo._client()  # noqa: SLF001 — bewusst derselbe Timeout/trust_env
    return httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    )


def _url(pfad: str) -> str:
    from diakronos_app.website import primo

    return primo._url(pfad)  # noqa: SLF001


def _fehlertext(antwort: Any) -> str:
    from diakronos_app.website import primo

    return primo._fehlertext(antwort)  # noqa: SLF001


def _auth_kopf(token: str) -> dict[str, str]:
    return {"Authorization": token}


def _superuser_token() -> str:
    """Superuser-Token von PocketBase (``auth-with-password``).

    BS-2d3-Nacharbeit: der Merker steht an EINER Stelle -- in
    :func:`diakronos_app.website.primo.superuser_token` (Bindung an URL/E-Mail,
    Laufzeit aus dem ``exp`` des Tokens). Diese Funktion ist nur noch der
    Einstiegspunkt dieses Moduls dorthin und uebersetzt Fehler in die eigenen
    Ausnahmen; vorher gab es zwei Merker (hier und im Bericht), und die
    Anmeldung konnte doppelt laufen -- PocketBase antwortet darauf mit **429**
    (Befund BS-2d3).

    Der Client des Adapters benutzt denselben Timeout und ``trust_env`` --
    in Tests denselben Transport.
    """
    from diakronos_app.settings import settings
    from diakronos_app.website import primo

    if not settings.primo_konfiguriert:
        from diakronos_app.website.primo import PrimoNichtKonfiguriert

        raise PrimoNichtKonfiguriert(
            "Primo ist nicht konfiguriert (PRIMO_URL/Superuser fehlen)."
        )
    try:
        return primo.superuser_token()
    except primo.PrimoNichtErreichbar as exc:
        raise PrimoSyncAbgelehnt(0, "Primo nicht erreichbar") from exc
    except primo.PrimoAbgelehnt as exc:
        raise PrimoSyncAbgelehnt(exc.status, exc.grund) from exc


def _mit_token(aufruf: Any) -> Any:
    """``aufruf(token)`` mit EINER neuen Anmeldung bei 401/403.

    Ein abgelaufenes oder zurueckgezogenes Superuser-Token kam bisher als
    "Zugriff abgelehnt" beim Benutzer an, obwohl ein neuer Login gereicht
    haette. Hier wird der Merker verworfen und der Aufruf genau einmal
    wiederholt; ein zweites 401/403 geht durch (dann stimmen die Daten nicht).
    """
    from diakronos_app.website import primo

    token = _superuser_token()
    try:
        return aufruf(token)
    except PrimoSyncAbgelehnt as fehler:
        if fehler.status not in primo.TOKEN_UNGUELTIG_STATUS:
            raise
        primo.token_verwerfen(nur_wenn=token)
        logger.info(
            "Bausteine: Superuser-Token abgelehnt (HTTP %s), neue Anmeldung.", fehler.status
        )
    return aufruf(_superuser_token())


def revision_holen(token: str) -> str:
    """Die aktuelle Bibliotheks-Revision (``X-Primo-Revision`` des Exports).

    Ohne diesen Wert antwortet ``import-library`` mit **428** (BS-0 F6, im
    Versuch belegt) — der Import braucht eine Sync-Basis. Der Export ist ein
    Lesevorgang; hier wird nur der Kopf benutzt, das ZIP verworfen.
    """
    import httpx

    try:
        with _client() as client:
            antwort = client.get(_url("/api/primo/export-library"), headers=_auth_kopf(token))
            # Der Rumpf interessiert nicht: nur den Kopf lesen und die
            # Verbindung schliessen. (Ein grosses ZIP in den Speicher zu
            # ziehen waere unnoetig.)
            if antwort.status_code != 200:
                raise PrimoSyncAbgelehnt(antwort.status_code, _fehlertext(antwort))
            return str(antwort.headers.get("X-Primo-Revision") or "").strip()
    except httpx.HTTPError as exc:
        raise PrimoSyncAbgelehnt(0, "Primo nicht erreichbar") from exc


def _import_zip(token: str, zip_bytes: bytes, expected_revision: str) -> dict[str, Any]:
    """``POST /api/primo/import-library`` (multipart: file, expected_revision)."""
    import httpx

    dateien = {"file": ("diakronos-bausteine.zip", zip_bytes, "application/zip")}
    daten = {"expected_revision": expected_revision}
    try:
        # EIGENER Timeout: dieser Aufruf SCHREIBT die ganze Bibliothek. Der
        # Lesetimeout aus `PRIMO_TIMEOUT_SEKUNDEN` (Default 5 s) reicht dafuer
        # nicht und brach den Import ab, waehrend Primo ihn fertig schrieb
        # (BS-2d3-Befund; siehe `import_timeout_sekunden`).
        with _client(import_timeout_sekunden()) as client:
            antwort = client.post(
                _url("/api/primo/import-library"),
                files=dateien,
                data=daten,
                headers=_auth_kopf(token),
            )
    except httpx.TimeoutException as exc:
        raise PrimoSyncAbgelehnt(0, "Zeitueberschreitung") from exc
    except httpx.HTTPError as exc:
        raise PrimoSyncAbgelehnt(0, "Primo nicht erreichbar") from exc
    if antwort.status_code != 200:
        raise PrimoSyncAbgelehnt(antwort.status_code, _fehlertext(antwort))
    try:
        koerper = antwort.json()
    except ValueError as exc:
        raise PrimoSyncAbgelehnt(200, "Antwort ist kein JSON") from exc
    return koerper if isinstance(koerper, dict) else {}


def _finde_eintrag(client: Any, sammlung: str, filter_: str, token: str) -> dict[str, Any] | None:
    """Ersten Datensatz einer Sammlung zu einem Filter lesen (``None`` = keiner).

    PocketBase-Filter sind Ausdruecke (``name = "x" && group = "y"``); der Wert
    wird mit :func:`json.dumps` als JSON-Zeichenkette eingesetzt — damit sind
    Anfuehrungszeichen und Sonderzeichen im Namen abgedeckt.
    """
    antwort = client.get(
        _url(f"/api/collections/{sammlung}/records"),
        params={"filter": filter_, "perPage": 1},
        headers=_auth_kopf(token),
    )
    if antwort.status_code != 200:
        raise PrimoSyncAbgelehnt(antwort.status_code, _fehlertext(antwort))
    eintraege = (antwort.json() or {}).get("items") or []
    if not eintraege:
        return None
    erster = eintraege[0]
    return erster if isinstance(erster, dict) else None


def _upsert(
    client: Any,
    sammlung: str,
    filter_: str,
    daten: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    """Datensatz anlegen ODER den vorhandenen ergaenzen (F3).

    Gesucht wird ueber den Filter (bei Bloecken ``name``, bei Feldern
    ``key``+``symbol``, bei Eintraegen ``field``+``locale``). Ein Treffer wird
    per ``PATCH`` aktualisiert, sonst per ``POST`` angelegt. Genau das macht den
    Weg wiederholbar: ein zweiter Lauf erzeugt KEINE Dubletten.
    """
    vorhanden = _finde_eintrag(client, sammlung, filter_, token)
    if vorhanden is None:
        antwort = client.post(
            _url(f"/api/collections/{sammlung}/records"),
            json=daten,
            headers=_auth_kopf(token),
        )
    else:
        antwort = client.patch(
            _url(f"/api/collections/{sammlung}/records/{vorhanden.get('id')}"),
            json=daten,
            headers=_auth_kopf(token),
        )
    if antwort.status_code not in (200, 201, 204):
        raise PrimoSyncAbgelehnt(antwort.status_code, _fehlertext(antwort))
    koerper = antwort.json() if antwort.content else {}
    return koerper if isinstance(koerper, dict) else {}


def _import_einzeln(token: str, bausteine: Iterable[Baustein], version: int,
                    adresse: str) -> str:
    """Rueckfallebene: Bibliothek per PocketBase-REST schreiben (BS-0 Roh-API).

    Wird nur benutzt, wenn Primo den Import-Endpunkt nicht kennt (404/405).

    BS-2a2 (F3): **idempotent.** Gruppe, Block, Felder und Vorgaben werden per
    Upsert geschrieben (siehe :func:`_upsert`) — der Weg ist wiederholbar, ein
    zweiter Lauf erzeugt keine Dubletten. Der Blockname traegt weiterhin die
    Version (``diakronos/<kennung>@v2``): eine neue Version legt also einen
    NEUEN Block daneben, die aeltere Fassung bleibt unangetastet. Angepasste
    Kopien in Primo-Sites werden in keinem Fall beruehrt (BS-0 F2c).
    """
    import httpx

    gruppe_id = ""
    with _client() as client:
        try:
            gruppe = _upsert(
                client,
                "library_symbol_groups",
                f"name = {json.dumps(GRUPPE_NAME)}",
                {"name": GRUPPE_NAME, "index": 0},
                token,
            )
            gruppe_id = str(gruppe.get("id") or "")
            if not gruppe_id:
                raise PrimoSyncAbgelehnt(200, "Gruppe ohne Kennung")

            for baustein in bausteine:
                name = blockname_mit_version(baustein.kennung, version)
                html, css, js = _zerlegen(baustein.quelle)
                symbol = _upsert(
                    client,
                    "library_symbols",
                    f"name = {json.dumps(name)}",
                    {
                        "name": name,
                        "group": gruppe_id,
                        "html": html,
                        "css": css,
                        # BS-2e: `js` bleibt LEER. Der `<script>`-Block einer
                        # Svelte-Quelle ist KEIN ausführbares JavaScript (Props,
                        # `$derived`, `$effect`); Primo übersetzt beim Import
                        # selbst aus `raw_source` (Node mit `svelte/compiler`).
                        # Ein vorbefülltes `js`-Feld hat den Übersetzer
                        # übersprungen: die Bibliothek trug dann den Quelltext
                        # im JS-Feld, der Publish lieferte einen Block ohne
                        # Verhalten (am Wegwerf-Primo belegt: Hydration-Modul
                        # 404, alle Blöcke blieben im Ladezustand).
                        "js": "",
                        "raw_source": baustein.quelle,
                    },
                    token,
                )
                symbol_id = str(symbol.get("id") or "")
                if not symbol_id:
                    raise PrimoSyncAbgelehnt(200, "Block ohne Kennung")

                for reihenfolge, feld in enumerate(baustein.felder):
                    feld_antwort = _upsert(
                        client,
                        "library_symbol_fields",
                        f"key = {json.dumps(str(feld['name']))} && "
                        f"symbol = {json.dumps(symbol_id)}",
                        {
                            "key": feld["name"],
                            "label": feld.get("label") or feld["name"],
                            "type": feld["type"],
                            "symbol": symbol_id,
                            "config": feld.get("config") or None,
                            "index": reihenfolge,
                        },
                        token,
                    )
                    feld_id = str(feld_antwort.get("id") or "")
                    vorgabe = feld.get("default")
                    if feld["name"] == FELD_BASISADRESSE and adresse:
                        vorgabe = adresse
                    if feld_id == "":
                        continue
                    # Eine Vorgabe von `null` ist der AUSDRUECKLICHE Wunsch
                    # "leer" (fields.json verlangt den Schluessel) — dann wird
                    # ein vorhandener Eintrag auf leer gesetzt, nicht geloescht.
                    _upsert(
                        client,
                        "library_symbol_entries",
                        f"field = {json.dumps(feld_id)} && locale = \"en\"",
                        {
                            "field": feld_id,
                            # Der Editor arbeitet mit der Sprache `en`; `de`
                            # ergaebe Leerwerte (BS-0 F3, Nebenbefund).
                            "locale": "en",
                            "value": "" if vorgabe is None else vorgabe,
                            "index": 0,
                        },
                        token,
                    )
        except httpx.HTTPError as exc:
            raise PrimoSyncAbgelehnt(0, "Primo nicht erreichbar") from exc
    return "einzeln"


def _zerlegen(quelle: str) -> tuple[str, str, str]:
    """``(html, css, js)`` wie Primo es aus ``component.svelte`` gewinnt.

    BS-2e: ``js`` wird vom Aufrufer (Rückfallweg) NICHT geschrieben — siehe
    dort. Die Funktion liefert den Inhalt des ``<script>``-Blocks weiterhin
    mit, weil ``_import_einzeln`` ihn für das Feld ``raw_source`` braucht.

    Primo selbst zerlegt beim Import mit regulären Ausdrücken
    (``internal/import.go::parseComponent``); hier dieselbe Zerlegung, damit
    der Rückfallweg dieselben drei Felder schreibt. Der ZIP-Weg braucht das
    nicht (Primo zerlegt dort selbst).
    """
    css = ""
    js = ""
    treffer_style = re.search(r"(?s)<style[^>]*>(.*?)</style>", quelle)
    if treffer_style:
        css = treffer_style.group(1).strip()
    treffer_script = re.search(r"(?s)<script[^>]*>(.*?)</script>", quelle)
    if treffer_script:
        js = treffer_script.group(1).strip()
    html = quelle
    html = re.sub(r"(?s)<style[^>]*>.*?</style>", "", html)
    html = re.sub(r"(?s)<script[^>]*>.*?</script>", "", html)
    return html.strip(), css, js


# ── In-Prozess-Merker (BS-2a2/F2) ──────────────────────────────────────────
#
# Nicht bei JEDEM Login Superuser-Anmeldung + vollständiger Bibliotheks-Export:
# hat DIESER Prozess eine Version einmal bestätigt (gelesen oder eingespielt),
# wird sie nicht erneut geprüft. Der Merker ist reiner Speicher — kein Redis,
# keine Tabelle, keine Migration. Nach einem Neustart wird wieder geprüft.

#: Höchste in diesem Prozess bestätigte Auslieferungsversion (0 = nichts).
_bestaetigte_version = 0


def bestaetigte_version() -> int:
    """Die in diesem Prozess bestätigt installierte Version (0 = keine)."""
    return _bestaetigte_version


def version_bestaetigen(version: object) -> None:
    """Merkt eine bestätigt installierte Version für diesen Prozess.

    Nur aufwärts: ein älterer Wert (paralleler Lauf, ältere Lesung) darf eine
    bereits bestätigte neuere Version nicht zurücksetzen.
    """
    global _bestaetigte_version
    try:
        wert = int(str(version).strip())
    except (TypeError, ValueError):
        return
    if wert > _bestaetigte_version:
        _bestaetigte_version = wert


def merker_zuruecksetzen() -> None:
    """Merker vergessen (Tests, Betreiber-Eingriff über `bausteine_installieren`).

    BS-2d3-Nacharbeit: der Superuser-Token-Merker liegt im Adapter
    (`primo`); er wird hier mit geleert. Das Prozess-Gedaechtnis "Bibliothek
    bestaetigt" bleibt die Aufgabe dieses Moduls.
    """
    global _bestaetigte_version
    from diakronos_app.website import primo

    _bestaetigte_version = 0
    primo.anmeldung_zuruecksetzen()


def steht_bereit(version: int | None = None) -> bool:
    """True, wenn die (mitgelieferte) Version in diesem Prozess bestätigt ist.

    ``version`` ist die mitgelieferte Version; ohne Angabe wird sie gelesen.
    Ein Lesefehler der Quellen ist ``False`` — dann entscheidet der Aufrufer.
    """
    try:
        ziel = mitgelieferte_version() if version is None else int(version)
    except BausteinQuelleFehler:
        return False
    return ziel >= 1 and _bestaetigte_version >= ziel


def sync(*, basis: str | None = None) -> Installationsergebnis:
    """Spielt die mitgelieferte Bibliothek in Primo ein (idempotent).

    Ablauf: Version und Quellen lesen -> ZIP bauen -> Primo-Revision holen ->
    Import mit ``expected_revision`` -> bei 404/405 Rückfall auf den Einzelweg.

    Fehler: :class:`PrimoSyncAbgelehnt` (Status + Kurzgrund) oder
    :class:`BausteinQuelleFehler`. Aufrufer, die den Login nicht stören dürfen,
    fangen beides.
    """
    ergebnis = _sync_echt(basis=basis)
    # F2: ein BESTÄTIGTER Lauf merkt die Version für den Prozess.
    version_bestaetigen(ergebnis.version)
    return ergebnis


def _sync_echt(*, basis: str | None = None) -> Installationsergebnis:
    """Der eigentliche Einspielvorgang (ohne Merker, für Tests/`sync`)."""
    version = mitgelieferte_version()
    bausteine = bausteine_lesen()
    adresse = _absolute_adresse(basis) if basis is not None else basisadresse()
    paket = build_zip(version=version, basisadresse=adresse, bausteine=bausteine)

    def einspielen(token: str) -> Installationsergebnis:
        revision = revision_holen(token)
        try:
            koerper = _import_zip(token, paket, revision)
        except PrimoSyncAbgelehnt as fehler:
            if fehler.status in (404, 405):
                # Kein Import-Endpunkt in dieser Primo-Fassung: Einzelweg.
                logger.info("Bausteine: Import-Endpunkt fehlt, benutze Einzelweg.")
                weg = _import_einzeln(token, bausteine, version, adresse)
                return Installationsergebnis(
                    version=version,
                    bausteine=[b.kennung for b in bausteine],
                    weg=weg,
                )
            raise
        kennungen = [b.kennung for b in bausteine]
        logger.info(
            "Bausteine eingespielt (Version %s, %s Blöcke).", version, len(kennungen)
        )
        return Installationsergebnis(
            version=version,
            bausteine=kennungen,
            revision=str(koerper.get("revision") or ""),
        )

    # BS-2d3-Nacharbeit: 401/403 -> Merker verwerfen, EINE neue Anmeldung.
    return _mit_token(einspielen)

    kennungen = [b.kennung for b in bausteine]
    logger.info("Bausteine eingespielt (Version %s, %s Blöcke).", version, len(kennungen))
    return Installationsergebnis(
        version=version,
        bausteine=kennungen,
        revision=str(koerper.get("revision") or ""),
    )


def bibliothek_stand() -> Stand:
    """Was liegt in Primo? — liest die Bibliothek, schreibt nichts, wirft nie.

    Grundlage ist der Bibliotheks-Export (``GET /api/primo/export-library``):
    daraus kommt die Revision UND je Block der Name samt Versionsvermerk. Ein
    nicht erreichbares oder nicht berechtigtes Primo ist der Zustand
    ``erreichbar=False``, keine Ausnahme.
    """
    from diakronos_app.website import primo as primo_adapter

    mitgeliefert = 0
    try:
        mitgeliefert = mitgelieferte_version()
    except BausteinQuelleFehler:
        mitgeliefert = 0
    quellen_hinweis = _hinweis_fuer_quellen()

    if not primo_adapter.settings.primo_konfiguriert:
        return Stand(
            mitgeliefert=mitgeliefert,
            hinweis=quellen_hinweis or "Der Website-Baukasten ist nicht eingerichtet.",
        )

    try:
        roh, revision = _mit_token(_export_zip)
        namen = _bloecke_aus_zip(roh)
    except Exception as exc:  # noqa: BLE001 — Anzeige darf nie 500 ergeben
        logger.info("Bausteine: Stand nicht lesbar (%s).", type(exc).__name__)
        return Stand(
            mitgeliefert=mitgeliefert,
            hinweis=quellen_hinweis or "Die Bibliothek ist derzeit nicht abrufbar.",
        )

    # Keine Zeile in der Bibliothek (oder nur fremde Gruppen): es ist NICHTS
    # von Diakronos installiert. Dann ist "installiert" ehrlich 0 und ein
    # Nachziehen findet statt — der Normalfall der Erstinstallation.
    eintraege: list[dict[str, Any]] = []
    hoechste = 0
    for name in namen:
        zerlegt = version_aus_blockname(name)
        if zerlegt is None:
            continue
        kennung, version = zerlegt
        hoechste = max(hoechste, version)
        eintraege.append({"kennung": kennung, "name": name, "version": version})

    # F2: Diese Lesung hat die Bibliothek bestätigt — liegt die installierte
    # Fassung nicht hinter der mitgelieferten, ist für DIESEN Prozess nichts
    # mehr zu tun (der nächste Login überspringt Anmeldung und Export).
    if hoechste >= mitgeliefert >= 1:
        version_bestaetigen(hoechste)

    return Stand(
        erreichbar=True,
        mitgeliefert=mitgeliefert,
        installiert=hoechste,
        bausteine=sorted(eintraege, key=lambda e: (e["kennung"], e["version"])),
        revision=revision,
        hinweis=quellen_hinweis,
    )


def _export_zip(token: str) -> tuple[bytes, str]:
    """Das Bibliotheks-ZIP samt Revision: ``(zip_bytes, revision)``.

    ``revision`` ist der Kopf ``X-Primo-Revision`` (``""``, wenn er fehlt) —
    der Aufrufer braucht BEIDE Werte, deshalb ein Tupel statt nur der Bytes.
    """
    import httpx

    from diakronos_app.website.primo import MAX_ANTWORT_BYTES

    try:
        with _client() as client:
            antwort = client.get(_url("/api/primo/export-library"), headers=_auth_kopf(token))
    except httpx.HTTPError as exc:
        raise PrimoSyncAbgelehnt(0, "Primo nicht erreichbar") from exc
    if antwort.status_code != 200:
        raise PrimoSyncAbgelehnt(antwort.status_code, _fehlertext(antwort))
    if len(antwort.content or b"") > MAX_ANTWORT_BYTES:
        raise PrimoSyncAbgelehnt(200, "Antwort zu gross")
    revision = str(antwort.headers.get("X-Primo-Revision") or "").strip()
    return antwort.content or b"", revision


def _bloecke_aus_zip(roh: bytes) -> list[str]:
    """Die Blocknamen aus dem Bibliotheks-ZIP — ohne externe YAML-Abhängigkeit.

    Gelesen wird nur ``config.yaml`` je Block (``name: …``). Das ist die eine
    Zeile, die ``export-library`` immer schreibt (``ExportedBlockConfig``);
    ein vollständiger YAML-Parser wäre für diesen Zweck eine neue Abhängigkeit
    im Image (NACHTRAG DOCKER Punkt 2) ohne Gegenwert.
    """
    namen: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(roh)) as archiv:
            for eintrag in archiv.namelist():
                if not eintrag.startswith("library/") or not eintrag.endswith("/config.yaml"):
                    continue
                if archiv.getinfo(eintrag).file_size > MAX_KOPF_BYTES:
                    continue
                text = archiv.read(eintrag).decode("utf-8", errors="replace")
                for zeile in text.splitlines():
                    if zeile.startswith("name:"):
                        namen.append(zeile.split(":", 1)[1].strip().strip('"\''))
                        break
    except (zipfile.BadZipFile, OSError) as exc:
        raise PrimoSyncAbgelehnt(200, "Antwort ist kein ZIP") from exc
    return namen
