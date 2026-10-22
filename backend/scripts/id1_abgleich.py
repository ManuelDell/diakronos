"""Zahlen der ID-1-Abnahme: I3-Abgleich gegen zwei Wegwerf-Kopien.

Läuft GEGEN die Kopie des Betriebs-Dumps im Ausgangszustand (`url_vorher`) und
die umgeschlüsselte Kopie (`url_nachher`) — aufgerufen von der Abnahme, nicht
von pytest (die Wegwerf-DBs leben nur während des Nachweises).

    python id1_abgleich.py <url_vorher> <url_nachher>

Geprüft wird Zusage I3: gleiche Zeilenzahl je Tabelle, und JEDE Beziehung auf
ein Mitglied (Gruppe, Plan, Dienst, Beziehung, Konto, Nachweis) zeigt danach
auf dieselbe Person — erkannt über vorname/nachname/email, NICHT über die
Kennung. Die Beziehungsspalten werden aus `pg_constraint` der Kopie gelesen
(nicht von Hand gepflegt): was dort als FK auf `mitglied.name` steht, muss den
Umzug überlebt haben.

Zusätzlich: die Kandidatenregel aus O1 (`^[0-9a-f]{8}-[0-9a-f]$`) — nach dem
Umschlüsseln darf keine Kennung mehr außerhalb des Musters stehen, und keine
Kennung darf einen Klarnamen tragen.
"""
from __future__ import annotations

import sys

import sqlalchemy as sa

#: Spalten, an denen eine Person wiedererkannt wird. NUR Stammdaten, die das
#: Umschlüsseln nicht anfassen darf — die Kennung selbst gehört ausdrücklich
#: nicht dazu (sie ändert sich ja).
STAMM = ("vorname", "nachname", "email", "status", "ausgeschlossen", '"user"',
         "geburtstag", "telefonnummer", "foto", "notiz", "creation")

#: Wert-Spalten OHNE Fremdschlüssel, die eine Kennung als GANZEN Wert tragen
#: (`dsgvo_anonymisierung.WERT_SPALTEN`). Sie werden hier eigens verglichen,
#: weil `pg_constraint` sie nicht kennt.
WERT_SPALTEN = (("pr_merkmal_wert", "ziel_id"), ("audit_log", "target_name"),
                ("notification_log", "document_name"), ("file", "attached_to_name"))

#: KIND-/VERWEISSPALTEN OHNE FREMDschlüssel (R-ID-1, Blocker B1). Sie werden
#: aus `pg_catalog` ermittelt, NICHT aus der Migrationsliste — sonst prüfte der
#: Abgleich genau die Liste, deren Lücke er finden soll (die Ironie aus R-ID-1:
#: der frühere Abgleich meldete 0, weil er dieselbe Handliste benutzte).
KIND_VERWEIS_PAARE = (
    ("parent", "parenttype"),          # Frappe-Kindtabellen
    ("link_name", "link_doctype"),     # dynamic_link
)

#: Tabellen, in denen überhaupt eine Mitglied-Kennung in der Verweis-/Kindspalte
#: stehen kann. Enthalten die Spalte UND die zugehörige Doctype-Spalte.
#:
#: Absichtlich NICHT hier: `element_mitarbeiter`, `dienstplan_*`,
#: `gruppenmitgliedschaft` usw. — sie tragen ihre Kennung in einer eigenen
#: Spalte MIT Fremdschlüssel und werden über `pg_constraint` geprüft. Die
#: Selbstbezüge `mitglied.ehepartner`/`elternteil` sind ebenfalls FKs.
VERWEIS_MITGLIED = (
    ("mitglied_beziehung", "parent", "parenttype"),
    ("mitglied_bereich", "parent", "parenttype"),
    ("dynamic_link", "link_name", "link_doctype"),
)

#: Abbildungstabelle der Migration alt -> neu (nur im Zustand „migriert“ da).
ABBILDUNG = "id1_mitglied_kennung"

#: Doctype-Wert, an dem ein Mitgliedsbezug erkannt wird.
MITGLIED = "Mitglied"

