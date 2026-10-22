"""Plan-Rahmen — Speicher: typisierte Grundoperationen (Repository).

Dieses Modul kapselt die elementaren, transaktionalen Zugriffe auf die
pr_*-Tabellen des Plan-Rahmens: Versionen anlegen (inkl. fortlaufender
Versionsnummer) und ermitteln, Einträge mit Verlaufseintrag atomar setzen und
den Verlauf undo-en. Es ist die eine Stelle, an der die P4-Regeln (Versionen
unveränderlich, Undo) durchgesetzt werden — wer Daten anlegt oder ändert, geht
über diese Funktionen, nicht direkt an die Modelle.

Ohne KI, ohne Engine: hier gibt es ausschliesslich Speicher, keine Generierung
und keine Endpunkte (P8). Typannotationen und Docstrings auf Deutsch, wie im
Konzept.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.models.planrahmen import (
    Eintrag,
    PlantypVersion,
    Verlauf,
)


class PlanrahmenFehler(Exception):
    """Basis für fachliche Fehler des Plan-Rahmen-Speichers."""


class VersionUnveraenderlich(PlanrahmenFehler):
    """Eine bereits angelegte Plantyp-Version darf nicht mehr geändert werden."""


def naechste_versionsnummer(session: Session, plantyp_id: str) -> int:
    """Liefert die nächste fortlaufende Versionsnummer eines Plantyps.

    Versionsnummern zählen ab 1 je Plantyp. Es wird `1 + max(versionsnummer)`
    gebildet; existiert noch keine Version, ist das Ergebnis `1`.
    """

    existing = (
        session.execute(
            select(PlantypVersion.versionsnummer).where(
                PlantypVersion.plantyp == plantyp_id
            )
        )
        .scalars()
        .all()
    )
    return (max(existing) + 1) if existing else 1


def version_anlegen(
    session: Session,
    *,
    plantyp_id: str,
    definition: dict | list | Any,
    gueltig_ab: date,
    schema_version: str = "1",
    erstellt_von: str | None = None,
    kommentar: str | None = None,
) -> PlantypVersion:
    """Legt eine neue, unveränderliche Plantyp-Version an.

    Die Versionsnummer wird automatisch als nächste freie Nummer des Plantyps
    vergeben. Die erzeugte Version wird der Session hinzugefügt (aber nicht
    committet — der Aufrufer committet in seiner Transaktion).
    """

    versionsnummer = naechste_versionsnummer(session, plantyp_id)
    version = PlantypVersion(
        plantyp=plantyp_id,
        versionsnummer=versionsnummer,
        gueltig_ab=gueltig_ab,
        definition=definition,
        schema_version=schema_version,
        erstellt_von=erstellt_von,
        kommentar=kommentar,
    )
    session.add(version)
    # Flush, damit eine unmittelbar folgende `version_anlegen`/`naechste_-
    # versionsnummer` in derselben Transaktion die neue Version schon sieht —
    # sonst wuerden zwei Versionen in einem Commit dieselbe Nummer bekommen.
    session.flush()
    return version


def version_aendern(session: Session, version: PlantypVersion, **aenderungen: Any) -> None:
    """Abgelehnte Änderung an einer Version — siehe P4.

    Wird versucht, eine bereits angelegte Version zu ändern, bricht die
    Funktion mit :class:`VersionUnveraenderlich` ab. Ein erneuter Aufruf mit
    denselben (unveränderten) Werten ist ausdrücklich kein Fehler — so bleibt
    ein "speichern, ohne etwas geändert zu haben"-Aufruf idempotent.

    `session` wird nicht benutzt, ist aber Teil der Signatur, damit die Regel
    gleichförmig mit den übrigen Operationen als Repository-Aufruf erkennbar
    bleibt.
    """

    for feld, neu in aenderungen.items():
        spalte = getattr(version.__class__, feld).property.columns[0]
        alt = getattr(version, feld)
        if alt == neu:
            continue
        raise VersionUnveraenderlich(
            f"Plantyp-Versionen sind unveränderlich (P4): Feld "
            f"{spalte.name!r} darf nicht geändert werden. Stattdessen eine neue "
            f"Version mit höherer Versionsnummer anlegen."
        )


def gueltige_version_zu_datum(
    session: Session, plantyp_id: str, stichtag: date
) -> PlantypVersion | None:
    """Ermittelt die am `stichtag` gültige Plantyp-Version.

    Es gilt die Version mit dem jüngsten `gueltig_ab <= stichtag`; bei
    mehreren Versionen am selben `gueltig_ab` gewinnt die höhere
    Versionsnummer. Liegt keine passende Version vor, wird `None`
    zurückgegeben.
    """

    versionen = (
        session.execute(
            select(PlantypVersion)
            .where(
                PlantypVersion.plantyp == plantyp_id,
                PlantypVersion.gueltig_ab <= stichtag,
            )
            .order_by(
                PlantypVersion.gueltig_ab.desc(),
                PlantypVersion.versionsnummer.desc(),
            )
        )
        .scalars()
        .all()
    )
    return versionen[0] if versionen else None


def _eintrag_snapshot(eintrag: Eintrag | None) -> dict[str, Any] | None:
    """Baut einen JSON-fähigen Schnappschuss eines Eintrags (für den Verlauf).

    Enthält `termin` und `feld_pfad` als Ort sowie `wert`/`fixiert`/`quelle`/
    `index`/`variante` als Zustand — damit der Undo den Eintrag eindeutig
    wiederfindet und seinen Stand wiederherstellt.
    """

    if eintrag is None:
        return None
    return {
        "termin": eintrag.termin,
        "feld_pfad": eintrag.feld_pfad,
        "wert": eintrag.wert,
        "fixiert": eintrag.fixiert,
        "quelle": eintrag.quelle,
        "index": eintrag.index,
        "variante": eintrag.variante,
    }


def eintrag_setzen(
    session: Session,
    *,
    plan_id: str,
    termin_id: str,
    feld_pfad: str,
    wert: dict | Any,
    benutzer: str | None = None,
    fixiert: bool = False,
    quelle: str = "manuell",
    index: int | None = None,
    variante: str | None = None,
    gruppe_id: str | None = None,
) -> Eintrag:
    """Setzt einen Eintrag an einem Termin und schreibt den Verlauf atomar.

    Es wird der bestehende Eintrag zu (``termin``, ``feld_pfad``) geladen
    (Unique-Constraint), ein Verlaufs-Datensatz mit `vorher`/`nachher` angelegt
    und der Eintrag aktualisiert bzw. neu angelegt — alles innerhalb der
    laufenden Transaktion des Aufrufers (der anschliessend committet). Damit
    schlagen Eintrag und Verlauf nie auseinander (Undo-Grundlage, P4).
    """

    eintrag = session.execute(
        select(Eintrag).where(
            Eintrag.termin == termin_id,
            Eintrag.feld_pfad == feld_pfad,
        )
    ).scalar_one_or_none()

    vorher = _eintrag_snapshot(eintrag)
    if eintrag is None:
        eintrag = Eintrag(termin=termin_id, feld_pfad=feld_pfad)
        session.add(eintrag)

    eintrag.wert = wert
    eintrag.fixiert = fixiert
    eintrag.quelle = quelle
    eintrag.index = index
    eintrag.variante = variante

    verlauf = Verlauf(
        plan=plan_id,
        benutzer=benutzer,
        aktion="eintrag_setzen",
        vorher=vorher,
        nachher=_eintrag_snapshot(eintrag),
        gruppe_id=gruppe_id,
    )
    session.add(verlauf)
    return eintrag


def undo_verlaufsgruppe(session: Session, gruppe_id: str) -> int:
    """Stellt den Zustand vor einer Verlaufsgruppe wieder her (Undo).

    Alle `eintrag_setzen`-Verläufe mit dieser `gruppe_id` werden in umgekehrter
    chronologischer Reihenfolge zurückgerollt:

    * hatte der Eintrag in `vorher` keinen Wert (``vorher is None``), wurde er
      durch die Gruppe neu angelegt und wird jetzt gelöscht;
    * hatte er einen Wert, werden `wert`/`fixiert`/`quelle`/`index`/`variante`
      auf den Stand von `vorher` zurückgesetzt.

    Der Eintrag wird über ``(termin, feld_pfad)`` aus dem Schnappschuss
    wiedergefunden. Rückgabe ist die Anzahl zurückgerollter Verlaufseinträge.
    Die Änderungen werden der Session hinzugefügt, nicht committet.
    """

    verlaeufe = (
        session.execute(
            select(Verlauf)
            .where(Verlauf.gruppe_id == gruppe_id)
            .order_by(Verlauf.zeitpunkt.desc())
        )
        .scalars()
        .all()
    )

    anz = 0
    for verlauf in verlaeufe:
        if verlauf.aktion != "eintrag_setzen":
            continue
        nachher = verlauf.nachher or {}
        feld_pfad = (verlauf.vorher or nachher).get("feld_pfad")
        termin = (verlauf.vorher or nachher).get("termin")
        if feld_pfad is None or termin is None:
            # Kein Ort im Schnappschuss — dieser Verlauf ist nicht (mehr)
            # zuordenbar. Überspringen statt raten (fail closed).
            continue
        eintrag = session.execute(
            select(Eintrag).where(
                Eintrag.termin == termin,
                Eintrag.feld_pfad == feld_pfad,
            )
        ).scalar_one_or_none()

        vorher = verlauf.vorher
        if not vorher:
            # Eintrag wurde in dieser Gruppe neu angelegt -> löschen.
            if eintrag is not None:
                session.delete(eintrag)
        else:
            if eintrag is not None:
                eintrag.wert = vorher["wert"]
                eintrag.fixiert = vorher.get("fixiert", False)
                eintrag.quelle = vorher.get("quelle", "manuell")
                eintrag.index = vorher.get("index")
                eintrag.variante = vorher.get("variante")
        anz += 1

    return anz
