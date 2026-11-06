"""ON-6: der erste Administrator ist ``root`` — Spalte, Tabelle, Bestandsdaten.

WAS DIESE MIGRATION TUT
-----------------------
1. ``gemeinde_einstellungen.root_benutzer``  VARCHAR(140) — der Konto-Name des
   Root-Benutzers. Leer = es gibt keinen root. Die Rechtepruefung liest
   AUSSCHLIESSLICH dieses Feld (``root_benutzer.ist_root``).
2. ``gruppen_root_user`` — eine Zeile je Konto, das die Kennrolle ``root``
   traegt (Protokoll/Inventar; NICHT die Rechtequelle).
3. **Bestandsinstallationen** bekommen einen root, sonst waere die Karte nur
   fuer Neuinstallationen wirksam. Ermittelt wird er so:

   * Kandidaten sind die ``has_role``-Zeilen mit ``parenttype`` ``User``
     (oder leer/NULL, siehe ``permissions.ist_user_zeile``) und der Rolle
     ``System Manager``, sortiert nach ``creation`` (Anlagezeitpunkt der
     Rollenzeile — die Spalte heisst in den Altdaten ``creation``, NICHT
     ``created``), dann ``idx`` (Reihenfolge der Rollenvergabe), dann
     ``parent``.
   * Genommen wird der ERSTE Kandidat, dessen ``parent`` in der
     ``user``-Tabelle steht. Gegenprobe am Betriebsdump vom 2026-11-05: die
     nach ``creation`` aeltesten System-Manager-Zeilen gehoeren zu DocTypes
     (``ToDo``, ``Document Share Report``) — ohne die ``user``-Gegenprobe
     waere die Migration dort gelandet statt beim Konto. Im Betrieb traegt
     genau ein Konto System Manager (der Gruender).
   * Existiert keine ``user``-Tabelle oder gibt es keinen Treffer, bleibt
     ``root_benutzer`` leer — es wird KEIN root erfunden.

   Der so gefundene root erhaelt die Kennrolle ``root`` in ``has_role``
   (falls sie fehlt) — die Oberflaeche zeigt damit denselben Stand wie die
   Rechtepruefung.

POSTGRES-DETAILS
----------------
``user`` und ``role`` sind in PostgreSQL RESERVIERTE Woerter: ohne
Anfuehrungszeichen loest ``FROM user`` auf die Funktion ``user`` auf
(„column name does not exist“). Jeder dynamisch gebaute Tabellenname wird
deshalb ueber :func:`_zitat` zitiert — und zwar erst, nachdem er ueber
:func:`_tabelle` IM KATALOG nachgeschlagen wurde (ein fremder Name kommt
damit nie in die Anweisung).

**Gebundene Parameter (Live-Abbruch 06.11., ON-6e).** Ein Parameter, der in
EINER Anweisung mehrfach vorkommt, bekommt auf PostgreSQL EINEN Typ — und
psycopg2 muss ihn aus allen Vorkommen ableiten. Gegen
``INSERT INTO gemeinde_einstellungen (name) SELECT :zeile WHERE NOT EXISTS
(SELECT 1 FROM gemeinde_einstellungen WHERE name = :zeile)`` scheiterte das
mit ``psycopg.errors.AmbiguousParameter: inconsistent types deduced for
parameter $1 — text versus character varying`` (``name`` ist
``VARCHAR(140)``, die Zielecke des ``SELECT`` typenlos), und die App startete
in einer Schleife. Deshalb gilt hier:

  * Schreibvorgaenge werden ERST GELESEN, DANN EINGEFUEGT (Python) — ein
    ``INSERT … SELECT … WHERE NOT EXISTS`` mit geteiltem Parameter entfaellt.
  * Wo doch gebunden wird, traegt das ZIEL einen ausdruecklichen ``CAST`` auf
    den Spaltentyp (``CAST(:wert AS VARCHAR(140))``), damit beide Vorkommen
    denselben Typ ergeben.
  * Datum/Zeit kommt aus ``CURRENT_TIMESTAMP`` der Datenbank, nie als
    gebundener Parameter (Vorfall DM1: ``now()`` als Parameter).

Geprueft gegen echtes PostgreSQL 17 (``backend/tests/test_on6e_pg_migration.py``):
frische DB, Bestands-DB mit Daten, Downgrade/Upgrade-Rundlauf.

Idempotent
----------
Jeder Schritt prueft zuerst den Bestand (Spalte/Tabelle/Zeile vorhanden?);
ein zweiter Lauf aendert nichts. Das Muster ist dasselbe wie in
``ux2b_papierkorb``; es funktioniert auf PostgreSQL (Betrieb) und auf
SQLite (Test-Rundlauf).

Einziger Head
-------------
``down_revision = "ux2b_papierkorb"`` — die Kette hat genau einen Kopf.

Revision ID: on6_root_benutzer
Revises: ux2b_papierkorb
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "on6_root_benutzer"
down_revision: Union[str, None] = "ux2b_papierkorb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Spalte an der Single-Zeile der Gemeinde-Angaben.
SPALTEN_TABELLE = "gemeinde_einstellungen"
SPALTE = "root_benutzer"
#: Name der Single-Zeile (``models/gemeinde.GEMEINDE_EINSTELLUNGEN_NAME``).
GEMEINDE_ZEILE = "Gemeinde Einstellungen"

#: Tabelle der Kennrolle (Handmodell ``models/root_benutzer.py``).
KENNROLLE_TABELLE = "gruppen_root_user"

#: Der Rollenname der Kennzeichnung (dieselbe Konstante wie im Modell).
ROOT_ROLLE = "root"

#: Rolle, aus der der Bestands-root abgeleitet wird.
SYSTEM_MANAGER = "System Manager"


def _katalog(bind) -> list[str]:
    """Tabellennamen WIE IM KATALOG (Gross-/Kleinschreibung bleibt erhalten)."""
    insp = sa.inspect(bind)
    namen = list(insp.get_table_names())
    if bind.dialect.name != "sqlite":
        namen += list(insp.get_table_names(schema="public"))
    return namen


def _tabelle(bind, name: str) -> str | None:
    """Der Katalogname zu ``name`` (case-insensitiv) oder ``None``."""
    for kandidat in _katalog(bind):
        if str(kandidat).lower() == str(name).lower():
            return str(kandidat)
    return None


def _zitat(bind, name: str) -> str:
    """Zitierter Tabellenname fuer rohes SQL (``user``/``role`` sind reserviert)."""
    return bind.dialect.identifier_preparer.quote(name)


def _hat_spalte(bind, tabelle: str, spalte: str) -> bool:
    insp = sa.inspect(bind)
    return any(
        str(s["name"]).lower() == str(spalte).lower()
        for s in insp.get_columns(tabelle)
    )


#: Werte, die ``enabled`` als „aus“ bedeuten. PostgreSQL liefert einen echten
#: Bool, SQLite mit Altdaten auch ``0``/``'0'``/``''`` — dieselbe Normalisierung
#: wie ``frappe_compat.api_helpers._ist_aktiv_flag``.
_AUS = {"", "0", "false", "nein", "no", "none", "off", "f"}


def _aktiv(wert) -> bool:
    """``enabled`` tolerant als Bool lesen (ON-6b, Datensicherheit)."""
    if wert is None:
        return False
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return bool(wert)
    return str(wert).strip().lower() not in _AUS


def _gemeinde_zeile_sichern(bind, gemeinde_q: str) -> None:
    """Stellt die Single-Zeile ``Gemeinde Einstellungen`` sicher (ON-6b).

    Die Migration schreibt den root in DIESE Zeile. Fehlte sie (frische oder
    beschnittene DB), lief das UPDATE ohne Treffer ins Leere, und die Rolle
    ``root`` entstand ohne den dazugehoerigen Eintrag — eine verwaiste
    Has-Role-Zeile, die einen root anzeigt, den es nicht gibt.

    Angelegt wird nur der ``name``; alle Fachspalten sind nullable und werden
    von der App gefuellt. Das ist kein Erfinden von Fachdaten. Idempotent:
    eine vorhandene Zeile bleibt unberuehrt.

    ON-6e: ERST LESEN, DANN SCHREIBEN. Das frueher benutzte
    ``INSERT … SELECT :zeile WHERE NOT EXISTS (… name = :zeile)`` liess
    PostgreSQL fuer denselben Parameter zwei Typen ableiten
    (``text`` gegen ``character varying``) und brach die Migration auf dem
    Betrieb ab (``AmbiguousParameter``).
    """
    vorhanden = bind.execute(
        sa.text(f"SELECT 1 FROM {gemeinde_q} WHERE name = :zeile"),
        {"zeile": GEMEINDE_ZEILE},
    ).first()
    if vorhanden is not None:
        return
    bind.execute(
        sa.text(
            f"INSERT INTO {gemeinde_q} (name) VALUES (CAST(:zeile AS VARCHAR(140)))"
        ),
        {"zeile": GEMEINDE_ZEILE},
    )


def _kennrolle_zeile_sichern(bind, kennrolle_q: str, konto: str) -> None:
    """Zeile in ``gruppen_root_user`` schreiben (ON-6b, idempotent).

    Diese Tabelle ist laut ``models/root_benutzer.py`` die AUTORITATIVE Quelle,
    wer die Kennrolle tragen darf — wer die Rolle in ``has_role`` direkt
    schreibt, erzeugt sonst zwei Staende. ``created`` bekommt den Zeitpunkt
    des Laufs (Spalte ist nullable, ein Wert ist trotzdem die bessere Spur).

    ``konto`` wird per Parameter gebunden, der Tabellenname stand schon im
    Katalog (``_tabelle``) — kein fremder Name kommt in die Anweisung.
    ON-6e: Lesen und Schreiben getrennt, Parameter mit ``CAST`` am Ziel
    (derselbe Grund wie in :func:`_gemeinde_zeile_sichern`).
    """
    name = str(konto or "").strip()
    if not name:
        return
    vorhanden = bind.execute(
        sa.text(f"SELECT 1 FROM {kennrolle_q} WHERE konto = :konto"),
        {"konto": name},
    ).first()
    if vorhanden is not None:
        return
    bind.execute(
        sa.text(
            f"INSERT INTO {kennrolle_q} (konto, created, created_by) "
            "VALUES (CAST(:konto AS VARCHAR(140)), CURRENT_TIMESTAMP, "
            "CAST(:quelle AS VARCHAR(140)))"
        ),
        {"konto": name, "quelle": "alembic:on6_root_benutzer"},
    )


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Spalte an der Gemeinde-Single.
    gemeinde = _tabelle(bind, SPALTEN_TABELLE)
    if gemeinde is not None and not _hat_spalte(bind, gemeinde, SPALTE):
        op.add_column(
            gemeinde,
            sa.Column(SPALTE, sa.String(length=140), nullable=True),
        )

    # 2) Tabelle der Kennrolle. Bewusst ohne Fremdschluessel auf `user`: das
    #    Loeschen eines Kontos (DSGVO) raeumt die Zeile ueber
    #    `root_benutzer.entferne` bzw. die Anonymisierung ab — ein FK wuerde
    #    dort eine Reihenfolge erzwingen, die die Loeschung nicht kennt.
    if _tabelle(bind, KENNROLLE_TABELLE) is None:
        op.create_table(
            KENNROLLE_TABELLE,
            sa.Column("konto", sa.String(length=140), nullable=False),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=140), nullable=True),
            sa.PrimaryKeyConstraint("konto"),
        )

    # 3) Bestandsdaten (siehe Modulkopf).
    rollen = _tabelle(bind, "has_role")
    if gemeinde is None or rollen is None:
        return

    gemeinde_q = _zitat(bind, gemeinde)
    rollen_q = _zitat(bind, rollen)
    kennrolle = _tabelle(bind, KENNROLLE_TABELLE)
    kennrolle_q = _zitat(bind, kennrolle) if kennrolle is not None else KENNROLLE_TABELLE
    # ON-6b: Die Single-Zeile MUSS existieren, bevor der Eintrag geschrieben
    # wird — ein UPDATE ohne Treffer lief frueher still ins Leere, und
    # `_kennrolle_sichern` legte danach eine root-Rolle an, zu der es keinen
    # Eintrag gab (verwaiste Has-Role-Zeile). Fehlt die Zeile, wird sie hier
    # angelegt; `name` ist der einzige Pflichtwert, alle Fachspalten sind
    # nullable.
    _gemeinde_zeile_sichern(bind, gemeinde_q)

    # Nichts tun, wenn schon ein root eingetragen ist (Downgrade/Upgrade-
    # Rundlauf oder eine Installation, die root von Hand gesetzt hat).
    schon = bind.execute(
        sa.text(
            f"SELECT {SPALTE} FROM {gemeinde_q} "
            f"WHERE {SPALTE} IS NOT NULL AND {SPALTE} <> '' LIMIT 1"
        )
    ).first()
    if schon is not None:
        _kennrolle_zeile_sichern(bind, kennrolle_q, str(schon[0]))
        _kennrolle_sichern(bind, rollen_q, str(schon[0]))
        return

    # ON-6b — DETERMINISTISCHE REIHENFOLGE auf SQLite UND PostgreSQL:
    # ``ORDER BY creation IS NULL, creation, name``. Ein blosses
    # ``ORDER BY creation`` ist NICHT deterministisch: PostgreSQL sortiert
    # NULLs ans Ende, SQLite an den Anfang — dieselben Daten haetten je nach
    # Datenbank einen anderen root ergeben. ``creation IS NULL`` liefert in
    # beiden Dialekten 0/1; Zeilen ohne Anlagezeitpunkt kommen damit zuletzt,
    # danach entscheidet die Zeit und zuletzt der Kontoname (stabil, auch
    # wenn zwei Zeilen dieselbe Sekunde tragen).
    #
    # ``idx`` ist ABSICHTLICH nicht mehr in der Sortierung: es ist die
    # Position der Rolle INNERHALB eines Users (bei Frappe fortlaufend je
    # Konto) und kein Zeitmass. Es machte den Vergleich zweier Konten von
    # ihrer Rollenreihenfolge abhaengig. ``parent`` als letzter Schluessel
    # deckt den Gleichstand vollstaendig ab.
    zeilen = bind.execute(
        sa.text(
            f"SELECT parent FROM {rollen_q} "
            "WHERE role = :rolle AND (parenttype IS NULL OR parenttype = '' "
            "      OR parenttype = 'User') "
            "ORDER BY creation IS NULL, creation, parent"
        ),
        {"rolle": SYSTEM_MANAGER},
    ).all()

    konten_tabelle = _tabelle(bind, "user")
    konto: str | None = None
    if konten_tabelle is not None:
        konten_q = _zitat(bind, konten_tabelle)
        for zeile in zeilen:
            name = str(zeile[0] or "").strip()
            if not name:
                continue
            treffer = bind.execute(
                sa.text(
                    f"SELECT enabled FROM {konten_q} WHERE name = :name"
                ),
                {"name": name},
            ).first()
            if treffer is None:
                continue
            # ON-6b: ein DEAKTIVIERTES Konto wird uebersprungen — ein
            # gesperrter Administrator kaeme als root nie zur Anmeldung und
            # die Gemeinde haette einen root, den niemand ausueben kann.
            # `enabled` wird bewusst tolerant gelesen (`0`/`false`/leer =
            # aus), weil Altdaten die Spalte als Text fuehren koennen.
            if not _aktiv(treffer[0]):
                continue
            konto = name
            break
    if konto is None:
        # Kein Konto gefunden -> KEIN root erfinden (Modulkopf, Punkt 3).
        return

    # Eintrag schreiben — die Zeile steht seit Schritt 3.1 fest (siehe
    # `_gemeinde_zeile_sichern`), das UPDATE trifft also garantiert.
    bind.execute(
        sa.text(
            f"UPDATE {gemeinde_q} SET {SPALTE} = CAST(:konto AS VARCHAR(140)) "
            "WHERE name = CAST(:zeile AS VARCHAR(140))"
        ),
        {"konto": konto, "zeile": GEMEINDE_ZEILE},
    )
    # ON-6b: ``gruppen_root_user`` ist laut Modell die AUTORITATIVE Quelle
    # dafuer, wer die Kennrolle tragen darf — die Zeile wird deshalb hier
    # mitgeschrieben, nicht nur die Rolle in ``has_role``.
    _kennrolle_zeile_sichern(bind, kennrolle_q, konto)
    _kennrolle_sichern(bind, rollen_q, konto)


def _kennrolle_sichern(bind, rollen_q: str, konto: str) -> None:
    """Kennrolle ``root`` fuer ``konto`` eintragen (idempotent).

    ON-6e: Auch hier traegt jeder gebundene Parameter einen ausdruecklichen
    ``CAST`` auf den Spaltentyp. Der Parameter ``:konto`` steht in ZWEI
    Anweisungen mit verschiedenen Spaltentypen (``parent`` in ``SELECT`` und
    ``INSERT``); ohne ``CAST`` muesste PostgreSQL den Typ erneut aus mehreren
    Vorkommen ableiten — genau die Falle, die die Migration auf dem Betrieb
    abgebrochen hat.
    """
    name = str(konto or "").strip()
    if not name:
        return
    vorhanden = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {rollen_q} "
            "WHERE parent = CAST(:konto AS VARCHAR(140)) "
            "AND role = CAST(:rolle AS VARCHAR(140))"
        ),
        {"konto": name, "rolle": ROOT_ROLLE},
    ).scalar()
    if int(vorhanden or 0):
        return
    bind.execute(
        sa.text(
            f"INSERT INTO {rollen_q} (name, parent, parenttype, parentfield, role, "
            "docstatus, idx) VALUES (CAST(:name AS VARCHAR(140)), "
            "CAST(:parent AS VARCHAR(140)), CAST('User' AS VARCHAR(140)), "
            "CAST('roles' AS VARCHAR(140)), CAST(:rolle AS VARCHAR(140)), 0, 0)"
        ),
        {"name": f"{name}-{ROOT_ROLLE}", "parent": name, "rolle": ROOT_ROLLE},
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Die Kennrolle wieder einsammeln, BEVOR die Spalte verschwindet — sonst
    # bliebe ein `has_role`-Eintrag stehen, den niemand mehr erklaeren kann.
    rollen = _tabelle(bind, "has_role")
    if rollen is not None:
        bind.execute(
            sa.text(f"DELETE FROM {_zitat(bind, rollen)} WHERE role = :rolle"),
            {"rolle": ROOT_ROLLE},
        )

    kennrolle = _tabelle(bind, KENNROLLE_TABELLE)
    if kennrolle is not None:
        op.drop_table(kennrolle)

    gemeinde = _tabelle(bind, SPALTEN_TABELLE)
    if gemeinde is not None and _hat_spalte(bind, gemeinde, SPALTE):
        op.drop_column(gemeinde, SPALTE)
