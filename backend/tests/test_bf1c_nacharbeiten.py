"""BF1c — Nacharbeit nach dem unabhaengigen Code-Review von `sicherung/bf1b`.

Jeder Test hier ist einem Befund des vorausgehenden Reviews zugeordnet und
prueft die BEHEBUNG, nicht die Fehlerbeschreibung. Fehlte zu einem Befund bisher ein Negativ-/Randtest, steht
er hier (Befund W9).

Befunde in dieser Datei:
  W1  Untergruppe im Rechtepfad -> 403 statt 500
  W2  Rechte Hinzufuegen/Entfernen/Rolle aendern konsistent
  W5  Kalenderabfrage mit unterer Zeitgrenze (Performance)
  W7  Persoenliche Daten nur auf Anforderung und nur fuer Admins
  W8  Umlaut-/Gross-klein-unabhaengige Suche zentral (Query-Layer)
"""
from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.kronos import Element

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren laufen beim Import

# Gemeinsame echte DB-Welt (Gruppen/Untergruppen/Verantwortliche).
from test_p4a_gruppen import hierarchie  # noqa: E402,F401
# Kalenderwelt (Kalender, Rollen) fuer die Kalender-Tests (W5).
from test_p4b_kronos_kern import kalenderwelt  # noqa: E402,F401

PFAD = "/api/method/diakronos.diakonos.api.gruppen."


def _aufruf(client, name, **daten):
    return client.post(PFAD + name, json=daten)


# ── W1: Untergruppe im Rechtepfad (500 -> 403) ─────────────────────────────


def test_w1_untergruppe_fremder_bekommt_403_statt_500(client, hierarchie):
    """W1: `Untergruppe` hat keine Spalte `dienstbereich`. Der Rechtepfad lief
    deshalb fuer einen Fremden in einen KeyError -> HTTP 500. Ein Fremder muss
    eine saubere Verweigerung (403) sehen, keinen Absturz."""
    set_user("mitglied-a@example.org")
    r = _aufruf(client, "get_gruppe_mitglieder_auswahl",
                gruppe_id="UG-A1", is_untergruppe=True)
    assert r.status_code == 403, f"Erwartet 403, bekam {r.status_code}: {r.text}"


def test_w1_untergruppe_verantwortlicher_darf_sehen(client, hierarchie):
    """W1: Der Verantwortliche der Untergruppe kommt durch (200) — und der
    Rechtepfad laeuft nicht in einen KeyError, weil der Dienstbereich der
    Untergruppe ueber ihre Obergruppe aufgeloest wird."""
    from diakronos_app.models.diakonos import UntergruppeVerantwortlicher

    sess = hierarchie
    sess.add(UntergruppeVerantwortlicher(
        name="UGV-1", parent="UG-A1", parenttype="Untergruppe",
        parentfield="verantwortliche", user="gruppenverantw@example.org",
        docstatus=0, idx=1,
    ))
    sess.commit()

    set_user("gruppenverantw@example.org")
    r = _aufruf(client, "get_gruppe_mitglieder_auswahl",
                gruppe_id="UG-A1", is_untergruppe=True)
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["message"], list)


def test_w1_add_untergruppe_fremder_403(client, hierarchie):
    """W1: Auch `add_mitglied_to_gruppe` darf fuer einen Fremden nicht 500
    liefern, sondern 403."""
    set_user("mitglied-a@example.org")
    r = _aufruf(client, "add_mitglied_to_gruppe",
                gruppe_id="UG-A1", mitglied_id="M-eigen-a", is_untergruppe=True)
    assert r.status_code == 403, r.text


# ── W2: Rechte Hinzufuegen/Entfernen/Rolle konsistent ──────────────────────


def test_w2_gruppenleiter_darf_hinzufuegen_entfernen_rolle(client, hierarchie):
    """W2: Wer aufnehmen darf, darf auch entfernen und die Rolle aendern.
    Vorher durfte der Gruppenverantwortliche nur hinzufuegen (200), waehrend
    Entfernen und Rollenwechsel mit 403 endeten — obwohl die SPA ihm genau
    diese drei Bedienelemente zeigt."""
    set_user("gruppenverantw@example.org")
    add = _aufruf(client, "add_mitglied_to_gruppe",
                  gruppe_id="G-A1", mitglied_id="M-neu-d", rolle="Mitglied")
    assert add.status_code == 200, add.text
    assert add.json()["message"]["success"] is True

    rolle = _aufruf(client, "update_mitglied_rolle",
                    gruppe_id="G-A1", mitglied_id="M-neu-d", rolle="Stellvertreter")
    assert rolle.status_code == 200, rolle.text
    assert rolle.json()["message"]["success"] is True

    weg = _aufruf(client, "remove_mitglied_from_gruppe",
                  gruppe_id="G-A1", mitglied_id="M-neu-d")
    assert weg.status_code == 200, weg.text
    assert weg.json()["message"]["success"] is True


