"""``Lokal`` — die Ablage im Dateisystem, byte-gleich wie bisher (SPEICHER-1).

Was hier steht, ist KEINE neue Ablage: es ist genau das Verhalten, das die
App heute in elf Dateien einzeln hat — ``open(path, "wb")`` unter
``settings.files_dir``, Symbole und Pfad-Ausbrueche abweisen, Ordner bei
Bedarf anlegen. Nur eben an EINER Stelle und hinter dem Vertrag aus
``basis.py``.

Warum ``resolve()`` und der Eltern-Vergleich (und nicht nur ein Prefix)
------------------------------------------------------------------------
Ein Praefix-Vergleich (``str(pfad).startswith(str(wurzel))``) haelt
``/data/files-alt/x`` fuer „innerhalb“ von ``/data/files``. Der Vergleich des
AUFGELOESTEN Elternordners ist strenger und faengt zusaetzlich Symlinks ab:
ein Link INNERHALB der Wurzel, der nach draussen zeigt, hat nach
``resolve()`` einen Elternordner ausserhalb.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import IO, Any

from diakronos_app.speicher.basis import (
    BLOCKGROESSE,
    Basis,
    DateiQuelle,
    Quelle,
    SpeicherNichtErreichbar,
    werfe_nicht_gefunden,
)
from diakronos_app.speicher.schluessel import UngueltigerSchluessel, normalisiere

__all__ = ["Lokal"]

#: Die UMASK des Prozesses, EINMAL beim Laden gelesen (Review Runde 4,
#: Punkt 6). Vorher stand hier je Schreibvorgang ein Paar
#: ``os.umask(0)``/``os.umask(alt)`` — systemweit und damit ein Wettlauf:
#: ein zweiter Thread legte in diesem Fenster seine Datei mit umask 0 an
#: (also 0666). ``os.umask`` ist der einzige Weg, die Maske zu LESEN; ihn
#: einmal zu benutzen ist der kleinste Eingriff.
_UMASK = os.umask(0)
os.umask(_UMASK)


class Lokal(Basis):
    """Dateisystem unterhalb ``wurzel`` (im Betrieb ``settings.files_dir``).

    ``wurzel`` wird bei jedem Zugriff neu aufgeloest: Tests und der
    Umzug zeigen ``settings.files_dir`` um, und ein einmal gemerkter Pfad
    waere dann falsch. Der Aufwand ist ein ``realpath`` je Aufruf.
    """

    name = "lokal"

    def __init__(self, wurzel: str | os.PathLike[str] | None = None) -> None:
        self._wurzel_roh = None if wurzel is None else Path(wurzel)

    # ── Wurzel ─────────────────────────────────────────────────────────────
    def _wurzel(self) -> Path:
        """Die Wurzel, aufgeloest. Holt sie bei Bedarf aus den Einstellungen."""
        roh = self._wurzel_roh
        if roh is None:
            from diakronos_app.settings import settings

            roh = Path(settings.files_dir)
        return Path(roh).resolve()

    def _ziel(self, schluessel: str) -> Path:
        """Schluessel -> Pfad INNERHALB der Wurzel.

        Drei Schranken, alle VOR dem Zugriff:

        1. ``normalisiere`` — kein absoluter Pfad, kein ``..``, kein
           Steuerzeichen (``UngueltigerSchluessel``, ein Programmierfehler).
        2. **Kein Symlink auf dem Weg** — weder die Datei selbst noch ein
           Elternordner unterhalb der Wurzel. ``main`` hat JEDEN Symlink
           abgewiesen (``files.stored_path``, ``formularbilder._zielpfad``,
           ``dsgvo.dateien_entfernen``); ohne diese Pruefung loeste
           ``resolve()`` einen Link auf und die Ablage lieferte — schlimmer —
           LOESCHTE die Datei dahinter.
        3. Der aufgeloeste Pfad liegt unter der Wurzel (sonst
           ``UngueltigerSchluessel``, Review-Punkt 6: das ist ein Fehler des
           Aufrufers, kein Betriebszustand).
        """
        sauber = normalisiere(schluessel)
        wurzel = self._wurzel()
        roh = wurzel / sauber
        if self._hat_symlink(roh, wurzel):
            # Ein Verweis ist ein ZUSTAND der Ablage (jemand hat einen Link
            # hineingelegt), kein Programmierfehler des Aufrufers — deshalb
            # ``AblageFehler`` und nicht ``UngueltigerSchluessel``. Der
            # Aufrufer behandelt „nicht auslieferbar“ einheitlich.
            raise SpeicherNichtErreichbar(
                "Der Pfad fuehrt ueber einen Verweis aus der Ablage heraus."
            )
        ziel = roh.resolve()
        if ziel != wurzel and wurzel not in ziel.parents:
            # Dagegen ein Schluessel, der aus der Wurzel herausrechnet: das
            # kann nur ein Fehler im Aufrufer sein (Review-Punkt 6).
            raise UngueltigerSchluessel(
                "Der Dateipfad liegt ausserhalb der Ablage."
            )
        return ziel

    @staticmethod
    def _hat_symlink(pfad: Path, wurzel: Path) -> bool:
        """True, wenn ``pfad`` oder ein Ordner darunter (bis zur Wurzel) ein Link ist.

        ``is_symlink()`` fragt das Pfadstueck SELBST ab, ohne ihm zu folgen —
        genau das ist noetig, um einen Link zu erkennen, bevor ``resolve()``
        ihn aufloest. Geprueft wird von der Wurzel abwaerts, damit ein Link
        OBERHALB der Wurzel (der Betreiber hat ``files_dir`` dorthin gelegt)
        nicht die ganze Ablage sperrt.
        """
        if wurzel not in pfad.parents:
            return False
        teile = pfad.relative_to(wurzel).parts
        aktuell = wurzel
        for teil in teile:
            aktuell = aktuell / teil
            try:
                if aktuell.is_symlink():
                    return True
            except OSError:  # pragma: no cover — kaputter Pfad
                return True
        return False

    def wurzel(self) -> Path:
        """Die Wurzel selbst (nur fuer Diagnose/Umzug, nie an Nutzer geben)."""
        return self._wurzel()

    # ── Schreiben ──────────────────────────────────────────────────────────
    def schreiben(self, schluessel: str, daten: bytes | IO[bytes]) -> int:
        """Schreibt atomar: erst ``.<name>.teil-XXXX``, dann ``os.replace``.

        Das ist seit jeher das Verhalten des Logo-Uploads (tmp + ``fsync`` +
        ``os.replace``) und gilt jetzt fuer JEDE Datei dieser Ablage: ein
        Abbruch hinterlaesst nie ein halbes Ziel, ein Leser sieht entweder die
        alte oder die neue Fassung. Der ``.teil``-Name passt auf keinen
        Dateinamen-Filter der App und wird auch vom Umzug uebersprungen.

        Der Temp-Name kommt aus ``tempfile.mkstemp`` (Review-Punkt 4): der
        fruehere Name ``.<name>.teil-<pid>`` war JE PROZESS derselbe, also
        schrieben zwei Threads mit derselben Datei in dieselbe Temp-Datei —
        gemischte Bytes oder ``FileNotFoundError`` beim zweiten ``replace``.

        Aufgeraeumt wird in ``finally`` fuer **jeden** Abbruch (Review-Punkt
        5): vorher blieb bei ``ValueError``/``KeyboardInterrupt``/einem Fehler
        der Quelle die ``.teil``-Datei liegen.
        """
        ziel = self._ziel(schluessel)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{ziel.name}.teil-", dir=str(ziel.parent))
        teil = Path(name)
        geschrieben = 0
        ersetzt = False
        try:
            # ``mkstemp`` legt die Datei mit 0600 an. ``open(..., "wb")`` haette
            # die Rechte aus der UMASK genommen (ueblicherweise 0644) — die
            # Ablage soll byte- UND rechtegleich zu ``main`` bleiben, sonst
            # koennte z. B. ein zweiter Dienst die Dateien nicht mehr lesen.
            # Die Maske wird beim Modulladen EINMAL gelesen (``_UMASK``):
            # ``os.umask`` gilt prozessweit, ein Aufruf hier waere ein
            # Wettlauf mit jedem anderen Thread.
            os.chmod(teil, 0o666 & ~_UMASK)
            with os.fdopen(fd, "wb") as fh:
                if isinstance(daten, (bytes, bytearray, memoryview)):
                    roh = bytes(daten)
                    fh.write(roh)
                    geschrieben = len(roh)
                else:
                    while True:
                        block = daten.read(BLOCKGROESSE)
                        if not block:
                            break
                        fh.write(block)
                        geschrieben += len(block)
                # Erst auf die Platte, dann umbenennen: ohne ``fsync`` steht
                # nach einem Stromausfall moeglicherweise eine leere Datei
                # unter dem richtigen Namen.
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(teil, ziel)
            ersetzt = True
        except OSError as fehler:
            raise SpeicherNichtErreichbar(
                f"Die Datei konnte nicht geschrieben werden ({type(fehler).__name__})."
            ) from fehler
        finally:
            if not ersetzt:
                # BaseException-sicher: auch ValueError, KeyboardInterrupt
                # und ein Fehler der Quelle raeumen ihre Temp-Datei weg.
                try:
                    teil.unlink(missing_ok=True)
                except OSError:  # pragma: no cover — Aufraeumen darf nie werfen
                    pass
        return geschrieben

    # ── Lesen ──────────────────────────────────────────────────────────────
    def oeffnen(self, schluessel: str) -> Quelle:
        ziel = self._ziel(schluessel)
        if not ziel.is_file():
            raise werfe_nicht_gefunden(normalisiere(schluessel))
        try:
            datei = open(ziel, "rb")  # noqa: PTH123
        except OSError as fehler:
            raise SpeicherNichtErreichbar(
                f"Die Datei konnte nicht gelesen werden ({type(fehler).__name__})."
            ) from fehler
        return DateiQuelle(datei, ziel.stat().st_size)

    def existiert(self, schluessel: str) -> bool:
        # Ein BOESER Schluessel bleibt ein Fehler (UngueltigerSchluessel);
        # nur „nicht erreichbar/ausserhalb“ wird zu ``False``.
        try:
            return self._da(self._ziel(schluessel))
        except SpeicherNichtErreichbar:
            return False

    @staticmethod
    def _da(ziel: Path) -> bool:
        """True, wenn ``ziel`` eine echte Datei ist (kein Ordner, kein Link)."""
        try:
            return ziel.is_file() and not ziel.is_symlink()
        except OSError:  # pragma: no cover — kaputter Eintrag
            return False

    def groesse(self, schluessel: str) -> int | None:
        ziel = self._ziel(schluessel)
        try:
            return ziel.stat().st_size if self._da(ziel) else None
        except OSError:
            return None

    def auflisten(self, praefix: str = "") -> list[str]:
        wurzel = self._wurzel()
        start = wurzel if not praefix.strip("/") else self._dir(praefix)
        if start is None or not start.is_dir():
            return []
        ergebnis: list[str] = []
        for eintrag in sorted(start.rglob("*")):
            # ``.teil-*``-Reste eines abgebrochenen Schreibens sind keine
            # Dateien der Ablage (und ein Symlink auch nicht).
            if eintrag.is_symlink() or not eintrag.is_file():
                continue
            if eintrag.name.startswith(".teil") or ".teil-" in eintrag.name:
                continue
            try:
                ergebnis.append(eintrag.relative_to(wurzel).as_posix())
            except ValueError:  # pragma: no cover — Symlink nach draussen
                continue
        return ergebnis

    def _dir(self, praefix: str) -> Path | None:
        try:
            return self._ziel(praefix)
        except Exception:  # noqa: BLE001 — ungueltiges Praefix = nichts
            return None

    # ── Loeschen ───────────────────────────────────────────────────────────
    def loeschen(self, schluessel: str) -> bool:
        try:
            ziel = self._ziel(schluessel)
        except SpeicherNichtErreichbar:
            return False
        # Ein Symlink wird NICHT geloescht: ``unlink`` traefe zwar den Link
        # selbst, aber die Ablage kennt ihn nicht als Datei (``main`` wies
        # jeden Link ab) — und wer ihn angelegt hat, raeumt ihn auf.
        if not self._da(ziel):
            return False
        try:
            ziel.unlink()
        except OSError:
            return False
        return True

    # ── Sonderfaelle ───────────────────────────────────────────────────────
    def pfad(self, schluessel: str) -> Path | None:
        try:
            ziel = self._ziel(schluessel)
        except SpeicherNichtErreichbar:
            # Ein Verweis ist „hier ist keine Datei“ — nicht ein Fehler der
            # Abfrage (``stored_path``/``_zielpfad`` erwarten ``None``).
            return None
        return ziel if self._da(ziel) else None

    # ── Zustand ────────────────────────────────────────────────────────────
    def gesundheit(self) -> dict[str, Any]:
        wurzel = self._wurzel()
        schreibbar = False
        try:
            wurzel.mkdir(parents=True, exist_ok=True)
            probe = wurzel / f".schreibprobe-{os.getpid()}"
            probe.write_bytes(b"")
            probe.unlink(missing_ok=True)
            schreibbar = True
        except OSError:
            schreibbar = False
        frei = None
        try:
            frei = shutil.disk_usage(wurzel).free
        except OSError:
            frei = None
        return {
            "backend": self.name,
            "erreichbar": wurzel.is_dir(),
            "schreibbar": schreibbar,
            "frei": frei,
        }
