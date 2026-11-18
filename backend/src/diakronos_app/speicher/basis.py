"""Die EINE Schnittstelle der Datei-Ablage (SPEICHER-1) — Vertrag und Helfer.

Bis hierher griff jede Stelle der App selbst in ``settings.files_dir``: Fotos
(``frappe_core.upload_file``), Anmeldeformular-Bilder, Gemeinde-Logo,
Dev-Modus-Bilder/Audio/Bericht, DSGVO-Loeschung, Papierkorb, Sicherung. Damit
haette eine zweite Ablage (Nextcloud) an jeder dieser Stellen einzeln
eingebaut werden muessen — elf Mal dieselbe Verzweigung, elf Mal die
Moeglichkeit, sie zu vergessen.

Dieses Paket dreht das um: EINE Schnittstelle, zwei Umsetzungen, und alle
Aufrufer kennen nur noch Schluessel (relative Pfade, siehe ``schluessel.py``).

    from diakronos_app.speicher import hole_speicher

    speicher = hole_speicher()
    speicher.schreiben("devmodus/2026-10-15/a.png", b"...")
    if speicher.existiert("devmodus/2026-10-15/a.png"):
        with speicher.oeffnen("devmodus/2026-10-15/a.png") as quelle:
            kopf = quelle.lesen_vorn(12)

Der Vertrag
-----------
``schreiben(schluessel, daten)``
    Legt die Datei an bzw. ersetzt sie. Elternordner werden bei Bedarf
    erzeugt. ``ValueError`` bei ungueltigem Schluessel.
``oeffnen(schluessel)`` -> :class:`Quelle`
    Lese-Kontext: ``lesen_vorn(n)``, ``lesen_rest()``, ``ganz()``, ``strom()``.
    ``NichtGefunden``, wenn es die Datei nicht gibt.
``lesen(schluessel)`` -> ``bytes``
    Bequemlichkeit fuer kleine Dateien (alles, was ohnehin in den Speicher
    passt); intern ``oeffnen``.
``loeschen(schluessel)`` -> ``bool``
    ``True`` = war da und ist weg. Fehlende Datei ist KEIN Fehler (das
    Aufraeumen soll nie an einer schon geloeschten Datei scheitern).
``existiert(schluessel)`` -> ``bool``
``auflisten(praefix="")`` -> ``list[str]``
    Alle Schluessel unterhalb von ``praefix``, sortiert.
``groesse(schluessel)`` -> ``int`` | ``None``
    Bytes, ``None`` wenn nicht vorhanden.
``pfad(schluessel)`` -> ``Path`` | ``None``
    NUR fuer die lokale Ablage: der Dateipfad, damit ``FileResponse`` die
    Datei ohne Umweg ausliefern kann. ``Nextcloud`` gibt immer ``None`` —
    dort gibt es keinen lokalen Pfad. Wer ``pfad()`` benutzt, MUSS den
    ``None``-Fall bedienen (Herunterladen in eine temporaere Datei).
``gesundheit()`` -> ``dict``
    Kurzer Zustand fuer Statusseiten (Backend-Name, erreichbar ja/nein).

Was NICHT in den Vertrag gehoert
--------------------------------
Rechte. Wer eine Datei sehen darf, entscheidet weiter Diakronos
(``files.attachment_allowed``, ``devmodus.rechte`` …). Die Ablage kennt keine
Benutzer — und Nextcloud-Links gehen NIE an den Browser (Kartenvorgabe 4).
"""

from __future__ import annotations

import io
import re
from abc import ABC, abstractmethod
from typing import IO, Any, Iterable, Iterator

from diakronos_app.speicher.schluessel import (
    MAX_SCHLUESSEL,
    UngueltigerSchluessel,
    elternordner,
    ist_gueltig,
    normalisiere,
)

__all__ = [
    "MAX_SCHLUESSEL",
    "AblageFehler",
    "Basis",
    "NichtErlaubt",
    "NichtGefunden",
    "Quelle",
    "SpeicherNichtErreichbar",
    "UngueltigerSchluessel",
    "elternordner",
    "ist_gueltig",
    "normalisiere",
]

#: Blockgroesse beim Stromlesen/Schreiben. 256 KiB ist gross genug, dass
#: Netz und Platte nicht in 4-KiB-Haeppchen arbeiten, und klein genug, dass
#: ein 10-GB-Archiv den Speicher nicht fuellt.
BLOCKGROESSE = 256 * 1024


