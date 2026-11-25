"""PERF-K4a — Anzeigenamen der Kalender-Moderation: EIN Vorrat statt je Zeile.

DER BEFUND (PERF-K3, live auf Postgres, 2240 Termine, 472 Vorschlaege/160
Konflikte): ``get_kanban_board_data`` brauchte als Admin 3834 Abfragen / 9,9 s.
3742 davon (98 %) kamen aus ``_anzeigename`` — je Zeile ``PersonenSicht.aus()``
(zwei Abfragen), je Zeile ein Mitglied (``get_all``) und je Zeile der
User-Name (``get_value``); dazu zwei ``get_value`` je Kalender.

WAS HIER FESTGEHALTEN WIRD
--------------------------
1. GLEICHHEIT: dieselbe Antwort wie die ABGELOESTE Rechnung. Der alte
   ``_anzeigename`` steht unten wortgleich als Zeuge und wird in den ECHTEN
   Endpunkt eingesetzt — verglichen wird die ganze Antwort (alle Listen, alle
   Felder, Reihenfolge) fuer sechs Rollen.

2. ABFRAGEN-OBERGRENZE: 50 Vorschlaege kosten weniger als 30 Abfragen, und
   die KOSTEN HAENGEN NICHT an der Zahl der Vorschlaege (50 vs. 100: gleich).

3. MUTATION: ein absichtlich falscher Vorrat macht (1) rot. Ohne diesen
   Nachweis koennte der Gleichheitstest gruen sein, weil er den Vorrat gar
   nicht sieht. Beleg (rot/grün) steht im Kommentar der Karte.

4. VORRAT: die beiden Sammelabfragen liefern je Kennung genau die Zeile, die
   die alte Einzelabfrage lieferte (``Mitglied.user``; der Vorrat ist nur eine
   OBERMENGE, entschieden wird an den Feldern).

Warum eine eingesetzte Altfassung statt eines Schalters: der Umbau hat keine
Betriebsart (kein Feature-Flag) — die neue Rechnung ist die einzige. Damit der
Vergleich trotzdem ehrlich bleibt, laeuft der alte Code als Zeuge mit.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import event

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren/Registrierung
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
from diakronos_app.models.kronos import Element, Kalender
from diakronos_app.models.rechte import (
    RechteFreigabe,
    RechteGruppenrolle,
    RechteModul,
    RechteObjekt,
)

# Obergrenze fuer das ganze Brett bei 50 Vorschlaegen (Rechte, Kalender,
# Termine, Staging, Namensvorrat). PERF-K3 zaehlte je Zeile; hier steht die
# Summe. Luft nach oben, damit eine zusaetzliche Sicht-/Rechteabfrage nicht
# sofort reisst — aber weit unter der Zahl der Zeilen (62 Termine).
HOECHSTENS_ABFRAGEN = 30

ADMIN = "k4-admin@example.org"
HV = "k4-hv@example.org"
MV = "k4-mv@example.org"
MITGLIED = "k4-mitglied@example.org"
AUSGETRETEN = "k4-ausgetreten@example.org"   # Moderator, Mitglied ausgetreten
GAST = "k4-gast@example.org"                 # angemeldet, ohne Mitgliedszeile

NUTZER = (ADMIN, HV, MV, MITGLIED, AUSGETRETEN, GAST)
KAL_MOD = [f"KAL-K4-{i}" for i in range(3)]
# Eigener Moderationskalender fuer die GELOESCHTE Person. Sie muss allein auf
# einem Brett stehen, das KEINER Moderator sieht: nur der Administrator kommt
# hin. So faellt die Regel „geloescht -> immer Geloeschte Person“ auf und
# nicht die Rollenfrage.
KAL_WEG = "KAL-K4-WEG"
KAL_LESEN = "KAL-K4-LESEN"
KAL_WAISE = "KAL-K4-WAISE"      # Rechte-Eintrag OHNE Kalender-Zeile
#: Wie die ANZEIGEREGEL eine ausgetretene Person fuer Nicht-Admins kuerzt
#: (`personen_anzeige.kuerze_name`: „Vorname N.“ — erster Buchstabe des
#: Nachnamens). Hier ausgeschrieben, damit der Test die Regel nennt.
AUSGETRETEN_ANZEIGE = "Person 0."


@pytest.fixture()
def kanbanwelt(patched_db):
    """Kleine, aber vollstaendige Moderationswelt (die Fixture COMMITTET).

    Enthalten sind genau die Faelle, an denen der Anzeigename scheitern kann:

    * aktives Mitglied (Klarname fuer alle),
    * AUSGETRETENES Mitglied, das zugleich Moderator ist (Nicht-Admins sehen
      die Kurzform, der Admin den Klarnamen — die Kernregel),
    * Konto ohne Mitgliedszeile (Rueckfall auf ``User.full_name``),
    * Antragsteller ohne jedes Konto (Rueckfall auf die Kennung selbst),
    * geloeschte Person als Antragsteller (immer „Geloeschte Person“),
    * Moderationskalender OHNE Zeile (verwaister Rechte-Eintrag): Titel =
      Kennung, Standardfarbe — der alte ``get_value``-Zweig.
    """
    from diakronos_app.models.core import HasRole as _HasRole

    sess = patched_db()
    konten = list(NUTZER) + [f"k4-person{i:02d}@example.org" for i in range(12)]
    sess.add_all([User(name=k, email=k, full_name=f"Person {i:02d}", enabled=True,
                       user_type="System User") for i, k in enumerate(konten)])
    sess.commit()
    sess.add_all([
        HasRole(name=f"HR-K4-{i}", parent=k, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1) for i, k in enumerate(konten)
    ])
    sess.add(_HasRole(name="HR-K4-MITGLIEDERVERW", parent=HV, parenttype="User",
                      parentfield="roles", role="Mitglied", docstatus=0, idx=2))
    sess.add(Gruppe(name="GR-K4", gruppenname="Gemeinde K4", docstatus=0, idx=0))
    sess.flush()

    mitglieder = [
        Mitglied(name=f"MIT-K4-{i:02d}", vorname="Person", nachname=f"{i:02d}",
                 email=k, user=k, status="Aktiv", ausgeschlossen=0,
                 docstatus=0, idx=i)
        for i, k in enumerate(konten)
    ]
    # Index 4 = AUSGETRETEN (und trotzdem Moderator).
    mitglieder[4].status = "Ausgetreten"
    mitglieder[4].austritt_datum = date(2026, 3, 1)
    # Geloeschte Person (DSGVO-2d): Anzeige „Geloeschte Person“.
    mitglieder.append(Mitglied(
        name="geloescht-0123abcd", vorname="Weg", nachname="Damit",
        email="k4-weg@example.org", user="k4-weg@example.org",
        status="geloescht", ausgeschlossen=0, docstatus=0, idx=90))
    sess.add_all(mitglieder)
    sess.flush()
    sess.add_all([
        Gruppenmitgliedschaft(name=f"GM-K4-{i}", parent="GR-K4", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied=m.name, status="Aktiv",
                              docstatus=0, idx=i)
        for i, m in enumerate(mitglieder) if m.name != "MIT-K4-05"  # k4-gast ohne Mitglied
    ])
    # Untergruppe UG-K4: ihr gehoert der Kalender, den ein Moderator nur
    # LESEN darf (s. Kalender-Abschnitt).
    from diakronos_app.models.diakonos import Untergruppe

    sess.add(Untergruppe(name="UG-K4", gruppe="GR-K4", untergruppenname="Untergruppe K4",
                         docstatus=0, idx=0))
    sess.flush()
    sess.add_all([
        # Moderatoren sind die LEITUNG der Gruppe (HV/MV) — der Rechte-Kern
        # vergibt `pruefstufen` ueber `hauptleitung`, NICHT ueber die
        # `moderieren`-Freigabe der RechteZeile. Die AUSGETRETENE Person ist
        # ebenfalls Moderatorin; MV, weil jede Hauptgruppe genau EINEN HV hat
        # (`uq_rechte_gruppenrolle_ein_hv`).
        RechteGruppenrolle(gruppe="GR-K4", untergruppe=None, benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="GR-K4", untergruppe=None, benutzer=MV, rolle="MV"),
        RechteGruppenrolle(gruppe="GR-K4", untergruppe=None, benutzer=AUSGETRETEN,
                           rolle="MV"),
        RechteModul(gruppe="GR-K4", modul="kalender"),
    ])
    sess.flush()

    sess.add_all([
        Kalender(name=KAL_MOD[0], calendar_name="Moderationskalender 0",
                 calendar_color="#112233", docstatus=0, idx=0),
        # Kalender-Zeile ohne Name/Farbe -> die Vorgaben muessen greifen.
        Kalender(name=KAL_MOD[1], calendar_name=None, calendar_color=None,
                 docstatus=0, idx=1),
        Kalender(name=KAL_MOD[2], calendar_name="Moderationskalender 2",
                 calendar_color="#445566", docstatus=0, idx=2),
        Kalender(name=KAL_LESEN, calendar_name="Nur lesen",
                 calendar_color="#778899", docstatus=0, idx=3),
        Kalender(name=KAL_WEG, calendar_name="Nachlass",
                 calendar_color="#99aabb", docstatus=0, idx=4),
    ])
    sess.flush()
    sess.add_all([
        RechteObjekt(typ="kalender", objekt=k, gruppe="GR-K4",
                     gemeinde_status="aus", gruppe_status="aktiv")
        for k in [*KAL_MOD, KAL_WAISE]
    ] + [
        # KAL-LESEN gehoert der UNTERGRUPPE UG-K4. Eine Freigabe „moderieren“
        # an der Gruppe haelt die Leitung davon NICHT zum Moderator
        # (Rechte-Kern: `moderieren and not eintrag.untergruppe`) — genau so
        # sieht ein Kalender aus, den ein Moderator nur LESEN darf.
        RechteObjekt(typ="kalender", objekt=KAL_LESEN, gruppe="GR-K4",
                     untergruppe="UG-K4", gemeinde_status="aus",
                     gruppe_status="aktiv"),
        # Gemeinde-Kalender OHNE Gruppe: nur der Administrator (Rechte-Kern).
        RechteObjekt(typ="kalender", objekt=KAL_WEG, gruppe=None,
                     gemeinde_status="aus", gruppe_status=None),
    ])
    sess.add_all([
        RechteFreigabe(typ="kalender", objekt=k, gruppe="GR-K4",
                       lesen=True, schreiben=True, moderieren=True)
        for k in [*KAL_MOD, KAL_WAISE]
    ])
    sess.add(RechteFreigabe(typ="kalender", objekt=KAL_LESEN, gruppe="GR-K4",
                            lesen=True, schreiben=True, moderieren=False))
    sess.flush()

    start = datetime(2026, 11, 2, 9, 0)
    elemente = []
    for i in range(50):
        s = start + timedelta(hours=i)
        elemente.append(Element(
            name=f"EL-K4-V{i:03d}", element_name=f"Vorschlag {i}",
            element_calendar=KAL_MOD[i % 3], element_start=s,
            element_end=s + timedelta(hours=1), all_day=False,
            status="Vorschlag", owner=konten[i % len(konten)],
            repeat_this_event=0, docstatus=0, idx=i))
    for i in range(12):
        s = start + timedelta(hours=100 + i)
        elemente.append(Element(
            name=f"EL-K4-K{i:03d}", element_name=f"Konflikt {i}",
            element_calendar=KAL_MOD[i % 3], element_start=s,
            element_end=s + timedelta(hours=1), all_day=False,
            status="Konflikt", owner=konten[(i * 5) % len(konten)],
            repeat_this_event=0, docstatus=0, idx=100 + i))
    # Antragsteller einer GELOESCHTEN Person (eigener Kalender, s. KAL_WEG)
    # und einer ohne jedes Konto.
    elemente.append(Element(
        name="EL-K4-V-WEG", element_name="Vorschlag Geloescht",
        element_calendar=KAL_WEG, element_start=start,
        element_end=start + timedelta(hours=1), all_day=False,
        status="Vorschlag", owner="k4-weg@example.org",
        repeat_this_event=0, docstatus=0, idx=200))
    elemente.append(Element(
        name="EL-K4-V-OFFEN", element_name="Vorschlag ohne Konto",
        element_calendar=KAL_MOD[1], element_start=start,
        element_end=start + timedelta(hours=1), all_day=False,
        status="Vorschlag", owner="k4-gibtsnicht@example.org",
        repeat_this_event=0, docstatus=0, idx=201))
    # Abgelehnt (Historie-Spalte, eigener Weg, eigener Moderator).
    for i in range(3):
        elemente.append(Element(
            name=f"EL-K4-A{i}", element_name=f"Abgelehnt {i}",
            element_calendar=KAL_MOD[i % 2],
            element_start=start + timedelta(days=10),
            element_end=start + timedelta(days=10, hours=1), all_day=False,
            status="Abgelehnt", owner=konten[i], moderiert_von=AUSGETRETEN,
            ablehnungs_grund="Termin doppelt", repeat_this_event=0,
            docstatus=0, idx=300 + i))
    sess.add_all(elemente)
    sess.commit()
    return sess


# ── Der ABGELOESTE Endpunkt (Stand vor PERF-K4a), als Zeuge ────────────────
def _alte_anzeigename(kennung: str | None) -> str:
    """Wortgleich ``_anzeigename`` vor dieser Karte."""
    from diakronos_app.frappe_compat.api_helpers import get_all, get_value
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, anzeigename

    if not kennung:
        return ""
    if kennung == "Administrator":
        return "Administrator"
    try:
        mitglieder = get_all(
            "Mitglied",
            filters={"user": kennung},
            fields=["name", "vorname", "nachname", "ausgeschlossen", "status",
                    "austritt_datum"],
            limit_page_length=1,
        ) or []
        if mitglieder:
            return anzeigename(mitglieder[0], sicht=PersonenSicht.aus())
        row = get_value("User", kennung, ["full_name"], as_dict=True) or {}
        name = row.get("full_name") if isinstance(row, dict) else None
        if name:
            return name
    except Exception:  # noqa: BLE001 — wie im Original
        pass
    return kennung


def _alte_ausgabe() -> dict:
    """Der ECHTE Endpunkt mit der ALTEN Namensrechnung.

    Statt seinen Code nachzubauen, wird nur die Namenshilfe ausgetauscht: ein
    Ersatz-``_anzeigename`` im Modul, und ``_fmt_event`` OHNE Vorrat (dann
    faellt es je Zeile auf die Einzelrechnung zurueck). Alles andere —
    Rechte-Stufen, Kalender-Vorrat, Staging — laeuft unveraendert.
    """
    import diakronos_app.api.kronos.kanban_api as K

    gesichert = K._anzeigename
    K._anzeigename = _alte_anzeigename  # type: ignore[assignment]
    # Der Vorrat muss WEG sein: sonst naehme `_fmt_event` ihn (der heutige
    # Endpunkt ruft `Anzeigenamen(...)`). Ersatz: ein Vorrat, der jede Kennung
    # ueber die alte Einzelrechnung beantwortet.
    echter_vorrat = K.Anzeigenamen
    K.Anzeigenamen = _AlterVorrat  # type: ignore[assignment]
    try:
        return K.get_kanban_board_data()
    finally:
        K._anzeigename = gesichert  # type: ignore[assignment]
        K.Anzeigenamen = echter_vorrat  # type: ignore[assignment]


class _AlterVorrat:
    """Steht fuer ``Anzeigenamen`` und rechnet je Kennung ALT (kein Vorrat)."""

    def __init__(self, kennungen=None) -> None:  # noqa: ARG002 — Signaturgleich
        pass

    def name(self, kennung: str | None) -> str:
        return _alte_anzeigename(kennung)


def _antwort(nutzer: str, welt) -> dict:
    """Die Antwort des Endpunkts fuer einen Nutzer (echte Sitzung)."""
    from diakronos_app.api.kronos.kanban_api import get_kanban_board_data
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user(nutzer)
    with merkungsrahmen(), als_aktuelle_sitzung(welt):
        return get_kanban_board_data()


def _anzahl(welt, nutzer: str, engine) -> tuple[int, int]:
    """(Termine im Ergebnis, SQL-Abfragen) eines Brett-Aufrufs."""
    from diakronos_app.api.kronos.kanban_api import get_kanban_board_data
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    zaehler = {"n": 0}

    def _zaehle(conn, cursor, statement, parameters, context, executemany):
        zaehler["n"] += 1

    set_user(nutzer)
    event.listen(engine, "before_cursor_execute", _zaehle)
    try:
        with merkungsrahmen(), als_aktuelle_sitzung(welt):
            erg = get_kanban_board_data()
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)
    return len(erg["vorschlaege"]) + len(erg["konflikte"]), zaehler["n"]


@pytest.mark.parametrize("nutzer", NUTZER)
def test_perf_k4a_gleichheit_alt_gegen_neu(kanbanwelt, nutzer):
    """Dieselbe Antwort wie die alte Zeilen-Rechnung — Feld fuer Feld.

    Der Vergleich laeuft gegen DENSELBEN Endpunkt (nur die Namenshilfe ist
    ausgetauscht), deshalb deckt er auch Kalender-Vorrat, Staging und die
    Rechte-Stufen ab. Sechs Rollen: Admin (vollstaendig), HV, MV, Mitglied,
    Moderator der ausgetretenen Person, Konto ohne Mitglied.
    """
    from diakronos_app.api.kronos.permissions import get_accessible_calendars
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    # Fixpunkt: HV, MV und die ausgetretene Moderatorin moderieren ALLE
    # Kalender der Gruppe (die Leitung prueft die Stufe `gruppe`, damit auch
    # KAL-LESEN), die uebrigen Rollen keinen. Ohne diese Zusage koennte ein
    # Gleichheitstest auf zwei LEEREN Antworten bestehen und nichts zeigen.
    # Der Admin ist im LEEREN Sinn kein Moderator (sein Brett laeuft ueber
    # `Kalenderadministrator`, s. `_mod_calendars`), sieht hier aber alles.
    set_user(nutzer)
    with merkungsrahmen(), als_aktuelle_sitzung(kanbanwelt):
        moderiert = {c["name"] for c in get_accessible_calendars()
                     if c.get("is_moderator")}
    assert moderiert == (set(KAL_MOD) | {KAL_LESEN}
                        if nutzer in (HV, MV, AUSGETRETEN) else set()), \
        f"{nutzer} moderiert {sorted(moderiert)}"

    neu = _antwort(nutzer, kanbanwelt)
    alt = _alte_ausgabe()
    assert neu == alt, f"{nutzer}: Antwort weicht von der alten Rechnung ab"


def test_perf_k4a_anzeigeregeln_sind_wirklich_drin(kanbanwelt):
    """Der Gleichheitstest ist nicht blind: die Kernregeln stehen drin.

    Ohne diese Probe koennten beide Laeufe gleich FALSCH sein (etwa wenn der
    Name ueberall nur die Kennung waere).
    """
    # Der ADMIN als `Administrator` (Login-Kurzschluss des Rechte-Kerns):
    # der `System Manager` ist hier Admin der MITGLIEDER, nicht der Kalender
    # (`_mod_calendars` fragt `is_moderator`, und das ist `Kalenderadministrator`
    # bzw. die Gruppenleitung).
    admin = _antwort("Administrator", kanbanwelt)
    hv = _antwort(HV, kanbanwelt)
    namen_admin = {e["antragsteller"] for e in admin["vorschlaege"] + admin["konflikte"]}
    namen_hv = {e["antragsteller"] for e in hv["vorschlaege"] + hv["konflikte"]}
    assert namen_admin, "Admin-Brett ist leer — Probe waere blind"

    # Die AUSGETRETENE Person als Antragstellerin: die Kuerzungsregel greift —
    # ein Moderator sieht „Person 0.“ (Vorname + Anfangsbuchstabe), der
    # `Administrator` den Klarnamen. Genau dieser Unterschied beweist, dass die
    # EINE `PersonenSicht` des Aufrufers noch wirkt und nicht etwa alle Namen
    # gleich behandelt werden.
    assert AUSGETRETEN_ANZEIGE in namen_hv, namen_hv
    assert "Person 04" not in namen_hv, namen_hv
    # ACHTUNG (bewusst NICHT geaendert): `PersonenSicht.aus()` fragt die
    # SITZUNG (`session.user`) — im Test ist das die Test-Naht-Identitaet,
    # nicht der `Administrator`. Deshalb kuerzt die Regel hier auch fuer den
    # Administrator-LOGIN. Dasselbe galt fuer `_anzeigename` vor dieser Karte;
    # die Bedingung „byte-gleich“ haelt das fest. Wer die Sicht auf den
    # ADMINISTRATOR statt auf die Sitzung umstellen will, aendert die
    # Anzeigeregel selbst — das ist eine eigene Entscheidung (Operator).
    assert [e["antragsteller"] for e in admin["vorschlaege"] if e["id"] == "EL-K4-V004"] \
        == [AUSGETRETEN_ANZEIGE]
    # Geloeschte Person: EIN Text — auf JEDEM Brett, auf dem sie steht, und
    # auch fuer den `Administrator`. Ihr Kalender KAL-K4-WEG haengt an keiner
    # Gruppe; erreichbar ist er nur ueber den Login-Kurzschluss `Administrator`
    # (der Login `k4-admin@…` ist System Manager der MITGLIEDER, nicht
    # Kalender-Moderator — s. `_mod_calendars`).
    # Der Login `Administrator` kommt an KAL-K4-WEG (gemeindeweit, ohne
    # Gruppe); ein Moderator sieht diesen Kalender nicht. Dort steht eine
    # GELOESCHTE Person — und die Regel „geloescht -> nie ein Name“ greift
    # fuer den User-Zweig NICHT: die ALTE Einzelabfrage las `Mitglied.user`
    # und verwarf geloeschte Zeilen (`ist_geloeschte_zeile` in
    # `_anzeigename`-Nachfolger), deshalb stand dort schon immer die rohe
    # Kennung. Byte-Gleichheit heisst: es bleibt so (Befund im Handoff).
    weg_admin = [e["antragsteller"] for e in admin["vorschlaege"]
                 if e["id"] == "EL-K4-V-WEG"]
    # Operator-Review: die alte Einzelabfrage lieferte die geloeschte Zeile,
    # also stand dort schon immer „Geloeschte Person“ — nie die Kennung.
    assert weg_admin == ["Gelöschte Person"], weg_admin
    assert not any("k4-weg@example.org" in n for n in namen_hv), namen_hv
    mv = _antwort(MV, kanbanwelt)
    assert mv["vorschlaege"], "MV-Brett ist leer — Probe waere blind"
    # `moderiert_von` ist eine ROHE Kennung (kein Anzeigename) — in JEDER
    # Rolle dieselbe. Waere sie gekuerzt, verloere die Pruefliste den Namen
    # des Moderators.
    mods_admin = {e["moderiert_von"] for e in admin["abgelehnt"]}
    mods_mv = {e["moderiert_von"] for e in mv["abgelehnt"]}
    assert mods_admin and mods_mv, (mods_admin, mods_mv)
    assert mods_admin == {AUSGETRETEN}, mods_admin
    assert mods_mv == {AUSGETRETEN}, mods_mv
    # Konto ohne Mitglied -> User-Name; ohne Konto -> die Kennung selbst.
    assert "Person 05" in namen_admin, namen_admin
    assert "k4-gibtsnicht@example.org" in namen_hv, namen_hv
    assert "k4-gibtsnicht@example.org" in namen_admin, namen_admin
    # Kalender: Name/Farbe aus dem Vorrat, fehlende Angaben -> Vorgaben.
    titel = {e["calendar"]: (e["calendar_title"], e["calendar_color"])
             for e in admin["vorschlaege"]}
    assert titel[KAL_MOD[0]] == ("Moderationskalender 0", "#112233")
    from diakronos_app.api.farbe import KALENDER_STANDARD_FARBE

    assert titel[KAL_MOD[1]] == (KAL_MOD[1], KALENDER_STANDARD_FARBE), titel[KAL_MOD[1]]
    assert titel[KAL_MOD[2]] == ("Moderationskalender 2", "#445566")


def test_perf_k4a_abfragen_unter_der_grenze(kanbanwelt, engine):
    """PERF-K4a: das Brett bei 50 Vorschlaegen kostet feste, kleine Zahl Abfragen.

    VORHER (PERF-K3, live): 3834 Abfragen, davon 3742 aus der Namensrechnung
    (eine Sicht-, eine Mitglieder- und eine User-Abfrage JE ZEILE). Der Test
    war vor der Behebung rot und ist danach gruen.
    """
    termine, abfragen = _anzahl(kanbanwelt, HV, engine)
    assert termine == 63, termine
    assert abfragen < HOECHSTENS_ABFRAGEN, (
        f"{abfragen} SQL-Abfragen fuer 50 Vorschlaege/12 Konflikte "
        f"(Obergrenze {HOECHSTENS_ABFRAGEN}; PERF-K3 live: 3834)")


def test_perf_k4a_abfragen_haengen_nicht_an_der_zeilenzahl(kanbanwelt, engine):
    """GLEICHHEIT, nicht nur eine Schranke: doppelt so viele Zeilen, gleiche Zahl."""
    _, klein = _anzahl(kanbanwelt, HV, engine)
    neu = []
    for i in range(50):
        s = datetime(2026, 12, 1, 9, 0) + timedelta(hours=i)
        neu.append(Element(
            name=f"EL-K4-Q{i:03d}", element_name=f"Zusatz {i}",
            element_calendar=KAL_MOD[i % 3], element_start=s,
            element_end=s + timedelta(hours=1), all_day=False,
            status="Vorschlag", owner=f"k4-person{i % 12:02d}@example.org",
            repeat_this_event=0, docstatus=0, idx=5000 + i))
    kanbanwelt.add_all(neu)
    kanbanwelt.commit()
    termine, gross = _anzahl(kanbanwelt, HV, engine)
    assert termine == 113, termine
    assert gross == klein, f"{gross} statt {klein} Abfragen bei doppelter Zeilenzahl"


def test_perf_k4a_vorrat_gleich_einzelabfrage(kanbanwelt):
    """Der VORRAT selbst stimmt mit der frischen Einzelabfrage ueberein.

    Je Kennung: was ``mitglieder_vorrat`` liefert, muss (an den Feldern
    entschieden, wie der Endpunkt es tut) dieselbe Zeile sein, die
    ``get_all("Mitglied", filters={"user": …})`` liefert — und der User-Vorrat
    muss den ``get_value``-Wert tragen. Geprueft werden auch Kennungen OHNE
    Treffer (die muessen fehlen, nicht „leer“ sein).
    """
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.frappe_compat.api_helpers import get_all, get_value
    from diakronos_app.frappe_compat.personen_anzeige import (
        benutzer_vorrat,
        mitglied_vorrat_pruefen,
        mitglieder_vorrat,
    )

    kennungen = list(NUTZER) + [f"k4-person{i:02d}@example.org" for i in range(12)]
    kennungen += ["k4-weg@example.org", "k4-gibtsnicht@example.org", "", None]
    with als_aktuelle_sitzung(kanbanwelt):
        vorrat = mitglieder_vorrat(kennungen)
        benutzer = benutzer_vorrat(kennungen)
        einzeln = {
            k: (get_all("Mitglied", filters={"user": k},
                        fields=["name", "vorname", "nachname", "ausgeschlossen",
                                "status", "austritt_datum"],
                        limit_page_length=1) or [])
            for k in kennungen if k
        }
        namen = {k: ((get_value("User", k, ["full_name"], as_dict=True) or {})
                     .get("full_name")) for k in kennungen if k}

    for kennung, treffer in einzeln.items():
        gewaehlt = [z for z in vorrat.get(kennung, [])
                    if mitglied_vorrat_pruefen(kennung, z)]
        if not treffer:
            assert not gewaehlt, (kennung, gewaehlt)
            assert kennung not in vorrat or not gewaehlt
        else:
            assert gewaehlt, (kennung, vorrat.get(kennung))
            assert gewaehlt[0]["name"] == treffer[0]["name"], (kennung, gewaehlt, treffer)
        assert benutzer.get(kennung) == (namen[kennung] or None), kennung
    # „Administrator“ wird nie nachgelesen (der Endpunkt short-schliesst).
    assert "Administrator" not in vorrat


@pytest.mark.parametrize(
    "pflanze",
    [
        lambda: ("komplett leer", lambda k: {}),
        lambda: ("falsche User-Namen", None),
    ],
    ids=["vorrat-leer", "user-namen-leer"],
)
def test_perf_k4a_mutation_macht_den_gleichheitstest_rot(kanbanwelt, pflanze):
    """MUTATION: ein absichtlich falscher Vorrat bricht die Gleichheit.

    Ohne diesen Nachweis waere unklar, ob (1) den Vorrat ueberhaupt sieht.
    Zwei Pflanzen: die Sammelabfrage liefert NICHTS (jeder Name faellt auf die
    Kennung zurueck) und der User-Vorrat liefert leere Namen. Beide muessen
    die Antwort veraendern — also ist (1) empfindlich genau gegen den Vorrat.
    """
    import diakronos_app.api.kronos.kanban_api as K
    import diakronos_app.frappe_compat.personen_anzeige as P

    bezeichnung, pflanzfunktion = pflanze()
    echt_mitglieder, echt_benutzer = P.mitglieder_vorrat, P.benutzer_vorrat
    if pflanzfunktion is None:
        # Nur der User-Vorrat wird verfaelscht: jeder Name ist leer. Die
        # Kennungen ohne Mitglied („Konto ohne Mitglied“) fallen dann auf die
        # Kennung zurueck statt auf `User.full_name` — sichtbar in der Antwort.
        P.mitglieder_vorrat = lambda kennungen: echt_mitglieder(kennungen)
        P.benutzer_vorrat = lambda kennungen: {k: "GEFAELSCHT" for k in kennungen}
    else:
        P.mitglieder_vorrat = pflanzfunktion
        P.benutzer_vorrat = pflanzfunktion
    try:
        neu = _antwort(HV, kanbanwelt)
    finally:
        P.mitglieder_vorrat, P.benutzer_vorrat = echt_mitglieder, echt_benutzer
    alt = _alte_ausgabe()
    assert neu != alt, f"Pflanze „{bezeichnung}“ blieb unsichtbar — Test ist blind"
    del K


@pytest.mark.parametrize("adresse", [None, "andere@example.org"],
                         ids=["email-leer", "email-anders"])
def test_perf_k4a_austritt_kurzform_auch_wenn_email_abweicht(kanbanwelt, adresse):
    """Operator-Review: Zuordnung NUR ueber ``Mitglied.user`` (wie die alte
    Einzelabfrage). Weicht ``email`` vom Login ab, darf die ausgetretene
    Person fuer Nicht-Admins NICHT mit Klarnamen erscheinen (Rueckfall auf
    ``User.full_name`` waere ein AUSTRITT-Leck)."""
    from diakronos_app.models.diakonos import Mitglied

    zeile = kanbanwelt.get(Mitglied, "MIT-K4-04")
    zeile.email = adresse
    kanbanwelt.commit()
    hv = _antwort(HV, kanbanwelt)
    namen_hv = {e["antragsteller"] for e in hv["vorschlaege"] + hv["konflikte"]}
    assert AUSGETRETEN_ANZEIGE in namen_hv, namen_hv
    assert "Person 04" not in namen_hv, namen_hv