#: ANZEIGENAMEN-Spalten (R-ID-1: ausdrücklich KEINE Kennung). `user.full_name`
#: und `ressourcen_buchung.gebucht_von_name` sind Namen der Person, `autor` in
#: `wiki_artikel` ebenso; sie dürfen — müssen sogar — unverändert bleiben.
#: Deshalb sind sie aus dem Wert-Scan ausgenommen und werden getrennt gemeldet.
ANZEIGENAME_SPALTEN = (
    ("user", "full_name"),
    ("ressourcen_buchung", "gebucht_von_name"),
    ("wiki_artikel", "autor"),
    ("beitrag", "autor"), ("beitrag_kommentar", "autor"),
)


def _zeilen(eng) -> dict[str, int]:
    with eng.connect() as c:
        tabellen = c.execute(sa.text(
            "select table_name from information_schema.tables "
            "where table_schema = 'public' and table_type = 'BASE TABLE' "
            "and table_name <> 'alembic_version' order by 1")).scalars().all()
        return {t: int(c.execute(sa.text(f'select count(*) from "{t}"')).scalar())
                for t in tabellen}


def _person(eng, name: str) -> tuple:
    with eng.connect() as c:
        spalten = ", ".join(STAMM)
        return tuple(c.execute(sa.text(
            f"select {spalten} from mitglied where name = :n"), {"n": name}).one())


def _abbildung(eng) -> dict[str, str]:
    with eng.connect() as c:
        return dict(c.execute(sa.text(
            "select alt, neu from id1_mitglied_kennung")).all())


def _fk_spalten(eng) -> list[tuple[str, str]]:
    """Alle FK-Spalten der Kopie, die auf `mitglied.name` zeigen."""
    with eng.connect() as c:
        return [tuple(r) for r in c.execute(sa.text(
            "select c.conrelid::regclass::text, a.attname "
            "from pg_constraint c "
            "join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey) "
            "where c.contype = 'f' and c.confrelid = 'mitglied'::regclass "
            "order by 1, 2")).all()]


def _pk(c, tabelle: str):
    return c.execute(sa.text(
        "select a.attname from pg_index i join pg_attribute a "
        "on a.attrelid = i.indrelid and a.attnum = i.indkey[0] "
        "where i.indrelid = cast(:t as regclass) and i.indisprimary"), {"t": tabelle}).scalar()


def _beziehungen(eng, spalten) -> dict:
    """Prüfsumme je Beziehung — über die PERSON, nicht über die Kennung.

    Der VERWEIS wird über den Namen aufgelöst (vorname, nachname, email der
    Person hinter dem Wert), die Zeile selbst über ihren Primärschlüssel. Bei
    `mitglied` ist der Primärschlüssel die Kennung, die sich ändert — dort
    zählt deshalb zusätzlich der Hinweis des Selbstbezugs (`ehepartner`,
    `elternteil`): die Person, auf die die Zeile zeigt. Sonst ließe sich eine
    gedrehte Kante („Markus zeigt auf Julia“ -> „Julia zeigt auf Markus“)
    nicht von der richtigen unterscheiden.
    """
    ergebnis = {}
    with eng.connect() as c:
        for tabelle, spalte in spalten:
            pk = _pk(c, tabelle)
            if pk is None:
                continue
            if pk == "name" and tabelle == "mitglied":
                # Wert -> Person; Zeile -> Person über ihre Stammdaten.
                zeilen = c.execute(sa.text(
                    'select m.vorname, m.nachname, m.email, '      # Zeile
                    '       z.vorname, z.nachname, z.email '        # Verweisziel
                    'from mitglied m left join mitglied z on z.name = m."%s"'
                    % spalte
                )).all()
            else:
                # Wert -> Person (vorname, nachname, email); bleibt der Wert ein
                # Nicht-Mitglied (Lied, Sammlung), steht er selbst da.
                zeilen = c.execute(sa.text(
                    f'select t."{pk}"::text, t."{spalte}"::text, '
                    f'       m.vorname, m.nachname, m.email '
                    f'from "{tabelle}" t left join mitglied m on m.name = t."{spalte}"'
                )).all()
            if tabelle == "mitglied":
                ergebnis[f"{tabelle}.{spalte}"] = {
                    (z[0], z[1], z[2]): (z[3], z[4], z[5]) for z in zeilen}
            else:
                ergebnis[f"{tabelle}.{spalte}"] = {
                    zeile[0]: (zeile[2], zeile[3], zeile[4])
                    if zeile[2] is not None else zeile[1]
                    for zeile in zeilen}
    return ergebnis