def test_w2_fremder_darf_weder_hinzufuegen_noch_entfernen_noch_rolle(client, hierarchie):
    """W2 (Negativtest): Ein Fremder darf KEINE der drei Schreiboperationen —
    fail closed, auch wenn er eine gueltige Gruppe nennt."""
    set_user("mitglied-a@example.org")
    for name, extra in (
        ("add_mitglied_to_gruppe", {"mitglied_id": "M-eigen-a"}),
        ("remove_mitglied_from_gruppe", {"mitglied_id": "M-gruppe-b1"}),
        ("update_mitglied_rolle", {"mitglied_id": "M-gruppe-b1", "rolle": "Leiter"}),
    ):
        r = _aufruf(client, name, gruppe_id="G-B1", **extra)
        assert r.status_code == 403, f"{name}: erwartet 403, bekam {r.status_code}: {r.text}"


# ── W5: Kalenderabfrage mit unterer Zeitgrenze ─────────────────────────────


@pytest.fixture()
def fensterwelt(kalenderwelt):
    """Termine vor, in und nach dem Fenster (Okt 2026)."""
    sess = kalenderwelt
    sess.add_all([
        # Weit VOR dem Fenster: darf die (jetzt begrenzte) Abfrage nicht
        # belasten und nicht im Ergebnis stehen.
        Element(name="EL-ALT", element_name="Alt", element_calendar="KAL-PUB",
                element_start=datetime(2001, 1, 1, 10, 0),
                element_end=datetime(2001, 1, 1, 11, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=0),
        # Endet VOR dem Fensterbeginn -> Punktkontakt nein, also nicht im Fenster.
        Element(name="EL-VOR", element_name="Vor", element_calendar="KAL-PUB",
                element_start=datetime(2026, 9, 20, 10, 0),
                element_end=datetime(2026, 9, 20, 11, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=1),
        # Ueberlappt den Fensteranfang von links (mehrtägig) -> muss erscheinen.
        Element(name="EL-UEBER", element_name="Ueberlapp", element_calendar="KAL-PUB",
                element_start=datetime(2026, 9, 28, 10, 0),
                element_end=datetime(2026, 10, 2, 11, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=2),
        # Genau im Fenster.
        Element(name="EL-DRIN", element_name="Drin", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 10, 10, 0),
                element_end=datetime(2026, 10, 10, 11, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=3),
    ])
    sess.commit()
    return sess


KAL_PFAD = "/api/method/diakronos.kronos.api.calendar_get."


def test_w5_fenster_grenzen_bleiben_korrekt(client, kalenderwelt, fensterwelt):
    """W5: Die neue untere Zeitgrenze in SQL darf das Ergebnis NICHT
    veraendern: nur Termine, die das Fenster wirklich beruehren."""
    set_user("admin-kal@example.org")
    r = client.post(KAL_PFAD + "get_calendar_events",
                    json={"start_date": "2026-10-01", "end_date": "2026-10-31",
                          "calendar_filter": '["KAL-PUB"]'})
    assert r.status_code == 200, r.text
    ids = {e["id"] for e in r.json()["message"]}
    assert "EL-DRIN" in ids
    assert "EL-UEBER" in ids, "Mehrtägiger Termin am Fensteranfang fehlt."
    assert "EL-ALT" not in ids, "Termin weit vor dem Fenster gehoert nicht ins Ergebnis."
    assert "EL-VOR" not in ids, "Termin vor dem Fenster gehoert nicht ins Ergebnis."


def test_w5_sql_filter_holt_nichts_vor_dem_fenster(client, kalenderwelt, fensterwelt, monkeypatch):
    """W5 (Performance-Beleg): Die Abfrage muss die untere Zeitgrenze in SQL
    tragen — nicht erst in Python filtern. Geprueft wird, dass der
    Kalender-Endpunkt die alten Termine gar nicht erst geladen bekommt."""
    set_user("admin-kal@example.org")
    from diakronos_app.api.kronos import calendar_get as cg

    gelesene_ids: list[str] = []
    echtes_get_all = cg.get_all

    def beobachtend(doctype, **kwargs):
        zeilen = echtes_get_all(doctype, **kwargs)
        if doctype == "Element":
            gelesene_ids.extend(str(z.get("name")) for z in (zeilen or []))
        return zeilen

    monkeypatch.setattr(cg, "get_all", beobachtend)
    r = client.post(KAL_PFAD + "get_calendar_events",
                    json={"start_date": "2026-10-01", "end_date": "2026-10-31",
                          "calendar_filter": '["KAL-PUB"]'})
    assert r.status_code == 200, r.text
    assert "EL-ALT" not in gelesene_ids, (
        "Kalenderabfrage laedt Termine vor der unteren Zeitgrenze — die "
        "SQL-Grenze (W5) fehlt."
    )
    assert "EL-VOR" not in gelesene_ids, "Termin vor dem Fenster wurde geladen."


# ── W7: Persoenliche Daten serverseitig ────────────────────────────────────


@pytest.fixture()
def personenwelt(patched_db):
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add(User(name="w7-admin@example.org", email="w7-admin@example.org",
                  full_name="W7 Admin", enabled=True))
    sess.add(HasRole(name="HR-w7", parent="w7-admin@example.org",
                     parenttype="User", parentfield="roles", role="System Manager",
                     docstatus=0, idx=0))
    from datetime import date as _date

    sess.add(Mitglied(name="M-W7", vorname="Wiebke", nachname="W7",
                      email="wiebke@example.org", status="Mitglied",
                      telefonnummer="07000 1", postleitzahl="70173",
                      wohnort="Stuttgart", geburtstag=_date(1980, 1, 1),
                      ancestor_path="/M-W7", docstatus=0, idx=0))
    sess.commit()
    return sess


def test_w7_liste_ohne_persoenliche_daten_liefert_keine(client, personenwelt):
    """W7: Ohne `persoenliche_daten=1` sind Telefon/Adresse/Geburtstag/E-Mail
    `None` — auch nicht fuer einen Admin. Die Schluessel bleiben (B2-Vertrag:
    SPA-Struktur), es steht aber KEIN persoenlicher Wert im Koerper."""
    set_user("w7-admin@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste",
                   params={"limit": 10})
    assert r.status_code == 200, r.text
    zeilen = r.json()["message"]["data"]
    assert zeilen, "Liste ist leer."
    for zeile in zeilen:
        for feld in ("telefonnummer", "geburtstag", "postleitzahl", "wohnort",
                     "straße", "email"):
            assert zeile.get(feld) is None, \
                f"{feld!r} steht ohne Anforderung mit Wert in der Liste."


def test_w7_liste_mit_persoenliche_daten_fuer_admin_liefert_sie(client, personenwelt):
    """W7: Mit `persoenliche_daten=1` UND Admin-Rolle kommen die Felder."""
    set_user("w7-admin@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste",
                   params={"limit": 10, "persoenliche_daten": 1})
    assert r.status_code == 200, r.text
    zeile = next(z for z in r.json()["message"]["data"] if z["name"] == "M-W7")
    assert zeile["email"] == "wiebke@example.org"
    assert zeile["telefonnummer"] == "07000 1"


def test_w7_nicht_admin_bekommt_keine_persoenlichen_daten(client, personenwelt):
    """W7 (fail closed): `persoenliche_daten=1` ist nur fuer Admins wirksam.
    Ein normales Mitglied bekommt die Felder nicht — auch nicht mit dem Flag."""
    from diakronos_app.models.core import HasRole, User

    sess = personenwelt
    sess.add(User(name="w7-user@example.org", email="w7-user@example.org",
                  full_name="W7 User", enabled=True))
    sess.add(HasRole(name="HR-w7u", parent="w7-user@example.org",
                     parenttype="User", parentfield="roles", role="Mitglied",
                     docstatus=0, idx=0))
    sess.commit()

    set_user("w7-user@example.org")
    r = client.get("/api/method/mitglieder.get_mitglieder_liste",
                   params={"limit": 10, "persoenliche_daten": 1})
    assert r.status_code == 200, r.text
    for zeile in r.json()["message"]["data"]:
        assert zeile.get("telefonnummer") is None
        assert zeile.get("geburtstag") is None


# ── W8: Umlaut-/Gross-klein-unabhaengige Suche im Query-Layer ──────────────


@pytest.fixture()
def liedwelt(patched_db):
    from diakronos_app.models.psalmos import Lied  # noqa: F401

    sess = patched_db()
    sess.add_all([
        Lied(name="L-1", titel="Mächtig ist der Herr", rechte_status="Frei"),
        Lied(name="L-2", titel="Sonnenaufgang", rechte_status="Frei"),
    ])
    sess.commit()
    return sess


@pytest.mark.parametrize("begriff", ["mächtig", "MÄCHTIG", "maechtig", "MAECHTIG"])
def test_w8_query_layer_like_ist_umlaut_und_case_tolerant(liedwelt, begriff):
    """W8: Der zentrale `like` im Query-Layer beachtet Gross-/Kleinschreibung
    UND Umlautschreibweise. Damit findet die Lieder-Suche (die genau diesen
    Layer benutzt) „maechtig“ genauso wie „Mächtig“."""
    from diakronos_app.frappe_compat.query import get_all

    treffer = get_all("Lied", filters=[["titel", "like", f"%{begriff}%"]],
                      fields=["name"]) or []
    assert {t["name"] for t in treffer} == {"L-1"}, f"Treffer fuer {begriff!r}: {treffer}"


def test_w8_query_layer_negativtreffer(liedwelt):
    """W8 (Negativtest): ein nicht vorkommender Begriff liefert nichts."""
    from diakronos_app.frappe_compat.query import get_all

    assert get_all("Lied", filters=[["titel", "like", "%gibtsnicht%"]],
                   fields=["name"]) == []
