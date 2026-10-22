"""AUSTRITT-d — Restbefunde aus dem zweiten Review (R-AUSTRITT-2).

Die Karte fordert je Befund: Test vorher ROT, Fix, Test gruen, Commit. Diese
Datei ist der ROT-Beweis. Sie beschreibt Absicht und Pruefstand, nicht die
Loesung; die Tests bleiben nach dem Fix unveraendert gueltig.

* **NB1** — alte Plaene zeigen eine Ausgetretene wieder an (Anzeige aus der
  ungefilterten Personenquelle, Kurzform auch fuer das Kuerzel).
* **NB3** — die Art (``austritt``/``ausschluss``) kommt aus dem Backend.
* **NH1** — Austritt eines bereits Ausgeschlossenen wird abgelehnt.
* **NM2** — die Kontenlisten kuerzen nur Ausgetretene fuer Nicht-Admins.
* **NM3** — der Antragsteller im Moderations-Board laeuft ueber die zentrale
  Namensregel.
* **NN5** — der Zaehler am Status-Chip „Ausgetreten“ stimmt.
"""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

MA = "Mitgliederadministrator"

ADMIN = "verwaltung@x.org"
LESER = "leser@x.org"
#: Kennung (Mitglied.name) der Zielperson — im Betrieb ist das der Klarname,
#: fuer diese Proben genuegt die einfache Form.
ZIEL = "M-ziel"
ZIEL_KONTO = "ziel@x.org"


def _konto(sess, kennung: str, rolle: str | None = None, *,
           vorname: str = "Lena", nachname: str = "Leser",
           konto: str | None = None, enabled: bool = True) -> None:
    konto = konto or kennung
    sess.add(User(name=konto, email=konto, full_name=f"{vorname} {nachname}",
                  enabled=enabled))
    if rolle:
        sess.add(HasRole(name=f"HR-{kennung}-{rolle}", parent=konto,
                         parenttype="User", parentfield="roles", role=rolle,
                         docstatus=0, idx=1))
    sess.add(Mitglied(
        name=kennung, vorname=vorname, nachname=nachname,
        email=konto, status="Mitglied", user=konto,
        ausgeschlossen=0, docstatus=0, idx=0,
    ))
    sess.commit()


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    _konto(sess, ADMIN, MA, vorname="Anna", nachname="Admin", konto=ADMIN)
    _konto(sess, LESER, vorname="Lena", konto=LESER)
    _konto(sess, ZIEL, vorname="Elvira", nachname="Dorn",
           konto=ZIEL_KONTO, enabled=False)
    sess.flush()
    for name in (ADMIN, LESER, ZIEL):
        sess.get(Mitglied, name).ancestor_path = "/gemeinde/|"
    sess.commit()
    yield sess
    sess.close()
    set_user("Administrator")


def _austritt() -> None:
    from diakronos_app.api.austritt import mitglied_austritt

    set_user(ADMIN)
    mitglied_austritt(ZIEL, "", "2026-10-01")


def _reaktivieren() -> None:
    from diakronos_app.api.austritt import mitglied_reaktivieren

    set_user(ADMIN)
    mitglied_reaktivieren(ZIEL)


def _ausschluss() -> None:
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus

    set_user(ADMIN)
    schliesse_mitglied_aus(ZIEL)


# ── NB1: Anzeige in alten Plaenen ───────────────────────────────────────────