def main(vorher: str, nachher: str) -> int:
    e_vor, e_nach = sa.create_engine(vorher), sa.create_engine(nachher)
    fehler = 0

    z_vor, z_nach = _zeilen(e_vor), _zeilen(e_nach)
    # Die Abbildungstabelle legt die Migration selbst an — sie ist kein
    # Datenverlust, sondern das Protokoll des Umzugs.
    z_vor.pop(ABBILDUNG, None)
    z_nach.pop(ABBILDUNG, None)
    abw = {t: (z_vor.get(t), z_nach.get(t)) for t in set(z_vor) | set(z_nach)
           if z_vor.get(t) != z_nach.get(t)}
    print(f"Tabellen: {len(z_vor)} vorher / {len(z_nach)} nachher")
    print(f"Zeilen gesamt: {sum(z_vor.values())} -> {sum(z_nach.values())}")
    print(f"Tabellen mit abweichender Zeilenzahl: {abw or 'keine'}")
    if abw:
        fehler += 1

    abbildung = _abbildung(e_nach)
    print(f"Umgeschlüsselt: {len(abbildung)} Mitglieder "
          f"(davon Kennungen mit Leerzeichen/@: "
          f"{sum(1 for a in abbildung if ' ' in a or '@' in a)})")
    print(f"mitglied-Zeilen vorher/nachher: "
          f"{z_vor.get('mitglied')} / {z_nach.get('mitglied')}")

    # Jede Person behält ihre Stammdaten — auch email='-' bleibt '-' (O2).
    abweichend = [alt for alt, neu in abbildung.items()
                  if _person(e_vor, alt) != _person(e_nach, neu)]
    print(f"Personen mit abweichenden Stammdaten: {abweichend or 'keine'}")
    if abweichend:
        fehler += 1

    # Jede Beziehung zeigt auf dieselbe Person — FKs aus pg_constraint plus
    # die Wert-Spalten ohne FK.
    fk_spalten = _fk_spalten(e_vor)
    print(f"FK-Spalten auf mitglied.name: {len(fk_spalten)}")
    b_vor = _beziehungen(e_vor, fk_spalten + list(WERT_SPALTEN))
    b_nach = _beziehungen(e_nach, fk_spalten + list(WERT_SPALTEN))
    kaputt = []
    for schluessel, werte in b_vor.items():
        neu_werte = b_nach.get(schluessel, {})
        for pk, person in werte.items():
            if neu_werte.get(pk) != person:
                kaputt.append((schluessel, pk, person, neu_werte.get(pk)))
    print(f"Beziehungen geprüft: {sum(len(v) for v in b_vor.values())} "
          f"in {len(b_vor)} Spalten")
    print(f"Beziehungen mit anderer Person: {len(kaputt)}")
    for eintrag in kaputt[:10]:
        print("   ", eintrag)
    if kaputt:
        fehler += 1

    # Kandidatenregel O1: keine Kennung mehr außerhalb des Musters.
    with e_nach.connect() as c:
        ausserhalb = c.execute(sa.text(
            "select name from mitglied where name !~ '^[0-9a-f]{8}-[0-9a-f]$' "
            "order by name")).scalars().all()
    print(f"Kennungen außerhalb des Musters nachher: {ausserhalb or 'keine'}")
    if ausserhalb:
        fehler += 1

    # Keine Kennung trägt danach noch einen Klarnamen bzw. eine Adresse.
    with e_nach.connect() as c:
        verdacht = [n for n in c.execute(sa.text("select name from mitglied")).scalars()
                    if " " in str(n) or "@" in str(n)]
    print(f"Kennungen mit Leerzeichen/@ (= Klarname/Adresse): {verdacht or 'keine'}")
    if verdacht:
        fehler += 1

    fehler += _waise(e_nach)

    print("ERGEBNIS:", "I3 erfüllt" if not fehler else f"I3 VERLETZT ({fehler} Punkte)")
    e_vor.dispose()
    e_nach.dispose()
    return 0 if not fehler else 1


