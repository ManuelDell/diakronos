"""R-1: Tabellen des EINEN Rechtesystems + Uebernahme des Bestands.

Was diese Migration tut
-----------------------
1. Legt die fuenf Tabellen aus ``models/rechte.py`` an (idempotent).
2. Uebernimmt den Bestand OHNE Rechteverlust:

   * ``mitglied.ancestor_path`` -> fehlende Zeilen in ``gruppenmitgliedschaft``
     bzw. ``untergruppenmitgliedschaft`` (der Kern liest nur die Tabellen).

   * ``gruppe_verantwortlicher`` -> ``rechte_gruppenrolle``. Je Gruppe wird
     EIN Hauptverantwortlicher (HV) bestimmt: die Person aus ``gruppe.leiter``
     (Freitext, Abgleich mit dem vollen Namen eines Mitglieds mit Konto), sofern
     sie unter den Verantwortlichen steht; sonst die erste Zeile nach ``idx``.
     Alle weiteren werden Mitverantwortliche (MV).
   * ``untergruppe_verantwortlicher`` -> Gruppenleiter (GL) der Untergruppe
     (NICHT MV der Hauptgruppe — Delegation, Manuel 11.11.).
   * ``dienstbereich_verantwortlicher`` -> MV jeder Gruppe des Bereichs
     (Dienstbereiche entfallen; die Person behaelt ihre Sicht).
   * Module: jede Gruppe bekommt ``beitraege``, ``aufgaben`` und ``wiki``
     (heute auf jeder Gruppenseite vorhanden), ``kalender`` wenn
     ``gruppe.kalender`` gesetzt ist, ``dienstplaene`` wenn ein Dienstplan
     bzw. ein Plan-Rahmen-Plan der Gruppe gehoert, ``lieder`` fuer die Gruppen
     der Bereiche „Musik…“ und Gruppen mit Liedzuordnung (bisherige Liedpflege); sonst
     entscheidet der Administrator je Gruppe.
   * ``rechte_objekt``: JEDER Kalender. Zeigt genau eine Gruppe auf ihn
     (``gruppe.kalender``), gehoert er ihr; sonst ist er ein Gemeinde-Kalender
     (gruppe leer) und die nutzenden Gruppen bekommen eine Gruppen-Freigabe
     (Mitglieder lesen, HV/MV schreiben). Gemeinde-Freigabe ``aktiv``, wenn der
     Kalender heute der Rolle ``Mitglied``/``All`` Leserecht gibt.
     Dienstplaene mit Gruppe (Eltern = ihr Kalender).
   * ``kalender_moderator`` -> Einzelfreigabe ``moderieren`` (+ lesen).
   * Rollen-Rechte am Kalender (``user_role`` lese-/schreibrechte je Rolle)
     -> Einzelfreigaben fuer die heutigen Rolleninhaber (aktive Konten);
     Leserecht ``Mitglied``/``All`` = Gemeinde-Freigabe (s. o.) — Konten
     ohne Mitglied-Datensatz bekommen dafuer eine Einzelfreigabe ``lesen``.

Doppelte Ausfuehrung aendert nichts (jede Zeile wird vorher geprueft).
``downgrade`` entfernt nur die neuen Tabellen; der Bestand bleibt unberuehrt.

SQLite und PostgreSQL: nur SQLAlchemy-Core, keine dialektabhaengigen Ausdruecke
(Lehre aus ON-6). Vor jedem Deploy gegen einen Betriebs-Dump testen.

Revision ID: r1_rechte_kern
Revises: bs3a_website_einwilligung
Create Date: 2026-11-11
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r1_rechte_kern"
down_revision: Union[str, None] = "bs3a_website_einwilligung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MIGRATION = "r1_rechte_kern"


def _tabellen(bind) -> set[str]:
    insp = sa.inspect(bind)
    namen = list(insp.get_table_names())
    if bind.dialect.name != "sqlite":
        namen += insp.get_table_names(schema="public")
    return {str(n).lower() for n in namen}


def _anlegen(bind) -> None:
    vorhanden = _tabellen(bind)
    if "rechte_gruppenrolle" not in vorhanden:
        op.create_table(
            "rechte_gruppenrolle",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("gruppe", sa.String(140), nullable=False),
            sa.Column("untergruppe", sa.String(140), nullable=True),
            sa.Column("benutzer", sa.String(140), nullable=False),
            sa.Column("rolle", sa.String(2), nullable=False),
            sa.Column("erteilt_von", sa.String(140), nullable=True),
            sa.Column("erteilt_am", sa.DateTime(timezone=False), nullable=True),
        )
        op.create_index("uq_rechte_gruppenrolle_gruppe_benutzer", "rechte_gruppenrolle", ["gruppe", "benutzer"], unique=True,
                        postgresql_where=sa.text("untergruppe IS NULL"), sqlite_where=sa.text("untergruppe IS NULL"))
        op.create_index("uq_rechte_gruppenrolle_untergruppe_benutzer", "rechte_gruppenrolle", ["untergruppe", "benutzer"],
                        unique=True, postgresql_where=sa.text("untergruppe IS NOT NULL"),
                        sqlite_where=sa.text("untergruppe IS NOT NULL"))
        op.create_index(
            "uq_rechte_gruppenrolle_ein_hv", "rechte_gruppenrolle", ["gruppe"], unique=True,
            postgresql_where=sa.text("rolle = 'HV'"), sqlite_where=sa.text("rolle = 'HV'"),
        )
    if "rechte_modul" not in vorhanden:
        op.create_table(
            "rechte_modul",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("gruppe", sa.String(140), nullable=False),
            sa.Column("modul", sa.String(40), nullable=False),
        )
        op.create_index("uq_rechte_modul_gruppe_modul", "rechte_modul", ["gruppe", "modul"], unique=True)
    if "rechte_objekt" not in vorhanden:
        op.create_table(
            "rechte_objekt",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("typ", sa.String(40), nullable=False),
            sa.Column("objekt", sa.String(140), nullable=False),
            sa.Column("gruppe", sa.String(140), nullable=True),
            sa.Column("untergruppe", sa.String(140), nullable=True),
            sa.Column("standard_gruppe_lesen", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("gemeinde_status", sa.String(20), nullable=False, server_default=sa.text("'aus'")),
            sa.Column("gruppe_status", sa.String(20), nullable=False, server_default=sa.text("'aus'")),
            sa.Column("eltern_typ", sa.String(40), nullable=True),
            sa.Column("eltern_objekt", sa.String(140), nullable=True),
        )
        op.create_index("uq_rechte_objekt_typ_objekt", "rechte_objekt", ["typ", "objekt"], unique=True)
        op.create_index("ix_rechte_objekt_gruppe", "rechte_objekt", ["gruppe"])
    if "rechte_freigabe" not in vorhanden:
        op.create_table(
            "rechte_freigabe",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("typ", sa.String(40), nullable=False),
            sa.Column("objekt", sa.String(140), nullable=False),
            sa.Column("benutzer", sa.String(140), nullable=True),
            sa.Column("gruppe", sa.String(140), nullable=True),
            sa.Column("lesen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("schreiben", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("moderieren", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("erteilt_von", sa.String(140), nullable=True),
            sa.Column("erteilt_am", sa.DateTime(timezone=False), nullable=True),
        )
        op.create_index("uq_rechte_freigabe_typ_objekt_benutzer", "rechte_freigabe", ["typ", "objekt", "benutzer"], unique=True,
                        postgresql_where=sa.text("benutzer IS NOT NULL"), sqlite_where=sa.text("benutzer IS NOT NULL"))
        op.create_index("uq_rechte_freigabe_typ_objekt_gruppe", "rechte_freigabe", ["typ", "objekt", "gruppe"], unique=True,
                        postgresql_where=sa.text("gruppe IS NOT NULL"), sqlite_where=sa.text("gruppe IS NOT NULL"))
        op.create_index("ix_rechte_freigabe_benutzer", "rechte_freigabe", ["benutzer"])
        op.create_index("ix_rechte_freigabe_gruppe", "rechte_freigabe", ["gruppe"])
    if "rechte_gastlink" not in vorhanden:
        op.create_table(
            "rechte_gastlink",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("typ", sa.String(40), nullable=False),
            sa.Column("objekt", sa.String(140), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("passwort_hash", sa.String(255), nullable=False),
            sa.Column("ablauf", sa.DateTime(timezone=False), nullable=False),
            sa.Column("erstellt_von", sa.String(140), nullable=True),
            sa.Column("erstellt_am", sa.DateTime(timezone=False), nullable=True),
            sa.Column("widerrufen_am", sa.DateTime(timezone=False), nullable=True),
        )
        op.create_index("uq_rechte_gastlink_token", "rechte_gastlink", ["token_hash"], unique=True)


# ── Bestand lesen (nur Spalten, die es sicher gibt; fehlende Tabelle = leer) ──


def _zeilen(bind, sql: str, **param) -> list:
    return list(bind.execute(sa.text(sql), param).fetchall())


def _gibt(bind, tabelle: str) -> bool:
    return tabelle.lower() in _tabellen(bind)


def _planrahmen_gruppen(bind, gruppen) -> set[str]:
    """Gruppen, denen Plan-Rahmen-Vorlagen MIT Plaenen gehoeren (R-6).

    Dieselbe Regel wie ``planrahmen.rechte.plantyp_gruppen``: die in der
    juengsten Definition gebundenen Gruppen, sonst die EINE Gruppe des
    frueheren Dienstbereichs. Diese Gruppen bekommen das Modul
    ``dienstplaene`` — sonst verloeren ihre HV/MV das Planrecht.
    """
    import json

    if not (_gibt(bind, "pr_plantyp") and _gibt(bind, "pr_plantyp_version") and _gibt(bind, "pr_plan")):
        return set()
    je_bereich: dict[str, list[str]] = {}
    for name, _l, _k, db in gruppen:
        if db:
            je_bereich.setdefault(db, []).append(name)
    mit_plan = {t for (t,) in _zeilen(bind, "SELECT DISTINCT plantyp FROM pr_plan")}
    ergebnis: set[str] = set()
    for typ_id, bereich in _zeilen(bind, "SELECT id, bereich FROM pr_plantyp"):
        if typ_id not in mit_plan:
            continue
        zeile = _zeilen(bind, "SELECT definition FROM pr_plantyp_version WHERE plantyp = :t "
                              "ORDER BY versionsnummer DESC LIMIT 1", t=typ_id)
        definition = zeile[0][0] if zeile else None
        if isinstance(definition, str):
            try:
                definition = json.loads(definition)
            except ValueError:
                definition = None
        gebunden = {g for g in ((definition or {}).get("gruppen") or []) if isinstance(g, str)} \
            if isinstance(definition, dict) else set()
        if not gebunden and bereich and len(je_bereich.get(bereich, [])) == 1:
            gebunden = {je_bereich[bereich][0]}
        ergebnis |= gebunden
    return ergebnis


def uebernehmen(bind) -> dict[str, int]:
    """Bestand -> neue Tabellen. Rueckgabe: Zaehler (fuer Tests/Protokoll)."""
    jetzt = datetime.utcnow().replace(microsecond=0)
    zaehler = {"hv": 0, "mv": 0, "gl": 0, "mitgliedschaft": 0, "modul": 0, "objekt": 0, "freigabe": 0}

    rolle_t = sa.table("rechte_gruppenrolle", sa.column("gruppe"), sa.column("untergruppe"), sa.column("benutzer"), sa.column("rolle"),
                       sa.column("erteilt_von"), sa.column("erteilt_am"))
    modul_t = sa.table("rechte_modul", sa.column("gruppe"), sa.column("modul"))
    objekt_t = sa.table("rechte_objekt", sa.column("typ"), sa.column("objekt"), sa.column("gruppe"),
                        sa.column("untergruppe"), sa.column("gruppe_status"),
                        sa.column("standard_gruppe_lesen"), sa.column("gemeinde_status"),
                        sa.column("eltern_typ"), sa.column("eltern_objekt"))
    freigabe_t = sa.table("rechte_freigabe", sa.column("typ"), sa.column("objekt"), sa.column("benutzer"), sa.column("gruppe"),
                          sa.column("lesen"), sa.column("schreiben"), sa.column("moderieren"),
                          sa.column("erteilt_von"), sa.column("erteilt_am"))

    gruppen = _zeilen(bind, "SELECT name, leiter, kalender, dienstbereich FROM gruppe WHERE geloescht_am IS NULL") \
        if _gibt(bind, "gruppe") else []

    bestehende_rollen = {(g, b): r for g, b, r in _zeilen(
        bind, "SELECT gruppe, benutzer, rolle FROM rechte_gruppenrolle WHERE untergruppe IS NULL")}
    bestehende_gl = {(u, b) for u, b in _zeilen(
        bind, "SELECT untergruppe, benutzer FROM rechte_gruppenrolle WHERE untergruppe IS NOT NULL")}
    hv_vergeben = {g for (g, _b), r in bestehende_rollen.items() if r == "HV"}

    def rolle_setzen(gruppe: str, benutzer: str, wunsch: str) -> None:
        if not gruppe or not benutzer or (gruppe, benutzer) in bestehende_rollen:
            return
        rolle = "HV" if wunsch == "HV" and gruppe not in hv_vergeben else "MV"
        bind.execute(rolle_t.insert().values(gruppe=gruppe, untergruppe=None, benutzer=benutzer, rolle=rolle,
                                             erteilt_von=MIGRATION, erteilt_am=jetzt))
        bestehende_rollen[(gruppe, benutzer)] = rolle
        if rolle == "HV":
            hv_vergeben.add(gruppe)
            zaehler["hv"] += 1
        else:
            zaehler["mv"] += 1

    # Leiter (Freitext) -> Konto: Mitglied mit vollem Namen und verknuepftem Konto.
    konto_nach_name: dict[str, str] = {}
    if _gibt(bind, "mitglied"):
        for vn, nn, user in _zeilen(bind, 'SELECT vorname, nachname, "user" FROM mitglied WHERE "user" IS NOT NULL'):
            voll = f"{(vn or '').strip()} {(nn or '').strip()}".strip().lower()
            if voll:
                konto_nach_name.setdefault(voll, user)

    verantwortliche: dict[str, list[str]] = {}
    if _gibt(bind, "gruppe_verantwortlicher"):
        for parent, user in _zeilen(bind, 'SELECT parent, "user" FROM gruppe_verantwortlicher WHERE "user" IS NOT NULL ORDER BY parent, idx'):
            verantwortliche.setdefault(parent, []).append(user)

    for name, leiter, _kal, _db in gruppen:
        liste = verantwortliche.get(name, [])
        leiter_konto = konto_nach_name.get(str(leiter or "").strip().lower())
        hv = leiter_konto if leiter_konto in liste else (liste[0] if liste else None)
        if hv:
            rolle_setzen(name, hv, "HV")
        for user in liste:
            rolle_setzen(name, user, "MV")

    # Untergruppen-Verantwortliche -> Gruppenleiter (GL) DIESER Untergruppe —
    # bewusst NICHT MV der Hauptgruppe (Manuel 11.11.: sonst kann man Arbeit
    # nicht delegieren).
    if _gibt(bind, "untergruppe_verantwortlicher") and _gibt(bind, "untergruppe"):
        for gruppe, untergruppe, user in _zeilen(
                bind, 'SELECT u.gruppe, u.name, v."user" FROM untergruppe_verantwortlicher v '
                      'JOIN untergruppe u ON u.name = v.parent WHERE v."user" IS NOT NULL AND u.gruppe IS NOT NULL'):
            if (untergruppe, user) in bestehende_gl:
                continue
            bind.execute(rolle_t.insert().values(gruppe=gruppe, untergruppe=untergruppe, benutzer=user, rolle="GL",
                                                 erteilt_von=MIGRATION, erteilt_am=jetzt))
            bestehende_gl.add((untergruppe, user))
            zaehler["gl"] += 1

    if _gibt(bind, "dienstbereich_verantwortlicher"):
        for bereich, user in _zeilen(bind, 'SELECT parent, "user" FROM dienstbereich_verantwortlicher WHERE "user" IS NOT NULL'):
            for name, _l, _k, db in gruppen:
                if db == bereich:
                    rolle_setzen(name, user, "MV")

    # Mitgliedschaften aus dem Alt-Pfad (``mitglied.ancestor_path``,
    # ``/G1/UG1/|/Bereich/``) nachtragen, wo die Kindtabelle fehlt. Der
    # Rechte-Kern liest NUR die Mitgliedschafts-Tabellen; ohne diesen Schritt
    # verloere jedes Mitglied, das bisher nur ueber den Pfad zu einer Gruppe
    # gehoerte, seine Sicht (Befund auf :8100: 24 Pfade, 19 Mitgliedschaften).
    if _gibt(bind, "mitglied") and _gibt(bind, "gruppenmitgliedschaft"):
        import uuid

        gruppen_namen = {g for g, _l, _k, _d in gruppen}
        ug_namen = {u for (u,) in _zeilen(bind, "SELECT name FROM untergruppe")} if _gibt(bind, "untergruppe") else set()
        gm_t = sa.table("gruppenmitgliedschaft", *(sa.column(c) for c in (
            "name", "parent", "parenttype", "parentfield", "creation", "modified", "modified_by",
            "owner", "docstatus", "idx", "mitglied", "rolle", "status", "beitrittsdatum")))
        ugm_t = sa.table("untergruppenmitgliedschaft", *(sa.column(c) for c in (
            "name", "parent", "parenttype", "parentfield", "creation", "modified", "modified_by",
            "owner", "docstatus", "idx", "mitglied", "rolle", "status", "beitrittsdatum")))
        hat_g = {(p, m) for p, m in _zeilen(bind, "SELECT parent, mitglied FROM gruppenmitgliedschaft")}
        hat_u = {(p, m) for p, m in _zeilen(bind, "SELECT parent, mitglied FROM untergruppenmitgliedschaft")} \
            if _gibt(bind, "untergruppenmitgliedschaft") else set()
        for mid, pfad in _zeilen(bind, "SELECT name, ancestor_path FROM mitglied WHERE ancestor_path IS NOT NULL"):
            teile = str(pfad or "").split("|")[0]
            for seg in [x for x in teile.split("/") if x]:
                if seg in gruppen_namen and (seg, mid) not in hat_g:
                    tabelle, eltern_typ, menge = gm_t, "Gruppe", hat_g
                elif seg in ug_namen and (seg, mid) not in hat_u:
                    tabelle, eltern_typ, menge = ugm_t, "Untergruppe", hat_u
                else:
                    continue
                bind.execute(tabelle.insert().values(
                    name=f"r1-{uuid.uuid4().hex[:12]}", parent=seg, parenttype=eltern_typ,
                    parentfield="mitglieder", creation=jetzt, modified=jetzt, modified_by=MIGRATION,
                    owner=MIGRATION, docstatus=0, idx=0, mitglied=mid, rolle=None, status="Aktiv",
                    beitrittsdatum=None))
                menge.add((seg, mid))
                zaehler["mitgliedschaft"] += 1

    # Module
    module = {(g, m) for g, m in _zeilen(bind, "SELECT gruppe, modul FROM rechte_modul")}

    def modul_setzen(gruppe: str, modul: str) -> None:
        if (gruppe, modul) not in module:
            bind.execute(modul_t.insert().values(gruppe=gruppe, modul=modul))
            module.add((gruppe, modul))
            zaehler["modul"] += 1

    plan_gruppen: set[str] = set()
    plaene: list = []
    if _gibt(bind, "dienstplan"):
        plaene = _zeilen(bind, "SELECT name, gruppe, kalender FROM dienstplan WHERE gruppe IS NOT NULL")
        plan_gruppen = {g for _n, g, _k in plaene}
    plan_gruppen |= _planrahmen_gruppen(bind, gruppen)
    # R-7: Lieder pflegten bisher die Verantwortlichen des Bereichs „Musik und
    # Worship“ (Name oder Bezeichnung) und seiner Gruppen — diese Gruppen
    # bekommen das Modul ``lieder`` (sonst verloeren sie das Recht).
    # R-11f: auch „Musik“ allein (Bestand devecg) — jeder Bereich, dessen Name
    # oder Bezeichnung mit „Musik“ beginnt; dazu jede Gruppe, der schon Lieder
    # zugeordnet sind (sie pflegt offensichtlich Lieder).
    musik_bereiche: set[str] = set()
    if _gibt(bind, "dienstbereich"):
        musik_bereiche = {n for n, m in _zeilen(bind, "SELECT name, ministry FROM dienstbereich")
                          if any(str(w or "").strip().casefold().startswith("musik") for w in (n, m))}
    lied_gruppen: set[str] = set()
    if _gibt(bind, "lied_gruppenzuordnung"):
        lied_gruppen = {g for (g,) in _zeilen(
            bind, "SELECT DISTINCT gruppe FROM lied_gruppenzuordnung WHERE gruppe IS NOT NULL")}
    for name, _l, kalender, _db in gruppen:
        if (_db and _db in musik_bereiche) or name in lied_gruppen:
            modul_setzen(name, "lieder")
        for m in ("beitraege", "aufgaben", "wiki"):
            modul_setzen(name, m)
        if kalender:
            modul_setzen(name, "kalender")
        if name in plan_gruppen:
            modul_setzen(name, "dienstplaene")

    # Objekte: JEDER Kalender. Eine Gruppe besitzt ihn nur, wenn genau EINE
    # Gruppe auf ihn zeigt; sonst ist er ein Gemeinde-Kalender (gruppe NULL).
    objekte = {(t, o) for t, o in _zeilen(bind, "SELECT typ, objekt FROM rechte_objekt")}
    gemeinde_lesend: set[str] = set()
    if _gibt(bind, "user_role"):
        gemeinde_lesend = {p for (p,) in _zeilen(
            bind, "SELECT parent FROM user_role WHERE parentfield = 'leserechte' AND role IN ('Mitglied', 'All')")}

    def objekt_setzen(typ, objekt, gruppe, gemeinde="aus", eltern_typ=None, eltern_objekt=None) -> None:
        if (typ, objekt) in objekte:
            return
        bind.execute(objekt_t.insert().values(typ=typ, objekt=objekt, gruppe=gruppe, standard_gruppe_lesen=True,
                                              gemeinde_status=gemeinde, eltern_typ=eltern_typ, eltern_objekt=eltern_objekt))
        objekte.add((typ, objekt))
        zaehler["objekt"] += 1

    nutzer_je_kalender: dict[str, list[str]] = {}
    for name, _l, kalender, _db in gruppen:
        if kalender:
            nutzer_je_kalender.setdefault(kalender, []).append(name)
    alle_kalender = [k for (k,) in _zeilen(bind, "SELECT name FROM kalender")] if _gibt(bind, "kalender") else []
    for kal in alle_kalender:
        nutzer = nutzer_je_kalender.get(kal, [])
        besitzer = nutzer[0] if len(nutzer) == 1 else None
        objekt_setzen("kalender", kal, besitzer, "aktiv" if kal in gemeinde_lesend else "aus")
    for plan, gruppe, kalender in plaene:
        objekt_setzen("dienstplan", plan, gruppe, "aus",
                      "kalender" if kalender else None, kalender or None)

    # Beitraege und Wiki-Artikel gibt es heute nur gemeindeweit (ohne Gruppe):
    # Gemeinde-Objekte, veroeffentlichte Beitraege und alle Wiki-Artikel fuer
    # alle Mitglieder lesbar (wie heute). Neue Inhalte koennen einer Gruppe
    # gehoeren (HV/MV legen an).
    if _gibt(bind, "beitrag"):
        for name, veroeffentlicht in _zeilen(bind, "SELECT name, veroeffentlicht FROM beitrag WHERE geloescht_am IS NULL"):
            objekt_setzen("beitrag", name, None, "aktiv" if veroeffentlicht else "aus")
    if _gibt(bind, "wiki_artikel"):
        for (name,) in _zeilen(bind, "SELECT name FROM wiki_artikel WHERE geloescht_am IS NULL"):
            objekt_setzen("wiki", name, None, "aktiv")
    # Ankuendigungen und Aufgaben der Gruppen-Seiten: gehoeren ihrer
    # (Unter-)Gruppe.
    ug_gruppe: dict[str, str] = {}
    if _gibt(bind, "untergruppe"):
        ug_gruppe = {u: g for u, g in _zeilen(bind, "SELECT name, gruppe FROM untergruppe WHERE gruppe IS NOT NULL")}
    for tabelle, typ in (("gruppen_ankuendigung", "ankuendigung"), ("gruppen_aufgabe", "aufgabe")):
        if not _gibt(bind, tabelle):
            continue
        for name, gruppe, untergruppe in _zeilen(bind, f"SELECT name, gruppe, untergruppe FROM {tabelle}"):
            hauptgruppe = gruppe or ug_gruppe.get(untergruppe or "")
            if not hauptgruppe:
                continue
            if (typ, name) in objekte:
                continue
            bind.execute(objekt_t.insert().values(typ=typ, objekt=name, gruppe=hauptgruppe,
                                                  untergruppe=untergruppe or None, standard_gruppe_lesen=True,
                                                  gemeinde_status="aus", gruppe_status="aus",
                                                  eltern_typ=None, eltern_objekt=None))
            objekte.add((typ, name))
            zaehler["objekt"] += 1

    # Gruppen, die einen Gemeinde-Kalender nutzen: Gruppen-Freigabe
    # (Mitglieder lesen, HV/MV schreiben) — so wie sie heute dort eintragen.
    vorhanden_g = {(t, o, g) for t, o, g in _zeilen(
        bind, "SELECT typ, objekt, gruppe FROM rechte_freigabe WHERE gruppe IS NOT NULL")}
    for kal, nutzer in nutzer_je_kalender.items():
        if len(nutzer) == 1:
            continue
        for g in nutzer:
            if ("kalender", kal, g) in vorhanden_g:
                continue
            bind.execute(freigabe_t.insert().values(typ="kalender", objekt=kal, benutzer=None, gruppe=g, lesen=True,
                                                    schreiben=True, moderieren=False,
                                                    erteilt_von=MIGRATION, erteilt_am=jetzt))
            vorhanden_g.add(("kalender", kal, g))
            zaehler["freigabe"] += 1

    # Kalender-Moderatoren -> Einzelfreigabe moderieren
    if _gibt(bind, "kalender_moderator"):
        vorhanden = {(t, o, b): bool(m) for t, o, b, m in _zeilen(
            bind, "SELECT typ, objekt, benutzer, moderieren FROM rechte_freigabe WHERE benutzer IS NOT NULL")}
        for kal, user in _zeilen(bind, 'SELECT parent, "user" FROM kalender_moderator WHERE "user" IS NOT NULL'):
            if ("kalender", kal, user) in vorhanden:
                # Bestehende Freigabe (z. B. aus einer Rolle) um „moderieren“ ergaenzen.
                if not vorhanden[("kalender", kal, user)]:
                    bind.execute(freigabe_t.update().where(
                        freigabe_t.c.typ == "kalender", freigabe_t.c.objekt == kal,
                        freigabe_t.c.benutzer == user).values(lesen=True, moderieren=True))
                    vorhanden[("kalender", kal, user)] = True
                continue
            bind.execute(freigabe_t.insert().values(typ="kalender", objekt=kal, benutzer=user, gruppe=None, lesen=True,
                                                    schreiben=False, moderieren=True,
                                                    erteilt_von=MIGRATION, erteilt_am=jetzt))
            vorhanden[("kalender", kal, user)] = True
            zaehler["freigabe"] += 1

    # Rollen-Rechte am Kalender (Lese-/Schreibrecht je ROLLE) -> Einzel-
    # freigaben fuer die HEUTIGEN Inhaber der Rolle (aktive Konten), damit
    # niemand ein Recht verliert. Leserecht „Mitglied“/„All“ deckt bereits
    # die Gemeinde-Freigabe ab (oben); Systemrollen bildet der Kern selbst ab.
    if _gibt(bind, "user_role") and _gibt(bind, "user"):
        systemrollen = {"Kalenderadministrator", "System Manager", "Administrator"}
        aktive = {n for (n,) in _zeilen(bind, 'SELECT name FROM "user" WHERE enabled = :ja', ja=True)} - {"Guest"}
        inhaber: dict[str, set[str]] = {"All": set(aktive)}
        if _gibt(bind, "has_role"):
            for user, rolle in _zeilen(bind, "SELECT parent, role FROM has_role WHERE parenttype = 'User'"):
                if user in aktive and rolle:
                    inhaber.setdefault(rolle, set()).add(user)
        mit_datensatz: set[str] = set()
        if _gibt(bind, "mitglied"):
            per_mail = {str(u).strip().lower(): u for u in aktive}
            for m_user, m_mail in _zeilen(bind, 'SELECT "user", email FROM mitglied'):
                if m_user in aktive:
                    mit_datensatz.add(m_user)
                elif m_mail and str(m_mail).strip().lower() in per_mail:
                    mit_datensatz.add(per_mail[str(m_mail).strip().lower()])
        bestehend = {(o, b): bool(sch) for o, b, sch in _zeilen(
            bind, "SELECT objekt, benutzer, schreiben FROM rechte_freigabe "
                  "WHERE typ = 'kalender' AND benutzer IS NOT NULL")}
        for kal, feld, rolle in _zeilen(
            bind, "SELECT parent, parentfield, role FROM user_role "
                  "WHERE parenttype = 'Kalender' AND parentfield IN ('leserechte', 'schreibrechte')"
        ):
            if not rolle or rolle in systemrollen:
                continue
            schreiben = feld == "schreibrechte"
            personen = inhaber.get(rolle, set())
            if not schreiben and rolle in ("Mitglied", "All"):
                # Die Gemeinde-Freigabe erreicht nur Konten MIT Mitglied-
                # Datensatz; Rolleninhaber ohne Datensatz behalten ihr
                # Leserecht als Einzelfreigabe.
                personen = personen - mit_datensatz
            for user in sorted(personen):
                if (kal, user) not in bestehend:
                    bind.execute(freigabe_t.insert().values(
                        typ="kalender", objekt=kal, benutzer=user, gruppe=None, lesen=True,
                        schreiben=schreiben, moderieren=False, erteilt_von=MIGRATION, erteilt_am=jetzt))
                    bestehend[(kal, user)] = schreiben
                    zaehler["freigabe"] += 1
                elif schreiben and not bestehend[(kal, user)]:
                    bind.execute(freigabe_t.update().where(
                        freigabe_t.c.typ == "kalender", freigabe_t.c.objekt == kal,
                        freigabe_t.c.benutzer == user).values(schreiben=True))
                    bestehend[(kal, user)] = True
    return zaehler


def upgrade() -> None:
    bind = op.get_bind()
    _anlegen(bind)
    uebernehmen(bind)


def downgrade() -> None:
    bind = op.get_bind()
    vorhanden = _tabellen(bind)
    for tabelle in ("rechte_gastlink", "rechte_freigabe", "rechte_objekt", "rechte_modul", "rechte_gruppenrolle"):
        if tabelle in vorhanden:
            op.drop_table(tabelle)