class AblageFehler(RuntimeError):
    """Oberklasse aller Fehler der Datei-Ablage.

    Die Aufrufer in Diakronos behandeln sie EINZELN und bewusst
    unterschiedlich („Logo fehlt“ -> Monogramm, „DSGVO-Datei weg“ -> weiter),
    deshalb keine gemeinsame Basis mit ``FrappeCompatError``: diese Ausnahmen
    sind keine API-Fehler, sondern Betriebszustaende.
    """

    #: Text fuer die Oberflaeche. NIE ein Pfad, nie ein Zugangsdatum.
    meldung = "Die Dateiablage ist nicht erreichbar."

    def __init__(self, meldung: str | None = None) -> None:
        super().__init__(meldung or self.meldung)


class NichtGefunden(AblageFehler):
    """Die Datei gibt es in dieser Ablage nicht."""

    meldung = "Die Datei ist nicht vorhanden."


class NichtErlaubt(AblageFehler):
    """Die Ablage hat den Zugriff verweigert (Zugangsdaten, Rechte)."""

    meldung = "Die Dateiablage hat den Zugriff verweigert."


class SpeicherNichtErreichbar(AblageFehler):
    """Zeitueberschreitung, Netzfehler, 5xx nach allen Wiederholungen."""

    meldung = "Die Dateiablage ist nicht erreichbar."


class Quelle(ABC):
    """Lese-Zugriff auf EINE Datei (Kontextmanager).

    Warum nicht einfach ein ``Path`` oder ``bytes``: die lokale Ablage liest
    von der Platte, die Nextcloud-Ablage ueber HTTP. Die Aufrufer wollen aber
    dasselbe tun — ein paar Kopfdaten schnueffeln (Magic-Bytes!), dann
    entscheiden, ob sie alles lesen, streamen oder nur die Datei ausliefern.
    Genau diese vier Faelle stehen hier, damit KEIN Aufrufer die Ablage
    umgeht, um doch wieder an einen Pfad zu kommen.

    ``lesen_vorn`` darf mehrfach aufgerufen werden und beginnt jedes Mal
    wieder vorn (das ist der Schnueffel-Fall: erst 12 Bytes, dann 4096, dann
    alles).
    """

    @abstractmethod
    def lesen_vorn(self, anzahl: int) -> bytes:
        """Die ersten ``anzahl`` Bytes (weniger, wenn die Datei kuerzer ist)."""

    @abstractmethod
    def lesen_rest(self) -> bytes:
        """Alles ab der aktuellen Leseposition."""

    @abstractmethod
    def strom(self) -> Iterable[bytes]:
        """Blöcke ab der aktuellen Leseposition (fuer grosse Dateien)."""

    def ganz(self) -> bytes:
        """Die ganze Datei (Position wird nicht vorausgesetzt)."""
        return self._ganz()

    @abstractmethod
    def _ganz(self) -> bytes:
        """Die ganze Datei — von den Umsetzungen geliefert."""

    @property
    @abstractmethod
    def groesse(self) -> int:
        """Groesse in Bytes (``-1`` = unbekannt)."""

    def schliessen(self) -> None:  # noqa: B027 — Vorgabe: nichts zu tun
        """Gibt Ressourcen frei. Idempotent."""

    def __enter__(self) -> "Quelle":
        return self

    def __exit__(self, *_: Any) -> None:
        self.schliessen()


class DateiQuelle(Quelle):
    """``Quelle`` fuer eine lokale Datei (``Lokal`` und der Umzug).

    Bewusst hier und nicht in ``lokal.py``: der Umzug liest aus der lokalen
    Ablage und schreibt in die andere — beide Seiten sollen dieselbe
    Leseform haben.
    """

    def __init__(self, datei: IO[bytes], groesse: int) -> None:
        self._datei = datei
        self._groesse = groesse

    def lesen_vorn(self, anzahl: int) -> bytes:
        if anzahl is None or anzahl < 0:
            return self._ganz()
        self._datei.seek(0)
        return self._datei.read(anzahl)

    def lesen_rest(self) -> bytes:
        return self._datei.read()

    def strom(self) -> Iterator[bytes]:
        while True:
            block = self._datei.read(BLOCKGROESSE)
            if not block:
                return
            yield block

    def _ganz(self) -> bytes:
        self._datei.seek(0)
        return self._datei.read()

    @property
    def groesse(self) -> int:
        return self._groesse

    def schliessen(self) -> None:
        try:
            self._datei.close()
        except OSError:  # pragma: no cover — Schliessen darf nie werfen
            pass