def test_nb1_altplan_zeigt_ausgetretene_weiter_an(welt) -> None:
    """Ein Plan mit einer Ausgetretenen behaelt deren Anzeigenamen.

    Die ZUTEILBARKEIT bleibt gefiltert (``personen()``), die ANZEIGE liest die
    ungefilterte Quelle: der Admin sieht den Klarnamen, der Leser
    „Elvira D.“ — nie leer, nie die Kennung. Das Kuerzel darf den Nachnamen
    nicht tragen („E. D.“, nicht „E. Dorn“).
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    sess = welt
    sess.expire_all()
    _austritt()
    sess.expire_all()

    for wer, erwartet, kuerzel_erwartet in (
        (ADMIN, "Elvira Dorn", "E. Dorn"),
        (LESER, "Elvira D.", "E. D."),
    ):
        set_user(wer)
        s = SessionLocal()
        try:
            quelle = DBDatenquelle(s)
            anzeige_namen = {p.kennung: p.name for p in quelle._quelle.personen()}
            kuerzel = {p.kennung: p.kuerzel for p in quelle._quelle.personen()}
        finally:
            s.close()
        assert anzeige_namen.get(ZIEL) == erwartet, f"{wer}: Anzeigename"
        assert kuerzel.get(ZIEL) == kuerzel_erwartet, f"{wer}: Kuerzel"
        assert "Dorn" not in kuerzel.get(ZIEL, "") or wer == ADMIN


def test_nb1_zuteilbarkeit_bleibt_gefiltert(welt) -> None:
    """Gegenprobe: als Kandidat ist die Ausgetretene weiterhin nicht da."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    sess = welt
    _austritt()
    sess.expire_all()
    set_user(ADMIN)
    s = SessionLocal()
    try:
        kandidaten = {p.kennung for p in DBDatenquelle(s).personen()}
    finally:
        s.close()
    assert ZIEL not in kandidaten


# ── NB3: die Art kommt aus dem Backend ──────────────────────────────────────


def _detail() -> dict:
    from diakronos_app.api import mitglieder as m

    perms = {
        "can_view": True, "can_edit": False, "can_delete": False,
        "can_view_sensitive": True, "reason": "test",
    }
    original = m.permissions.mitglied_permissions
    m.permissions.mitglied_permissions = lambda *a, **k: dict(perms)
    try:
        return m.get_mitglied_detail(ZIEL)["data"]
    finally:
        m.permissions.mitglied_permissions = original


def test_nb3_austritt_ohne_begruendung_meldet_art_austritt(welt) -> None:
    """Austritt ohne Begruendung: ``austritt.art == 'austritt'`` (nicht '')."""
    sess = welt
    set_user(ADMIN)
    _austritt()
    sess.expire_all()
    daten = _detail()
    assert daten["austritt"]["ausgetreten"] is True
    assert daten["austritt"]["art"] == "austritt", (
        "ohne Art leitet die Oberflaeche aus der (hier leeren) Begruendung "
        "einen Ausschluss ab")


def test_nb3_ausschluss_meldet_art_ausschluss(welt) -> None:
    """Ausschluss: ``austritt.art == 'ausschluss'``, ``ausgetreten`` False."""
    sess = welt
    set_user(ADMIN)
    _ausschluss()
    sess.expire_all()
    daten = _detail()
    assert daten["austritt"]["art"] == "ausschluss"
    assert daten["austritt"]["grund"] is None or daten["austritt"]["grund"] == ""


def test_nb3_altbestand_status_ohne_marke_meldet_art_austritt(welt) -> None:
    """Altbestand „Ausgetreten“ OHNE Marke (R-AUSTRITT-2, NN3).

    Der Status allein ist das Austrittsmerkmal (``ist_ausgeschieden``) — die
    Oberflaeche bietet dort „Reaktivieren“ an. Der Knopf nimmt den Austritt
    zurueck und stellt „Mitglied“ her (Kartentext, Punkt N).
    """
    sess = welt
    set_user(ADMIN)
    # Genau der Altbestand: Status „Ausgetreten“, Marke 0, kein Austrittsdatum.
    # (Der Fixture-Datensatz wird dafuer frisch geladen — die Sitzung haelt
    # sonst ein zwischenzeitlich geaendertes Objekt.)
    sess.expire_all()
    zeile = sess.get(Mitglied, ZIEL)
    zeile.status = "Ausgetreten"
    zeile.ausgeschlossen = 0
    zeile.austritt_datum = None
    sess.commit()
    daten = _detail()
    assert daten["austritt"]["art"] == "austritt"


def test_nb3_nichts_gesetzt_meldet_leere_art(welt) -> None:
    """Normale Person: leere Art."""
    sess = welt
    set_user(ADMIN)
    daten = _detail()
    assert daten["austritt"]["art"] == ""
    assert daten["austritt"]["ausgetreten"] is False


