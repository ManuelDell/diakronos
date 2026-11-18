"""Schluessel der Datei-Ablage (SPEICHER-1): EIN Begriff von „Datei".

Ein **Schluessel** ist ein Pfad RELATIV zur Wurzel der Ablage, mit ``/`` als
Trenner, ohne fuehrenden oder abschliessenden Schraegstrich::

    foto-abc123.png
    devmodus/2026-10-15/ab12cd34ef56.png

NIE ein absoluter Pfad. Die Wurzel kennt nur das jeweilige Backend
(``Lokal`` = ``settings.files_dir``, ``Nextcloud`` = ``nextcloud_ordner`` im
WebDAV-Baum), und kein Aufrufer soll sie kennen muessen.

Warum die Pruefung HIER liegt und nicht in den Umsetzungen
---------------------------------------------------------
Ein Pfad-Ausbruch (``../``, ``/etc/passwd``, ``a/../../b``, ein Nullbyte,
ein Laufwerksbuchstabe, ein UNC-Praefix) ist eine Eigenschaft des SCHLUESSELS,
nicht des Backends. Laege die Pruefung je Umsetzung, gaebe es zwei Wahrheiten
und die naechste Umsetzung haette die Luecke. Deshalb: genau eine Funktion
(:func:`normalisiere`), und BEIDE Backends rufen sie als erstes auf.

Abgewiesen wird laut (``UngueltigerSchluessel``) statt still bereinigt: ein
Schluessel, den ein Aufrufer falsch bildet, ist ein Fehler im Programm und
kein Fall fuer „irgendwie retten“. Nur so faellt auf, wenn eine Stelle
versehentlich absolute Pfade oder URLs in die Ablage reicht.
"""

from __future__ import annotations

import posixpath
import re

__all__ = [
    "MAX_SCHLUESSEL",
    "UngueltigerSchluessel",
    "ist_gueltig",
    "normalisiere",
]


class UngueltigerSchluessel(ValueError):
    """Der Schluessel ist kein relativer Pfad innerhalb der Ablage."""


#: Laengengrenze eines Schluessels in Zeichen. Nextcloud/WebDAV ist hier
#: grosszuegiger als jedes Dateisystem, aber ein 1000-Zeichen-Name ist kein
#: Dateiname mehr, sondern ein Fehler des Aufrufers.
MAX_SCHLUESSEL = 1024

#: Zeichen, die in einem Schluessel NIE vorkommen: Steuerzeichen (inkl.
#: Nullbyte — ``open()`` bricht dort ab, WebDAV schickt Muell) und der
#: Backslash (unter Windows ein Trenner, in URLs ein Fluchtzeichen).
_VERBOTEN = re.compile(r"[\x00-\x1f\x7f\\]")

#: Laufwerksbuchstabe (``C:``) und UNC-Praefix (``//host``) sind absolute
#: Pfade in fremder Schreibweise — beide haben in einem Schluessel nichts
#: verloren.
_LAUFWERK = re.compile(r"^[A-Za-z]:")


def normalisiere(schluessel: str) -> str:
    """Prueft einen Schluessel und gibt ihn kanonisch zurueck.

    Kanonisch heisst: ``/`` als Trenner, keine leeren Segmente, kein
    ``.``/``..``-Segment, kein fuehrender/abschliessender Schraegstrich —
    also genau die Form, die beide Backends wiedererkennen.

    ``UngueltigerSchluessel`` bei allem, was aus der Ablage herausfuehren
    koennte. Ein leerer Schluessel ist ebenfalls ungueltig: „die Wurzel“ ist
    keine Datei.
    """
    if not isinstance(schluessel, str):
        raise UngueltigerSchluessel("Schluessel muss Text sein.")
    # Leerraum aussen ist ein Versehen beim Zusammensetzen (f-String mit
    # Leerzeichen) — bereinigen ist hier richtig, weil er nichts bedeutet.
    # Ein Leerzeichen INNEN bleibt: Dateinamen duerfen es enthalten.
    roh = schluessel.strip()
    if not roh:
        raise UngueltigerSchluessel("Leerer Schluessel.")
    if len(roh) > MAX_SCHLUESSEL:
        raise UngueltigerSchluessel(
            f"Schluessel zu lang ({len(roh)} > {MAX_SCHLUESSEL} Zeichen)."
        )
    if _VERBOTEN.search(roh):
        # Kein Ausgeben des Zeichens: es landet sonst in einem Protokoll und
        # zerreisst die Zeile.
        raise UngueltigerSchluessel("Schluessel enthaelt Steuerzeichen.")
    if _ist_absolut(roh):
        raise UngueltigerSchluessel("Schluessel darf kein absoluter Pfad sein.")
    segmente = [teil for teil in roh.split("/") if teil not in ("", ".")]
    if any(teil == ".." for teil in segmente):
        raise UngueltigerSchluessel("Schluessel darf nicht aus der Ablage herausfuehren.")
    if not segmente:
        raise UngueltigerSchluessel("Leerer Schluessel.")
    return "/".join(segmente)


def _ist_absolut(wert: str) -> bool:
    """True, wenn der ROHWERT absolut aussieht (``/x``, ``//host/x``, ``C:``).

    Getrennt von :func:`normalisiere`, weil ``posixpath.normpath`` ein
    ``/etc/passwd`` NICHT als absolut meldet (es bleibt ``/etc/passwd``) —
    ohne eigene Pruefung waere der Ausbruch durchgerutscht.
    """
    return wert.startswith("/") or bool(_LAUFWERK.match(wert))


def ist_gueltig(schluessel: object) -> bool:
    """True, wenn :func:`normalisiere` den Wert annimmt (ohne Ausnahme)."""
    try:
        normalisiere(schluessel)  # type: ignore[arg-type]
    except UngueltigerSchluessel:
        return False
    return True


def elternordner(schluessel: str) -> list[str]:
    """Alle Elternordner eines Schluessels, von oben nach unten.

    ``a/b/c.png`` -> ``["a", "a/b"]``. ``Lokal`` legt sie beim Schreiben an
    (``mkdir(parents=True)``), ``Nextcloud`` schickt je Ordner ein MKCOL.
    """
    teile = normalisiere(schluessel).split("/")[:-1]
    return ["/".join(teile[: i + 1]) for i in range(len(teile))]


def gemeinsam(a: str, b: str) -> str:
    """Gemeinsamer Elternordner zweier Schluessel (``""`` = Wurzel)."""
    teile_a = normalisiere(a).split("/")[:-1]
    teile_b = normalisiere(b).split("/")[:-1]
    gemeinsam_: list[str] = []
    for links, rechts in zip(teile_a, teile_b):
        if links != rechts:
            break
        gemeinsam_.append(links)
    return "/".join(gemeinsam_)


def ist_unterordner(kandidat: str, ordner: str) -> bool:
    """Liegt ``kandidat`` unterhalb von ``ordner`` (oder ist er selbst)?"""
    k = normalisiere(kandidat)
    o = posixpath.normpath(normalisiere(ordner))
    return k == o or k.startswith(o + "/")