class BytesQuelle(Quelle):
    """``Quelle`` ueber bereits gelesene Bytes (Nextcloud: Antwortkoerper)."""

    def __init__(self, daten: bytes) -> None:
        self._puffer = io.BytesIO(daten)
        self._groesse = len(daten)

    def lesen_vorn(self, anzahl: int) -> bytes:
        if anzahl is None or anzahl < 0:
            return self._ganz()
        self._puffer.seek(0)
        return self._puffer.read(anzahl)

    def lesen_rest(self) -> bytes:
        return self._puffer.read()

    def strom(self) -> Iterator[bytes]:
        while True:
            block = self._puffer.read(BLOCKGROESSE)
            if not block:
                return
            yield block

    def _ganz(self) -> bytes:
        self._puffer.seek(0)
        return self._puffer.read()

    @property
    def groesse(self) -> int:
        return self._groesse


class Basis(ABC):
    """Die Schnittstelle. Zwei Umsetzungen: ``Lokal`` und ``Nextcloud``.

    Keine der Methoden kennt Benutzer oder Rechte — die Ablage ist ein
    Speicher, keine Freigabe. Und keine gibt eine Adresse nach aussen.
    """

    #: Name fuer Protokoll und Statusanzeige (``"lokal"``/``"nextcloud"``).
    name: str = "basis"

    # ── Schreiben ──────────────────────────────────────────────────────────
    @abstractmethod
    def schreiben(self, schluessel: str, daten: bytes | IO[bytes]) -> int:
        """Datei anlegen/ersetzen. Rueckgabe: geschriebene Bytes."""

    # ── Lesen ──────────────────────────────────────────────────────────────
    @abstractmethod
    def oeffnen(self, schluessel: str) -> Quelle:
        """Lese-Kontext oeffnen (``NichtGefunden``, wenn es sie nicht gibt)."""

    def lesen(self, schluessel: str) -> bytes:
        """Die ganze Datei als ``bytes``."""
        with self.oeffnen(schluessel) as quelle:
            return quelle.ganz()

    def lesen_vorn(self, schluessel: str, anzahl: int) -> bytes | None:
        """Die ersten ``anzahl`` Bytes — OHNE die ganze Datei zu uebertragen.

        Fuer das Typ-Schnueffeln (Magic-Bytes): der Aufrufer will 4096 Bytes
        sehen, nicht eine 500-MB-Audiodatei. ``None`` heisst „gibt es nicht“.

        Die Vorgabe hier ist der ehrliche Weg ueber :meth:`oeffnen` (Abbruch
        nach ``anzahl`` Bytes, danach ``schliessen``); ``Nextcloud``
        ueberschreibt sie mit einem gestreamten ``GET`` samt ``Range``, damit
        auch der ANFANG nicht mehr kostet als der Ausschnitt.
        """
        try:
            with self.oeffnen(schluessel) as quelle:
                return quelle.lesen_vorn(anzahl)
        except NichtGefunden:
            return None

    @abstractmethod
    def existiert(self, schluessel: str) -> bool:
        """Gibt es die Datei?"""

    @abstractmethod
    def groesse(self, schluessel: str) -> int | None:
        """Groesse in Bytes — ``None``, wenn es die Datei nicht gibt."""

    @abstractmethod
    def auflisten(self, praefix: str = "") -> list[str]:
        """Alle Schluessel unterhalb von ``praefix``, sortiert."""

    # ── Loeschen ───────────────────────────────────────────────────────────
    @abstractmethod
    def loeschen(self, schluessel: str) -> bool:
        """Datei entfernen. ``True`` = war da. Fehlende Datei: ``False``."""

    # ── Sonderfaelle ───────────────────────────────────────────────────────
    def pfad(self, schluessel: str) -> Any:
        """Lokaler Dateipfad — nur ``Lokal`` kann das. Sonst ``None``."""
        return None

    def strom(
        self,
        schluessel: str,
        *,
        von: int = 0,
        bis: int | None = None,
        bereich: bool | None = None,
        gesamt: int | None = None,
    ) -> tuple[Iterable[bytes], int, int]:
        """Blockweise ausliefern OHNE die ganze Datei im Speicher: ``(bloecke, von, bis)``.

        Fuer die Auslieferung an den Browser (Kartenvorgabe 4: das Ausliefern
        bleibt bei Diakronos). ``von``/``bis`` sind INKLUSIV, wie der
        HTTP-``Range``-Kopf (``bytes=100-199`` -> ``von=100, bis=199``).

        ``bereich=False`` heisst „der Client hat KEINEN Bereich verlangt“;
        ``Nextcloud`` schickt dann keinen ``Range``-Kopf an WebDAV
        (Review-Punkt 8). ``None`` = aus ``von``/``bis`` ableiten.

        ``gesamt`` ist die bereits bekannte Dateigroesse (aus
        ``groesse_und_bereich``); ``Nextcloud`` braucht sie, wenn die
        GET-Antwort keine ``Content-Length`` traegt (chunked) — Review Runde
        4, Punkt 3. ``Lokal`` liest ohnehin von der Platte.

        Vorgabe fuer beide Umsetzungen: die Datei wird geoeffnet und in
        ``BLOCKGROESSE``-Stuecken geliefert — bei ``Lokal`` von der Platte,
        bei ``Nextcloud`` aus dem HTTP-Strom der WebDAV-Antwort. Nichts davon
        haelt die Datei komplett im Speicher (das war der Befund: eine Datei
        ueber ``max_upload_bytes_audio`` wurde still abgeschnitten).
        """
        with self.oeffnen(schluessel) as quelle:
            daten = quelle.ganz()
        gesamt = len(daten)
        anfang = max(0, int(von or 0))
        ende = gesamt - 1 if bis is None else min(int(bis), gesamt - 1)

        def bloecke() -> Iterator[bytes]:
            position = anfang
            while position <= ende:
                stueck = daten[position : min(position + BLOCKGROESSE, ende + 1)]
                if not stueck:
                    return
                yield stueck
                position += len(stueck)

        if ende < anfang:
            # Leere Datei oder Bereich hinter dem Ende: NICHTS liefern.
            return iter(()), anfang, -1
        return bloecke(), anfang, ende

    def groesse_und_bereich(
        self, schluessel: str, bereich: str | None
    ) -> tuple[int, int, int]:
        """``(gesamt, von, bis)`` fuer einen ``Range``-Kopf (``bis`` inklusiv).

        Ohne Bereich: ``(gesamt, 0, gesamt - 1)``. Ein ``bytes=``-Bereich wird
        nach RFC 9110 ausgewertet. **Ungueltig** (fremde Einheit,
        Mehrfachbereich, Muell) heisst „nicht unterstuetzt“ -> die GANZE
        Datei mit 200. **Unerfuellbar** (syntaktisch gueltiger Einzelbereich
        hinter dem Dateiende, leere Datei) ergibt ``(gesamt, 0, -1)`` — der
        Aufrufer antwortet dann mit 416.
        """
        gesamt = self.groesse(schluessel)
        if gesamt is None:
            raise werfe_nicht_gefunden(self.pruefe(schluessel))
        if gesamt <= 0:
            # Eine leere Datei hat 0 Bytes: ohne Range ein 200 mit 0 Bytes
            # (``files._aus_der_ablage``), mit Range ist JEDER Bereich
            # unerfuellbar (416 mit ``*/0``).
            return 0, 0, -1
        if not bereich:
            return gesamt, 0, gesamt - 1
        if not bereich_syntax(bereich):
            # Nicht unterstuetzt: RFC 9110 (14.2) erlaubt, den Range zu
            # ignorieren — die GANZE Datei, 200, kein 416.
            return gesamt, 0, gesamt - 1
        _, von, bis = _parse_bereich(bereich, gesamt)
        return gesamt, von, bis

    def temporaerdatei(self, schluessel: str) -> tuple[Any, bool]:
        """Eine lokale Datei mit dem Inhalt dieses Schluessels — ``(Pfad, kopiert)``.

        Fuer Aufrufer, die zwingend einen Dateipfad brauchen (Auslieferung
        ueber ``FileResponse``) und NICHT wissen, welche Ablage laeuft. Ist
        die Ablage lokal, wird nichts kopiert: es kommt direkt der Pfad
        zurueck (``kopiert=False``). Sonst liegt der Inhalt in einer
        temporaeren Datei (``kopiert=True``) — die MUSS der Aufrufer nach
        dem Senden loeschen (``finally``).

        Der Umweg ueber eine Kopie ist Absicht: die Alternative waere, dass
        jede Ausliefer-Stelle wieder selbst an der Ablage vorbei einen Pfad
        baut — genau der Zustand, den diese Karte beendet.
        """
        direkt = self.pfad(schluessel)
        if direkt is not None:
            return direkt, False
        import os
        import tempfile

        with self.oeffnen(schluessel) as quelle:
            fd, name = tempfile.mkstemp(prefix="diakronos-ablage-", suffix=".teil")
            try:
                with os.fdopen(fd, "wb") as fh:
                    for block in quelle.strom():
                        fh.write(block)
            except OSError:
                os.unlink(name)
                raise
        return name, True

    @abstractmethod
    def gesundheit(self) -> dict[str, Any]:
        """Kurzer Zustand: ``{"backend": ..., "erreichbar": bool, ...}``."""

    # ── gemeinsam genutzte Vorpruefung ─────────────────────────────────────
    @staticmethod
    def pruefe(schluessel: str) -> str:
        """Schluessel pruefen und kanonisch zurueckgeben (``UngueltigerSchluessel``)."""
        return normalisiere(schluessel)

    def __repr__(self) -> str:  # pragma: no cover — Diagnose
        return f"<{type(self).__name__} {self.name}>"


