"""Bilder am Anmeldeformular: Ablage, Abrufwege und Beschreibungstext (REG-1a).

Zwei Aufgaben, EINE Quelle:

1. **Abrufweg der Formularbilder.** Banner und Hintergrund sind Dateien in
   ``settings.files_dir`` (angelegt ueber den vorhandenen Upload-Mechanismus
   ``frappe_core.upload_file``). Gespeichert wird in
   ``anmeldeformular.bannerbild``/``hintergrundbild`` nur der DATEINAME.
   Ausgeliefert werden die Bilder ausschliesslich ueber

       GET /public/registrierung/<token>/bild/<banner|hintergrund>

   — also nur dem, der den Registrierungstoken hat. ``/files/…`` verlangt eine
   Anmeldung (``files.serve_file``) und bleibt fuer diese Bilder gesperrt: ein
   Bild, das „oeffentlich nur ueber das Formular abrufbar“ sein soll, darf
   nicht am Formular vorbei abrufbar sein.

2. **Beschreibungstext.** ``anmeldeformular.beschreibung`` ist freier Text der
   Verwaltung und geht an Besucher. Gespeichert/ausgeliefert wird reiner Text
   (Markdown-light: Absaetze, Zeilenumbrueche; Betonungen werden zu Text).
   **Kein Maskieren beim Speichern:** ``<``/``>`` bleiben Zeichen im Text —
   sonst liest der Besucher woertlich ``&lt;``. Das Escaping macht
   ausschliesslich die Anzeige (``{{ }}`` in Vue, nie ``v-html``).

3. **Lebenszyklus.** Ein Formularbild ist eine Datei MIT ``File``-Datensatz
   (Herkunft: ``upload_file``, siehe :func:`pruefe_bilddatei`). Wird es am
   Formular entfernt/ersetzt oder das Formular geloescht, raeumt
   :func:`raeume_bild_auf` Datei und Datensatz mit weg — sofern kein anderes
   Formular dieselbe Datei noch nutzt.

Der Token-Pfad existiert nur fuer den Link, nie fuer das Formular allein: ohne
gueltigen Link gibt es auch kein Bild (``registrierung._validate_token``).
"""

from __future__ import annotations

import re

from pathlib import Path

from diakronos_app.files import binary_content_type
from diakronos_app.settings import settings

__all__ = [
    "BILD_ROLLEN",
    "MAX_BESCHREIBUNG",
    "normalisiere_beschreibung",
    "bild_pfad",
    "dateiname_aus_wert",
    "pruefe_bilddatei",
    "oeffne_formularbild",
    "bild_noch_in_gebrauch",
    "raeume_bild_auf",
]

#: Rolle -> Spalte am `anmeldeformular`. Die Namen sind Teil der oeffentlichen
#: API (``/bild/<rolle>``) und der Antwortfelder (``banner_bild``/``hintergrund_bild``).
BILD_ROLLEN: dict[str, str] = {
    "banner": "bannerbild",
    "hintergrund": "hintergrundbild",
}

#: Obergrenze des Beschreibungstextes in Zeichen. Ein Formularhinweis ist ein
#: Absatz, kein Aufsatz; die Grenze verhindert, dass eine versehentlich
#: eingefuegte Riesendatei im oeffentlichen Seitenaufbau landet.
MAX_BESCHREIBUNG = 5000

#: Nur Dateinamen wie aus `upload_file` (`<uuid-hex>-<name>`): Buchstaben,
#: Ziffern, Punkt, Unterstrich, Bindestrich. Kein Pfadanteil, kein `..`.
_DATEINAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")

#: Markdown-light: `**fett**` und `*kursiv*` werden auf den reinen Text
#: reduziert, `\r\n` vereinheitlicht. KEIN HTML-Durchlass, keine Links.
_FETT = re.compile(r"\*\*([^*\n]+)\*\*")
_KURSIV = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")
#: Steuerzeichen ohne Zeilenumbruch/Tab (die bleiben: Absaetze und Einrueckung).
_STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalisiere_beschreibung(wert) -> str:
    """Beschreibungstext speicher-/auslieferbar machen (REG-1a).

    ``None``/leer -> ``""``. Zeilenumbrueche bleiben (Absaetze), Steuerzeichen
    fliegen raus, Markdown-Betonungen werden zu reinem Text. ``<`` und ``>``
    bleiben **Zeichen im Text**: gespeichert wird Klartext, das Escaping macht
    die Anzeige (``{{ }}``). Vorher stand hier ``&lt;`` im Speicher — der
    Besucher las dann woertlich „&lt;“ (Operator-Review REG-1a, Punkt 2).
    Ergebnis wird auf ``MAX_BESCHREIBUNG`` gekuerzt.
    """
    if wert is None:
        return ""
    text = str(wert).replace("\r\n", "\n").replace("\r", "\n")
    text = _STEUERZEICHEN.sub("", text)
    text = _FETT.sub(r"\1", text)
    text = _KURSIV.sub(r"\1", text)
    # Absaetze: hoechstens zwei Leerzeilen am Stueck.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text[:MAX_BESCHREIBUNG]


