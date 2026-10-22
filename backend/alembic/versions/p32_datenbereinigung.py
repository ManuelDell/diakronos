"""P3-2: Import-Altwaisen und leere Link-Werte bereinigen.

Datenbereinigung ist absichtlich nicht rueckgaengig: downgrade erfindet keine
verlorenen Referenzen. Audit-Zeilen bleiben erhalten, nur ihr unaufloesbarer
Policy-Link wird geleert. Bestehende/fehlende FK werden danach validiert.
"""
import logging

import sqlalchemy as sa
from alembic import op

revision = "p32_datenbereinigung"
down_revision = "p14_termin_variante"
branch_labels = None
depends_on = None

# Genau die acht beim alten Dump-Restore gescheiterten Fremdschluessel.
LINKS = (
    ("liedfassung", "lied", "lied"),
    ("audit_log", "policy_triggered", "audit_policy"),
    ("mitglied_bereich", "dienstbereich", "dienstbereich"),
    ("ablaufplan_position", "gruppe", "gruppe"),
    ("ablaufplan_position", "referenz_doctype", "doctype"),
    ("ablaufplan_position", "verantwortlicher", "mitglied"),
    ("element", "element_category", "eventkategorie"),
    ("element", "ressource", "ressource"),
)


def bereinigen(conn):
    """Idempotente Datenkorrektur; auch separat gegen Dump-Kopien pruefbar."""
    zahlen = {}
    # Pflicht-Eltern zuerst behandeln. Auch ein UPDATE einer anderen Spalte
    # kann bestehende (beim replica-Import umgangene) FK-Verletzungen pruefen.
    waise = "SELECT name FROM liedfassung WHERE lied IS NOT NULL AND lied <> '' AND NOT EXISTS (SELECT 1 FROM lied WHERE lied.name = liedfassung.lied)"
    # Referenzen auf geloeschte Fassungen nicht ihrerseits verwaisen lassen.
    for tabelle in ("liedgruppe_lied", "dienstplan_position"):
        conn.execute(sa.text(f'UPDATE "{tabelle}" SET fassung = NULL WHERE fassung IN ({waise})'))
    conn.execute(sa.text(
        f"DELETE FROM lied_material WHERE parenttype = 'Liedfassung' AND parent IN ({waise})"))
    zahlen["liedfassung.waise"] = conn.execute(sa.text(
        f"DELETE FROM liedfassung WHERE name IN ({waise})")).rowcount
    zahlen["mitglied_bereich.waise"] = conn.execute(sa.text(
        "DELETE FROM mitglied_bereich WHERE dienstbereich IS NOT NULL AND dienstbereich <> '' "
        "AND NOT EXISTS (SELECT 1 FROM dienstbereich WHERE dienstbereich.name = mitglied_bereich.dienstbereich)"
    )).rowcount

    tabellen = {}
    for tabelle, spalte, ziel in LINKS:
        tabellen.setdefault(tabelle, []).append((spalte, ziel))
    for tabelle, links in tabellen.items():
        setzen, bedingungen = [], []
        for spalte, ziel in links:
            leer = f'"{spalte}" = \'\''
            waise = (f'"{spalte}" IS NOT NULL AND "{spalte}" <> \'\' '
                     f'AND NOT EXISTS (SELECT 1 FROM "{ziel}" '
                     f'WHERE "{ziel}".name = "{tabelle}"."{spalte}")')
            for art, bedingung in (("leer", leer), ("waise", waise)):
                zahlen[f"{tabelle}.{spalte}.{art}"] = conn.execute(sa.text(
                    f'SELECT count(*) FROM "{tabelle}" WHERE {bedingung}'
                )).scalar_one()
            kaputt = f'({leer}) OR ({waise})'
            setzen.append(f'"{spalte}" = CASE WHEN {kaputt} THEN NULL ELSE "{spalte}" END')
            bedingungen.append(f'({kaputt})')
        # Alle kaputten Links einer Zeile gleichzeitig korrigieren. Einzelne
        # Spalten-UPDATEs koennen am noch unveraenderten Nachbar-FK scheitern,
        # auch wenn dieser NOT VALID ist. Keine Constraints/Trigger abschalten.
        conn.execute(sa.text(
            f'UPDATE "{tabelle}" SET {", ".join(setzen)} WHERE {" OR ".join(bedingungen)}'))
    zahlen["beitrag_kommentar.waise"] = conn.execute(sa.text(
        "DELETE FROM beitrag_kommentar WHERE parenttype = 'Beitrag' "
        "AND NOT EXISTS (SELECT 1 FROM beitrag WHERE beitrag.name = beitrag_kommentar.parent)"
    )).rowcount
    # Nur Mengen, keine personenbezogenen Zeilenwerte ins Migrationslog.
    logging.getLogger("alembic.runtime.migration").info("P3-2 Bereinigung: %s", zahlen)
    return zahlen


def upgrade():
    conn = op.get_bind()
    bereinigen(conn)
    for tabelle, spalte, ziel in LINKS:
        name = f"{tabelle}_{spalte}_fkey"
        vorhanden = any(fk['constrained_columns'] == [spalte] and
                        fk['referred_table'] == ziel and fk['referred_columns'] == ['name']
                        for fk in sa.inspect(conn).get_foreign_keys(tabelle))
        if not vorhanden:
            conn.execute(sa.text(
                f'ALTER TABLE "{tabelle}" ADD CONSTRAINT "{name}" '
                f'FOREIGN KEY ("{spalte}") REFERENCES "{ziel}" (name) NOT VALID'))
        # Auch einen bereits bestehenden NOT VALID-FK tatsaechlich validieren.
        for fk in sa.inspect(conn).get_foreign_keys(tabelle):
            if fk['constrained_columns'] == [spalte] and fk['referred_table'] == ziel:
                fk_name = conn.dialect.identifier_preparer.quote(fk['name'])
                conn.execute(sa.text(f'ALTER TABLE "{tabelle}" VALIDATE CONSTRAINT {fk_name}'))


def downgrade():
    # Die FK gehoeren schon zum Basisschema, auch nach downgrade bleiben sie.
    # Ein zweites upgrade findet keine Waisen und ist wirkungslos.
    pass