def werfe_nicht_gefunden(name: str) -> NichtGefunden:
    """Einheitlicher „gibt's nicht“-Fehler (ohne Pfad, ohne Interna)."""
    return NichtGefunden(f"Die Datei {name!r} ist in der Ablage nicht vorhanden.")


#: Ein ``Range``-Kopf, wie ihn Browser fuer Audio schicken: ``bytes=a-b``,
#: ``bytes=a-`` (ab a bis Ende) oder ``bytes=-n`` (die letzten n Bytes).
_BEREICH = re.compile(r"^\s*bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$", re.IGNORECASE)


def bereich_syntax(bereich: str) -> bool:
    """Ist das ein ``bytes=``-EINZELbereich, den wir bedienen koennen?

    Reine SYNTAX-Pruefung, ohne Dateigroesse: ``bytes=5-9`` ist gueltig, auch
    wenn die Datei kuerzer ist. ``bytes=0-0,5-9`` (Mehrfachbereich),
    ``items=0-5`` (fremde Einheit) und ``bytes=abc`` sind es nicht — die
    werden ignoriert (ganze Datei, 200).
    """
    treffer = _BEREICH.match(str(bereich or ""))
    if not treffer:
        return False
    anfang, ende = treffer.group(1), treffer.group(2)
    if not anfang and not ende:
        return False
    if not anfang:
        return int(ende) > 0
    return not ende or int(ende) >= int(anfang)