# ── NH1: Austritt eines Ausgeschlossenen ────────────────────────────────────


def test_nh1_austritt_bei_ausschluss_wird_abgelehnt(welt) -> None:
    """Erst Ausschluss aufheben — sonst waere „Reaktivieren“ der Seiteneingang.

    Ohne die Schranke hebt „Ausschluss → Austritt → Reaktivieren“ den
    Ausschluss still auf (R-AUSTRITT-2, NH1). Der Zustand muss dabei
    unveraendert bleiben.
    """
    from diakronos_app.frappe_compat.exceptions import ValidationError

    sess = welt
    _ausschluss()
    sess.expire_all()
    vorher = sess.get(Mitglied, ZIEL)
    vorher_status, vorher_seit = vorher.status, vorher.ausgeschlossen_seit

    with pytest.raises(ValidationError) as fehler:
        _austritt()
    assert "ausgeschlossen" in str(fehler.value).lower()
    assert "Ausschluss" in str(fehler.value)

    sess.expire_all()
    zeile = sess.get(Mitglied, ZIEL)
    assert zeile.status == vorher_status
    assert zeile.austritt_datum is None
    assert zeile.austritt_grund is None


# ── NM2: Kontenlisten kuerzen nur Ausgetretene, nur fuer Nicht-Admins ───────


def _konto_liste(wer: str) -> dict[str, str]:
    """Kontenliste des Aufrufers — ueber den Weg, der ihm offensteht.

    `get_konten_liste` verlangt eine Admin-Rolle (dort keine Kuerzung). Dem
    Kalenderadministrator steht `get_moderator_auswahl` offen; genau dort
    greift die Kuerzung (NM2).
    """
    from diakronos_app.api.zugang import get_konten_liste, get_moderator_auswahl

    set_user(wer)
    try:
        return {k["user"]: k["name"] for k in get_konten_liste()["konten"]}
    except Exception:  # noqa: BLE001 — Nicht-Admin: der schmale Weg
        return {k["user"]: k["name"] for k in get_moderator_auswahl()["konten"]}


def test_nm2_admin_sieht_klarnamen_in_kontenlisten(welt) -> None:
    """Ein Administrator sieht ALLE Namen voll — auch bei Ausgetretenen."""
    sess = welt
    _austritt()
    sess.expire_all()
    assert _konto_liste(ADMIN)[ZIEL_KONTO] == "Elvira Dorn"