def _waise(eng) -> int:
    """Unabhängiger Waisen-Scan (R-ID-1/B1) — NICHT über die Migrationsliste.

    Geprüft wird JEDE Spalte mit Mitgliedsbezug in DREI Schritten:

    1. Kind-/Verweisspalten, die aus `pg_catalog` ermittelt werden: welche
       Spalte heißt `parent` (mit `parenttype`) bzw. `link_name` (mit
       `link_doctype`) und hat Zeilen mit DocType `Mitglied`? Für jede solche
       Spalte muss der Wert eine existierende Mitglied-Kennung sein. Genau hier
       verwaisten die 3 Beziehungszeilen aus B1.
    2. Alle Fremdschlüsselspalten auf `mitglied.name` (aus `pg_constraint`).
    3. Alle Text-/JSON-Spalten: kein Wert darf mehr GENAU eine Alt-Kennung
       tragen (Anzeigenamen wie `user.full_name` sind erlaubt — sie sind keine
       Kennung; die Alt-Kennungen stehen in der Abbildung, die hier noch liegt).

    Rückgabe: Zahl der gefundenen Waisen (0 = sauber).
    """
    fehler = 0
    with eng.connect() as c:
        alt = {r[0] for r in c.execute(sa.text(f"select alt from {ABBILDUNG}"))}

        # 1) Kind-/Verweisspalten — Kandidaten aus pg_catalog.
        kandidaten = c.execute(sa.text(
            "select t.table_name, a.column_name, b.column_name "
            "from information_schema.columns a "
            "join information_schema.columns b "
            "  on b.table_schema = a.table_schema and b.table_name = a.table_name "
            "join information_schema.tables t "
            "  on t.table_schema = a.table_schema and t.table_name = a.table_name "
            "where a.table_schema = 'public' and t.table_type = 'BASE TABLE' "
            "  and (a.column_name, b.column_name) in (('parent','parenttype'),"
            "       ('link_name','link_doctype'))")).all()
        print(f"Kind-/Verweisspalten aus pg_catalog: {len(kandidaten)}")
        for tabelle, spalte, doctype_spalte in kandidaten:
            belegt = c.execute(sa.text(
                f'select count(*) from "{tabelle}" where "{doctype_spalte}" = :d'
            ), {"d": MITGLIED}).scalar()
            if not belegt:
                continue
            waisen = c.execute(sa.text(
                f'select count(*) from "{tabelle}" x where x."{doctype_spalte}" = :d '
                f'  and x."{spalte}" is not null '
                f'  and not exists (select 1 from mitglied m where m.name = x."{spalte}")'
            ), {"d": MITGLIED}).scalar()
            print(f"  {tabelle}.{spalte} ({belegt} Mitglied-Zeilen): Waisen {waisen}")
            if waisen:
                fehler += int(waisen)

        # 2) Fremdschlüssel auf mitglied.name.
        for tabelle, spalte in _fk_spalten(eng):
            waisen = c.execute(sa.text(
                f'select count(*) from "{tabelle}" x where x."{spalte}" is not null '
                f'  and not exists (select 1 from mitglied m where m.name = x."{spalte}")'
            )).scalar()
            if waisen:
                print(f"  WAISE (FK) {tabelle}.{spalte}: {waisen}")
                fehler += int(waisen)

        # 3) Alle Text-/JSON-Spalten: alte Kennung als ganzer Wert?
        if alt:
            spalten = c.execute(sa.text(
                "select table_name, column_name, data_type from information_schema.columns "
                "where table_schema = 'public' "
                "  and data_type in ('character varying','text','json','jsonb') "
                "order by 1, 2")).all()
            treffer = []
            anzeigenamen = []
            for tabelle, spalte, _typ in spalten:
                if tabelle == ABBILDUNG:
                    continue
                n = c.execute(sa.text(
                    f'select count(*) from "{tabelle}" where "{spalte}"::text = any(:a)'
                ), {"a": list(alt)}).scalar()
                if not n:
                    continue
                ziel = anzeigenamen if (tabelle, spalte) in ANZEIGENAME_SPALTEN\
                    else treffer
                ziel.append((tabelle, spalte, int(n)))
            print(f"Wert-Spalten mit alter Kennung: {treffer or 'keine'}")
            print(f"Anzeigenamen-Spalten mit dem Klarnamen (erwartet, keine Kennung): "
                  f"{anzeigenamen or 'keine'}")
            if treffer:
                fehler += len(treffer)

    print(f"Waisen/Eigentreffer gesamt: {fehler}")
    return fehler


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