def dateiname_aus_wert(wert) -> str:
    """Gespeicherten Spaltenwert -> reiner Dateiname (oder ``""``).

    Altbestand aus Frappe kann ``/files/<name>`` oder ``/private/files/<name>``
    tragen; beides wird auf den Dateinamen zurueckgefuehrt. Alles, was danach
    nicht dem Dateinamen-Muster entspricht, gilt als „kein Bild“.
    """
    roh = str(wert or "").strip()
    if not roh:
        return ""
    # Ein Pfad ist ein Fehler, kein Hinweis: `/etc/passwd`, `../../x.png` und
    # `https://fremd/x.png` werden ABGELEHNT statt auf den Dateinamen gekuerzt.
    # Akzeptiert wird genau der Client, den `upload_file` erzeugt, und der
    # Frappe-Altbestand mit Praefix `/files/` bzw. `/private/files/`.
    for praefix in ("/private/files/", "/files/"):
        if roh.startswith(praefix):
            roh = roh[len(praefix):]
            break
    if not _DATEINAME.fullmatch(roh) or roh in {".", ".."}:
        return ""
    return roh


def bild_pfad(slug, rolle: str, wert) -> str:
    """Oeffentlicher Abrufpfad eines Formularbildes — ``""``, wenn keins gesetzt.

    Relativ (die Anzeige kennt ihren Host bereits) und bewusst mit Token: nur
    ueber den Link erreichbar, nie ueber ``/files/…``.
    """
    if rolle not in BILD_ROLLEN:
        raise ValueError(f"Unbekannte Bildrolle: {rolle!r}")
    name = dateiname_aus_wert(wert)
    if not name or not str(slug or "").strip():
        return ""
    return f"/public/registrierung/{slug}/bild/{rolle}"


def _zielpfad(name: str) -> Path | None:
    """Ein Dateiname -> Pfad unter ``files_dir`` (nie ausserhalb, nie Symlink)."""
    if not name:
        return None
    root = Path(settings.files_dir).resolve()
    kandidat = root / name
    if kandidat.is_symlink():
        return None
    if kandidat.resolve().parent != root:
        return None
    return kandidat