def test_nm2_nicht_admin_sieht_ausgetretene_gekuerzt(welt) -> None:
    """Kalenderadministrator (kein Mitgliederadmin): Kurzform nur beim Austritt."""
    sess = welt
    sess.add(HasRole(name="HR-ka", parent=LESER, parenttype="User",
                     parentfield="roles", role="Kalenderadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _austritt()
    sess.expire_all()
    # Das Konto ist beim Austritt deaktiviert (`enabled=False`); die schmale
    # Auswahl bietet deaktivierte Konten nicht an (N12b). Fuer die Anzeige-
    # regel hier wieder einschalten.
    sess.get(User, ZIEL_KONTO).enabled = True
    sess.commit()
    assert _konto_liste(LESER)[ZIEL_KONTO] == "Elvira D."


def test_nm2_ausschluss_bleibt_auch_fuer_nicht_admin_voll(welt) -> None:
    """Ein Ausschluss kuerzt NICHT (N3) — auch nicht in den Kontenlisten."""
    sess = welt
    sess.add(HasRole(name="HR-ka", parent=LESER, parenttype="User",
                     parentfield="roles", role="Kalenderadministrator",
                     docstatus=0, idx=1))
    sess.commit()
    _ausschluss()
    sess.expire_all()
    # Der Ausschluss deaktiviert das Konto ebenfalls (siehe oben, N12b).
    sess.get(User, ZIEL_KONTO).enabled = True
    sess.commit()
    assert _konto_liste(LESER)[ZIEL_KONTO] == "Elvira Dorn"


# ── NM3: Antragsteller im Moderations-Board ─────────────────────────────────


def test_nm3_antragsteller_ausgetretener_ist_gekuerzt(welt) -> None:
    """Der Board-Antragsteller laeuft ueber ``personen_anzeige``."""
    from diakronos_app.api.kronos import kanban_api

    sess = welt
    _austritt()
    sess.expire_all()

    set_user(LESER)
    assert kanban_api._anzeigename(ZIEL_KONTO) == "Elvira D."
    set_user(ADMIN)
    assert kanban_api._anzeigename(ZIEL_KONTO) == "Elvira Dorn"


# ── AUSTRITT-e: Restliste des dritten Reviews (R-AUSTRITT-3) ────────────────


def _personen_anzeige():
    """(name, kuerzel) der Zielperson aus der Planrahmen-Quelle."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    s = SessionLocal()
    try:
        quelle = DBDatenquelle(s)
        namen = {p.kennung: (p.name, p.kuerzel) for p in quelle._quelle.personen()}
        kandidaten = {p.kennung for p in quelle.personen()}
    finally:
        s.close()
    return namen.get(ZIEL), ZIEL in kandidaten


def test_nr2_planrahmen_kuerzt_nur_ausgetretene(welt) -> None:
    """NR2 (BLOCKER): Kuerzung und Zuteilbarkeit sind zwei Fragen.

    Die Planrahmen-Anzeige (alte Plaene, Regelmeldung, Kuerzel) kuerzte ueber
    die Marke ``ausgeschlossen`` — damit sah ein Leser eine AUSGESCHLOSSENE
    Person als „Elvira D.“/„E. D.“, obwohl die Fachentscheidung sie voll
    sichtbar laesst. Gekuerzt wird nur das Austrittsmerkmal; gefiltert bleibt
    die Marke (beide Faelle nicht zuteilbar).
    """
    sess = welt
    _austritt()
    sess.expire_all()

    # Ausgetretene: gekuerzt fuer den Leser, voll fuer den Admin — beide nicht
    # zuteilbar.
    for wer, erwartet in ((ADMIN, ("Elvira Dorn", "E. Dorn")),
                          (LESER, ("Elvira D.", "E. D."))):
        set_user(wer)
        (anzeige, kandidat) = _personen_anzeige()
        assert anzeige == erwartet, f"{wer}: Austritt kuerzt"
        assert kandidat is False, f"{wer}: Ausgetretene ist kein Kandidat"

    # Ausschluss (nach dem Reaktivieren): NICHT gekuerzt, weiter nicht zuteilbar.
    set_user(ADMIN)
    _reaktivieren()
    _ausschluss()
    sess.expire_all()

    for wer in (ADMIN, LESER):
        set_user(wer)
        (anzeige, kandidat) = _personen_anzeige()
        assert anzeige == ("Elvira Dorn", "E. Dorn"), f"{wer}: Ausschluss kuerzt nicht"
        assert kandidat is False, f"{wer}: Ausgeschlossene ist kein Kandidat"


def test_nr3_ausschluss_einer_ausgetretenen_wird_abgelehnt(welt) -> None:
    """NR3: Die Gegenrichtung zu NH1 — erst zuruecknehmen, dann ausschliessen.

    Ohne die Schranke blieb ``austritt_datum`` stehen, das Detail meldete
    „Austritt“, und „Reaktivieren“ hob still den Ausschluss auf. Der Zustand
    bleibt hier unveraendert.
    """
    from diakronos_app.frappe_compat.exceptions import ValidationError

    sess = welt
    _austritt()
    sess.expire_all()
    with pytest.raises(ValidationError) as fehler:
        _ausschluss()
    assert "ausgetreten" in str(fehler.value)
    assert "Reaktiviere" in str(fehler.value)

    sess.expire_all()
    zeile = sess.get(Mitglied, ZIEL)
    assert zeile.status == "Ausgetreten"
    assert zeile.austritt_datum is not None
    # Der Ausschluss hat NICHT geschrieben: `ausgeschlossen_seit` traegt beim
    # Austritt aus Kompatibilitaet das Austrittsdatum — ein Ausschluss haette
    # es auf HEUTE gesetzt. Der Status bleibt „Ausgetreten“ (nicht „Passiver
    # Gast“), also hat auch die Statusaenderung nicht gegriffen.
    assert zeile.ausgeschlossen_seit == zeile.austritt_datum


def test_nr5_reaktivieren_altbestand_ohne_marke(welt) -> None:
    """NR5: Altbestand „Ausgetreten“ ohne Marke laesst sich reaktivieren.

    Die Oberflaeche bietet es an (``art='austritt'``). „Reaktivieren“ stellt
    dort „Mitglied“ her — und laesst eine ECHTE Nichteingetretene weiterhin
    abblitzen.
    """
    from diakronos_app.api.austritt import mitglied_reaktivieren
    from diakronos_app.frappe_compat.exceptions import ValidationError

    sess = welt
    zeile = sess.get(Mitglied, ZIEL)
    zeile.status = "Ausgetreten"  # Altbestand: keine Marke, kein Datum
    sess.commit()

    set_user(ADMIN)
    mitglied_reaktivieren(ZIEL)

    sess.expire_all()
    zeile = sess.get(Mitglied, ZIEL)
    assert zeile.status == "Mitglied"
    assert not zeile.ausgeschlossen

    # Gegenprobe: wer nie ausgetreten war, bleibt abgelehnt.
    sess.get(Mitglied, ZIEL).status = "Mitglied"
    sess.commit()
    with pytest.raises(ValidationError):
        mitglied_reaktivieren(ZIEL)


def test_nr4_besetzungsmatrix_kein_n_plus_eins(welt) -> None:
    """NR4: Die Besetzungsmatrix bildet die Personensicht EINMAL je Aufruf.

    ``_mitglied_name`` fragt je Name die Rollen des Aufrufers mit ab (4
    Abfragen); 30 Namen waren damit 120 Abfragen. Ueber ``_MitgliedNamen`` wird
    je Kennung hoechstens EINE Zeile gelesen und die Sicht genau einmal
    gebildet.
    """
    from sqlalchemy import event

    from diakronos_app.api import planung
    from diakronos_app.db import SessionLocal, engine
    from diakronos_app.models.diakonos import Dienstplan, Mitglied, Rollenbesetzung

    sess = welt
    # 30 zusaetzliche Mitglieder, alle in der Matrix eines Plans.
    plan_name = "zz-nr4-plan"
    sess.add(Dienstplan(
        name=plan_name, plantitel="NR4", jahr=2026, status="Entwurf",
        ist_entwurf=0, start_datum=None, ende_datum=None, docstatus=0, idx=0,
    ))
    for i in range(30):
        kennung = f"zz-nr4-{i:02d}"
        sess.add(Mitglied(name=kennung, vorname="Nora", nachname=f"Nr{i:02d}",
                          email=f"zz-nr4-{i:02d}@x.org", status="Mitglied",
                          docstatus=0, idx=0))
        sess.add(Rollenbesetzung(
            name=f"zz-nr4-rb-{i:02d}", dienstplan=plan_name, rolle=f"Rolle {i:02d}",
            teilnehmer=kennung, besetzung_nr=1, status="Bestaetigt",
            docstatus=0, idx=0,
        ))
    sess.commit()

    zaehler: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _zaehle(conn, cursor, statement, parameters, context, executemany):
        zaehler.append(statement)

    set_user(ADMIN)
    try:
        ergebnis = planung.get_besetzungsmatrix(plan_name)
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)

    assert len(ergebnis["rollen"]) == 30
    assert all(z["besetzungen"][0]["teilnehmer_name"] for z in ergebnis["besetzungen"])
    # Vor dem Fix: 129 Abfragen (4 je Name). Nach dem Fix 42 = 12 feste
    # Abfragen des Endpunkts + 1 je Name. Die Schwelle 60 liegt klar unter den
    # 129 und deutlich ueber den 42 (Puffer fuer weitere feste Abfragen).
    assert len(zaehler) <= 60, f"{len(zaehler)} Abfragen fuer 30 Namen"
