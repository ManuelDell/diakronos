"""Umzug der Datei-Ablage (SPEICHER-1).

    python -m diakronos_app.speicher.umzug --nach nextcloud [--probelauf]

Was passiert
------------
Jede Datei der QUELLE wird in die ZIEL-Ablage kopiert, danach werden Groesse
UND SHA-256 verglichen (Rueckweg: aus dem Ziel gelesen, nicht aus der Quelle —
sonst pruefte man die Quelle gegen sich selbst). Nur uebereinstimmende Dateien
zaehlen als „uebertragen“.

Was NICHT passiert
------------------
**Es wird nichts geloescht.** Nach dem Umzug liegen die Dateien an beiden
Orten; erst wenn eine Abnahme in der Oberflaeche stimmt, entfernt der
Betreiber das lokale Volume (bzw. laesst es als Rueckfallebene stehen). Ein
Werkzeug, das im Zweifel loescht, ist bei Personendaten das falsche Werkzeug —
und Rueckgaengig gibt es nach einem Loeschvorgang keinen.

EBENSO NICHT: Es wird nichts in der Datenbank geaendert. Die `File`-Zeilen
tragen weiter `/files/<name>`; welche Bytes das sind, entscheidet allein die
Einstellung `SPEICHER_BACKEND`.

``--probelauf``
---------------
Liest und prueft alles, schreibt NICHTS ins Ziel (kein MKCOL, kein PUT, keine
Datei). Genau das ist die Abnahme vor dem Umzug: „was wuerde passieren, und
stimmt die Verbindung?“

Aufruf im Container::

    docker compose exec app python -m diakronos_app.speicher.umzug \\
        --nach nextcloud --probelauf

Der Rueckgabewert ist exit-Code 0 (alles uebertragen), 1 (Fehler bei
mindestens einer Datei), 2 (Aufruffehler/Einstellung fehlt).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass, field
from typing import Callable, Iterable

from diakronos_app.speicher.basis import (
    BLOCKGROESSE,
    AblageFehler,
    Basis,
    NichtGefunden,
    UngueltigerSchluessel,
)

__all__ = ["Ergebnis", "umzug", "main"]

#: Ziele, die dieses Werkzeug kennt. „lokal“ ist absichtlich dabei: der
#: Rueckweg (Nextcloud -> lokal) ist derselbe Vorgang mit getauschten Seiten.
ZIELE = ("lokal", "nextcloud")


@dataclass
class Ergebnis:
    """Was der Lauf getan hat (und was nicht)."""

    probelauf: bool = False
    quelle: str = ""
    ziel: str = ""
    #: Anzahl Dateien, deren Groesse UND Pruefsumme im Ziel stimmen.
    uebertragen: int = 0
    #: Anzahl Dateien, die im Ziel schon identisch vorlagen (nicht geschrieben).
    vorhanden: int = 0
    #: Dateien, bei denen etwas schiefging: (schluessel, grund).
    fehler: list[tuple[str, str]] = field(default_factory=list)
    #: Dateien, die im Probelauf uebertragen WUERDEN.
    geplant: list[str] = field(default_factory=list)

    @property
    def erfolgreich(self) -> bool:
        return not self.fehler

    def zeilen(self) -> list[str]:
        """Kurzbericht fuer die Ausgabe (ohne Pfade, ohne Zugangsdaten)."""
        art = "Probelauf" if self.probelauf else "Umzug"
        zeilen = [
            f"{art}: {self.quelle} -> {self.ziel}",
            f"  uebertragen: {self.uebertragen}",
            f"  bereits vorhanden (identisch): {self.vorhanden}",
        ]
        if self.probelauf:
            zeilen.append(f"  wuerde uebertragen: {len(self.geplant)}")
        zeilen.append(f"  fehler: {len(self.fehler)}")
        for schluessel, grund in self.fehler[:20]:
            zeilen.append(f"    - {schluessel}: {grund}")
        if len(self.fehler) > 20:
            zeilen.append(f"    … und {len(self.fehler) - 20} weitere")
        if not self.probelauf:
            zeilen.append("  Es wurde NICHTS geloescht (Quelle bleibt bestehen).")
        return zeilen


def _pruefsumme(ablage: Basis, schluessel: str) -> tuple[str, int]:
    """SHA-256 und Groesse einer Datei in der Ablage (blockweise gelesen)."""
    summe = hashlib.sha256()
    anzahl = 0
    with ablage.oeffnen(schluessel) as quelle:
        for block in quelle.strom():
            summe.update(block)
            anzahl += len(block)
    return summe.hexdigest(), anzahl


#: Endungen/Namen, die KEINE Dateien der Ablage sind: Reste eines
#: abgebrochenen Schreibens (``.name.teil-<pid>``) und die Schreibprobe der
#: Gesundheitspruefung. Sie gehoeren nicht in ein Ziel.
_RESTE = (".teil-",)


def _ist_rest(schluessel: str) -> bool:
    """True fuer Zwischenstaende, die nicht umgezogen werden."""
    name = schluessel.rsplit("/", 1)[-1]
    if name.startswith(".schreibprobe"):
        return True
    return any(teil in name for teil in _RESTE)


def umzug(
    quelle: Basis,
    ziel: Basis,
    *,
    probelauf: bool = False,
    praefix: str = "",
    bericht: Callable[[str], None] | None = None,
) -> Ergebnis:
    """Kopiert alle Dateien von ``quelle`` nach ``ziel`` (ohne Loeschen).

    Geprueft wird je Datei: Groesse UND SHA-256, gelesen aus dem ZIEL. Eine
    Datei, die schon identisch im Ziel liegt, wird NICHT erneut geschrieben
    (der Lauf ist damit wiederholbar: ein Abbruch nach 900 von 1000 Dateien
    setzt beim naechsten Mal bei den restlichen 100 an).

    Eine Datei, deren SCHLUESSEL die Ablage nicht annimmt (``UngueltigerSchluessel``
    — z. B. ein Altbestand mit ``..`` oder ein absoluter Pfad), wird als Fehler
    DIESER Datei gemeldet und uebersprungen: ein einzelner kaputter Eintrag
    darf den Umzug der anderen 999 nicht verhindern (Review-Punkt 9).
    """
    ergebnis = Ergebnis(probelauf=probelauf, quelle=quelle.name, ziel=ziel.name)
    melde = bericht or (lambda _text: None)

    try:
        schluessel_liste: Iterable[str] = quelle.auflisten(praefix)
    except AblageFehler as fehler:
        ergebnis.fehler.append((praefix or "/", str(fehler)))
        return ergebnis

    for schluessel in schluessel_liste:
        if _ist_rest(schluessel):
            # Reste eines abgebrochenen Schreibens / die Schreibprobe.
            melde(f"- {schluessel} (Zwischenstand, uebersprungen)")
            continue
        try:
            summe_quelle, groesse_quelle = _pruefsumme(quelle, schluessel)
        except UngueltigerSchluessel:
            ergebnis.fehler.append(
                (str(schluessel), "Ungueltiger Schluessel (uebersprungen)")
            )
            continue
        except (AblageFehler, OSError) as fehler:
            ergebnis.fehler.append((schluessel, f"Quelle nicht lesbar ({type(fehler).__name__})"))
            continue

        # Liegt die Datei im Ziel schon identisch vor? Dann nichts tun.
        try:
            if ziel.existiert(schluessel):
                summe_ziel, groesse_ziel = _pruefsumme(ziel, schluessel)
                if summe_ziel == summe_quelle and groesse_ziel == groesse_quelle:
                    ergebnis.vorhanden += 1
                    melde(f"= {schluessel}")
                    continue
        except NichtGefunden:
            pass
        except UngueltigerSchluessel:
            ergebnis.fehler.append(
                (str(schluessel), "Ungueltiger Schluessel (uebersprungen)")
            )
            continue
        except AblageFehler as fehler:
            # Ziel nicht erreichbar ist ein Abbruchgrund fuer DIESE Datei,
            # aber nicht fuer den Lauf: der Bericht zaehlt alle Fehler.
            ergebnis.fehler.append((schluessel, str(fehler)))
            continue

        if probelauf:
            ergebnis.geplant.append(schluessel)
            ergebnis.uebertragen += 1
            melde(f"? {schluessel} ({groesse_quelle} Bytes)")
            continue

        try:
            # Frisches Leseobjekt: ``_pruefsumme`` oben hat schon eines
            # verbraucht, und ``lesen_rest`` setzt an der aktuellen Position an.
            with quelle.oeffnen(schluessel) as quelle_datei:
                ziel.schreiben(schluessel, quelle_datei.lesen_rest())
            summe_ziel, groesse_ziel = _pruefsumme(ziel, schluessel)
        except UngueltigerSchluessel:
            ergebnis.fehler.append(
                (str(schluessel), "Ungueltiger Schluessel (uebersprungen)")
            )
            continue
        except (AblageFehler, OSError) as fehler:
            ergebnis.fehler.append((schluessel, f"Schreiben fehlgeschlagen ({type(fehler).__name__})"))
            continue

        if summe_ziel != summe_quelle or groesse_ziel != groesse_quelle:
            ergebnis.fehler.append(
                (schluessel, "Pruefsumme/Groesse weicht ab")
            )
            continue
        ergebnis.uebertragen += 1
        melde(f"+ {schluessel} ({groesse_quelle} Bytes, sha256 {summe_quelle[:12]}…)")

    return ergebnis


def _ablage_fuer(name: str) -> Basis:
    """Die Ablage zu einem Namen (``lokal`` oder ``nextcloud``)."""
    from diakronos_app.settings import settings

    if name == "lokal":
        from diakronos_app.speicher.lokal import Lokal

        return Lokal(settings.files_dir)
    if name == "nextcloud":
        from diakronos_app.speicher.nextcloud import Nextcloud, NextcloudZugang

        zugang = NextcloudZugang(
            settings.nextcloud_url,
            settings.nextcloud_benutzer,
            settings.nextcloud_app_passwort_effektiv,
            settings.nextcloud_ordner,
            timeout=settings.nextcloud_timeout_sekunden,
            transfer_timeout=settings.nextcloud_transfer_timeout_sekunden,
            versuche=settings.nextcloud_versuche,
        )
        fehlt = zugang.fehlende_angaben()
        if fehlt:
            raise AblageFehler(
                "Die Nextcloud ist nicht eingerichtet (fehlt: " + ", ".join(fehlt) + ")."
            )
        return Nextcloud(zugang)
    raise AblageFehler(f"Unbekannte Ablage {name!r} (erlaubt: {', '.join(ZIELE)}).")


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstieg (``python -m diakronos_app.speicher.umzug``)."""
    parser = argparse.ArgumentParser(
        prog="python -m diakronos_app.speicher.umzug",
        description=(
            "Dateien zwischen den Ablagen kopieren (lokal <-> Nextcloud). "
            "Es wird NICHTS geloescht."
        ),
    )
    parser.add_argument("--nach", required=True, choices=ZIELE,
                        help="Ziel-Ablage.")
    parser.add_argument("--von", default=None, choices=ZIELE,
                        help="Quell-Ablage (Default: die andere).")
    parser.add_argument("--probelauf", action="store_true",
                        help="Nur lesen und pruefen, nichts schreiben.")
    parser.add_argument("--pfad", default="",
                        help="Nur diesen Ordner umziehen (Schluessel-Praefix).")
    parser.add_argument("--still", action="store_true",
                        help="Nur die Zusammenfassung ausgeben.")
    args = parser.parse_args(argv)

    von = args.von or ("lokal" if args.nach == "nextcloud" else "nextcloud")
    if von == args.nach:
        print("Quelle und Ziel sind gleich — nichts zu tun.", file=sys.stderr)
        return 2
    try:
        quelle = _ablage_fuer(von)
        ziel = _ablage_fuer(args.nach)
    except AblageFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 2

    ergebnis = umzug(
        quelle, ziel,
        probelauf=args.probelauf,
        praefix=args.pfad,
        bericht=None if args.still else (lambda text: print(text)),
    )
    print()
    for zeile in ergebnis.zeilen():
        print(zeile)
    if not ergebnis.erfolgreich:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI-Einstieg
    raise SystemExit(main())