def _parse_bereich(bereich: str, gesamt: int) -> tuple[str, int, int]:
    """``Range``-Kopf -> ``(art, von, bis)`` inklusiv.

    ``art`` ist ``"gueltig"`` (``von``/``bis`` gelten) oder ``"ungueltig"``
    (``(0, -1)``). Ein **ungueltiger** Kopf ist etwas anderes als ein
    **unerfuellbarer**: ``bytes=0-0,5-9`` (Mehrfachbereich), ``items=0-5``
    (fremde Einheit) und ``bytes=abc`` koennen wir nicht bedienen — dann gilt
    ``Ignore-Range`` (ganze Datei, 200, RFC 9110, 14.2). 416 gibt es nur fuer
    einen syntaktisch gueltigen EINZELbereich, der hinter dem Dateiende
    liegt (``bytes=100-`` bei 100 Bytes) oder fuer eine leere Datei.
    """
    treffer = _BEREICH.match(str(bereich or ""))
    if not treffer or gesamt <= 0:
        return "ungueltig", 0, -1
    anfang, ende = treffer.group(1), treffer.group(2)
    if not anfang and not ende:
        return "ungueltig", 0, -1
    if not anfang:
        # ``bytes=-n``: die LETZTEN n Bytes.
        anzahl = int(ende)
        if anzahl <= 0:
            return "ungueltig", 0, -1
        return "gueltig", max(0, gesamt - anzahl), gesamt - 1
    von = int(anfang)
    if von >= gesamt:
        # Syntaktisch in Ordnung, aber hinter dem Dateiende -> 416.
        return "gueltig", 0, -1
    if not ende:
        return "gueltig", von, gesamt - 1
    bis = int(ende)
    if bis < von:
        return "gueltig", 0, -1
    return "gueltig", von, min(bis, gesamt - 1)