def _file_datensatz(name: str):
    """Der ``File``-Datensatz zu einem Dateinamen — oder ``None``.

    ``upload_file`` legt ihn immer mit an; eine Datei OHNE Datensatz ist keine
    von der App hochgeladene Datei (z. B. von Hand in ``files_dir`` gelegt)
    oder ihr Eintrag wurde bereits entfernt.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    with SessionLocal() as sess:
        return (
            sess.query(FileModel)
            .filter(FileModel.file_url.in_([f"/files/{name}", f"/private/files/{name}"]))
            .first()
        )


def _ist_fremde_privatdatei(datensatz) -> bool:
    """Gehoert die Datei zur PRIVATEN Ablage eines MITGLIEDS?

    ``/private/files/…`` bleibt grundsaetzlich gesperrt (fremde Ablage).
    Fuer den Rest entscheidet seit REG-1c NICHT MEHR die Rolle des
    Eigentuemers, sondern die ZUORDNUNG (``attached_to_doctype``/
    ``attached_to_name``): eine Datei ist nur dann ein Formularbild, wenn sie an
    genau DIESES Anmeldeformular angehaengt ist (:func:`pruefe_bilddatei`).

    REG-1b hatte hier „jede private Datei eines Verwalters ist zulaessig“
    eingefuehrt (Anlass: ein zweiter Administrator konnte ein vorhandenes
    Bild nicht mehr zuordnen). Das war zu weit: es gab JEDE private Datei aus
    der Hand eines Verwalters frei — auch ein Personenphoto, das an einem
    Mitgliedsdatensatz haengt. Die Zuordnung entscheidet genauer und nimmt
    beide Faelle mit (fremde Verwalter-Datei ohne/mit anderem Bezug ->
    abgelehnt, eigene Formular-Datei -> angenommen).
    """
    return str(getattr(datensatz, "file_url", "") or "").startswith("/private/files/")


def _ist_an_diesem_formular(datensatz, formular: str) -> bool:
    """Ist die Datei an GENAU dieses Anmeldeformular angehaengt?

    ``upload_file`` schreibt ``doctype``/``docname`` in den ``File``-Datensatz
    (``attached_to_doctype``/``attached_to_name``). Ein Formularbild entsteht
    damit nachweisbar AM Formular — und nur so eine Datei wird angenommen.
    Eine Datei ohne Bezug oder mit Bezug auf ein anderes Dokument (Mitglied,
    Lied, anderes Formular) ist kein Formularbild, auch wenn ein Verwalter sie
    hochgeladen hat.
    """
    ziel = str(formular or "").strip()
    if not ziel:
        return False
    doctype = str(getattr(datensatz, "attached_to_doctype", "") or "").strip()
    name = str(getattr(datensatz, "attached_to_name", "") or "").strip()
    return doctype == "Anmeldeformular" and name == ziel


def pruefe_bilddatei(name: str, formular: str) -> str | None:
    """Dateiname aus dem Upload -> gueltiger Bildname oder ``None``.

    Zulaessig ist nur, was ueber **diesen** Formular-Upload entstanden sein
    kann (Operator-Review REG-1a, Punkt 3; REG-1c, Punkt 1). Geprueft wird
    deshalb:

      1. der Name entspricht dem Dateinamen-Muster (kein Pfad, kein ``..``),
      2. es gibt einen ``File``-Datensatz zu genau diesem Namen — sonst waere
         es eine beliebige Datei aus ``files_dir`` (z. B. ein privates Foto
         eines Mitglieds), die hier oeffentlich wuerde,
      3. die Datei ist an GENAU DIESES Anmeldeformular angehaengt
         (``attached_to_doctype == "Anmeldeformular"`` und
         ``attached_to_name == formular``). Die Rolle des Eigentuemers
         entscheidet NICHT: eine fremde Verwalter-Datei (Profilfoto an einem
         Mitglied, Bild eines anderen Formulars) bleibt draussen,
      4. die Mitglieds-Privatablage (``/private/files/…``) ist ausgenommen,
      5. die Datei existiert unter ``files_dir`` und ihre MAGIC-BYTES sind ein
         Rasterbild (PNG/JPEG/GIF/WebP).

    ``formular`` ist die Kennung des Formulars, an dem das Bild haengen soll.
    Ohne sie wird NICHTS angenommen — ein Aufruf ohne Ziel waere die alte
    Lockerung.

    Rueckgabe: der zu speichernde Dateiname oder ``None``.
    """
    sauber = dateiname_aus_wert(name)
    if not sauber:
        return None
    datensatz = _file_datensatz(sauber)
    if datensatz is None:
        return None
    if not _ist_an_diesem_formular(datensatz, formular):
        return None
    if _ist_fremde_privatdatei(datensatz):
        return None
    if oeffne_formularbild(sauber) is None:
        return None
    return sauber


def oeffne_formularbild(name: str) -> tuple[Path, str] | None:
    """Datei eines Formularbildes oeffnen: ``(Pfad, Content-Type)`` oder ``None``.

    Der Content-Type kommt aus den MAGIC-BYTES: gespeichert wird nur, was
    wirklich ein Rasterbild ist (PNG/JPEG/GIF/WebP). Alles andere (auch SVG)
    ergibt ``None`` — ein Formularbild wird nie als Markup ausgeliefert.
    """
    pfad = _zielpfad(name)
    if pfad is None or not pfad.is_file():
        return None
    with pfad.open("rb") as fh:
        kopf = fh.read(256)
    typ = binary_content_type(kopf)
    if not typ or not typ.startswith("image/"):
        return None
    return pfad, typ


def bild_noch_in_gebrauch(name: str, *, ausser_formular: str = "") -> bool:
    """Nutzt ein ANDERES Anmeldeformular die Datei noch?

    Ein Bild kann an mehreren Formularen haengen (gleicher Upload zweimal
    zugeordnet). Solange es irgendwo steht, darf die Datei nicht weg.
    """
    sauber = dateiname_aus_wert(name)
    if not sauber:
        return False

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldeformular

    with SessionLocal() as sess:
        treffer = sess.query(Anmeldeformular).filter(
            (Anmeldeformular.bannerbild == sauber)
            | (Anmeldeformular.hintergrundbild == sauber)
        )
        for form in treffer:
            if ausser_formular and form.name == ausser_formular:
                continue
            return True
    return False


def raeume_bild_auf(name, *, ausser_formular: str = "") -> bool:
    """Bilddatei + ``File``-Datensatz loeschen, wenn sie niemand mehr nutzt.

    Aufgerufen, wenn ein Bild vom Formular entfernt, ersetzt oder das Formular
    selbst geloescht wird (Operator-Review REG-1a, Punkt 1). Ohne diesen Schritt
    bleibt ein Bild ohne Formular als Datenrest liegen — bei einem Foto mit
    Personen ein DSGVO-Befund.

    ``ausser_formular`` ist das Formular, dessen Spalten GERADE geaendert
    werden: seine (noch nicht bestaetigte) Zuordnung darf nicht als „in
    Gebrauch“ gelten, sonst raeumt ein Ersetzen nie auf.

    Rueckgabe ``True``, wenn Datei und/oder Datensatz entfernt wurden.
    """
    sauber = dateiname_aus_wert(name)
    if not sauber:
        return False
    if bild_noch_in_gebrauch(sauber, ausser_formular=ausser_formular):
        return False

    entfernt = False
    pfad = _zielpfad(sauber)
    if pfad is not None and pfad.is_file():
        try:
            pfad.unlink()
            entfernt = True
        except OSError:
            # Aufraeumen darf den fachlichen Vorgang nicht scheitern lassen;
            # der Datensatz wird trotzdem entfernt (naechster Lauf raeumt nach).
            pass

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import FileModel

    with SessionLocal() as sess:
        zeilen = (
            sess.query(FileModel)
            .filter(FileModel.file_url.in_([f"/files/{sauber}", f"/private/files/{sauber}"]))
            .all()
        )
        for zeile in zeilen:
            sess.delete(zeile)
            entfernt = True
        if zeilen:
            sess.commit()
    return entfernt
