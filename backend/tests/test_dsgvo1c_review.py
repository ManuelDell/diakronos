"""DSGVO-1c: Restbefunde des zweiten Reviews (R-DSGVO-1b, N-1 … N-6).

DER GRUND, WARUM DIESE DATEI ANDERS AUSSIEHT
--------------------------------------------
Der Reviewer hat die Löschung an einer Kopie der Betriebs-DB nachgestellt und
dabei gefunden, dass FREMDE Daten zerstört werden, sobald die gelöschte Person
eine Veranstaltungsanmeldung (Vorname/Nachname einzeln) oder ein einteiliges
Konto hat (N-1). Dieses Verhalten konnte der Branch nicht sehen, weil die
Kollateral-Prüfung ganze Tabellen ausgenommen hat (N-4).

Die Tests hier übernehmen die Reviewer-Probe
(`R-DSGVO-1b-probe/test_zz_review_probe2.py`) mit SICHERER Erwartung und
prüfen zusätzlich die Restbefunde N-2, N-3, N-5, N-6 und die Merge-Folgen des
Austritts. Jeder Test nennt den Befund, den er festnagelt.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from test_ma1_mailversand import _smtp_einrichten
from sqlalchemy import String, Text, select, update

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import FileModel, HasRole, NotificationLog, User
from diakronos_app.models.diakonos import (
    Anmeldung,
    Beitrag,
    DSGVOEinwilligung,
    Mitglied,
    RessourcenBuchung,
    SichererAnhang,
)
from diakronos_app.models.devmodus import DevBefund
from diakronos_app.models.planrahmen import Abwesenheit

PFAD = "/api/method/diakronos.diakonos.api.datenschutz."
ADMIN = "admin@example.org"

ELVIRA = {
    "name": "Elvira Dorn",
    "vorname": "Elvira",
    "nachname": "Dorn",
    "email": "elvira.dorn@example.org",
    "telefon": "0711 55501-22",
}
#: Namensvetter mit demselben NACHnamen, anderes Konto, andere Person.
HENDRIK = {
    "name": "Hendrik Dorn",
    "vorname": "Hendrik",
    "nachname": "Dorn",
    "email": "hendrik.dorn@example.org",
}
#: Ein Name mit Umlaut (Suche nach „weiss“ muss „Weiß“ finden).
UMLAUT = "Jörg Weiß"
#: Namensvetter mit demselben VOLLnamen (N-6).
DOPPEL = "Hendrik Dorn"


def post(client, fn, **kw):
    return client.post(PFAD + fn, json=kw)


@pytest.fixture()
def smtp(monkeypatch, tmp_path, patched_db):
    from diakronos_app import files, mailversand
    from diakronos_app.settings import get_settings

    class Fake:
        def __init__(self):
            self.nachrichten = []

        def ehlo(self):
            pass

        def has_extn(self, name):
            return True

        def starttls(self):
            pass

        def login(self, *_a):
            pass

        def send_message(self, nachricht):
            self.nachrichten.append(nachricht)

        def quit(self):
            pass

    # MAIL-1: die SMTP-Werte stehen in der DB (Tabelle `smtp_einstellungen`),
    # nicht mehr in der Umgebung — siehe `_smtp_einrichten`.
    _smtp_einrichten(patched_db)
    s = get_settings()
    for feld, wert in (
        ("files_dir", str(tmp_path)),
    ):
        monkeypatch.setattr(s, feld, wert, raising=False)
    monkeypatch.setattr(files.settings, "files_dir", str(tmp_path), raising=False)
    fake = Fake()
    fake.dir = tmp_path
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    return fake


@pytest.fixture()
def welt(patched_db, smtp):
    """Elvira Dorn (Klarname als Kennung, MIT Anmeldung) und Namensvetter.

    Dazu genau die fremden Texte, an denen die Probe N-1 gezeigt hat:
    „Hendrik Dorn“ (Nachname gemeinsam), ein einwortiger Konto-Name und ein
    fremdes Konto mit EXAKT dem Vollnamen (N-6).
    """
    with patched_db.begin() as s:
        s.add(User(name=ADMIN, email=ADMIN, full_name="Verwaltung", enabled=True))
        s.add(HasRole(name="role-admin", parent=ADMIN, parenttype="User",
                      role="System Manager"))
        for person in (ELVIRA, HENDRIK):
            s.add(User(name=person["email"], email=person["email"],
                       full_name=f"{person['vorname']} {person['nachname']}",
                       password_hash="hash", enabled=True))
            s.add(HasRole(name=f"role-{person['nachname'].lower()}-{person['vorname'].lower()}",
                          parent=person["email"], parenttype="User", role="Mitglied"))
        # N-6: ein DRITTES Konto, das zufällig genau wie die Person heißt.
        s.add(User(name="namensvetter@example.org", email="namensvetter@example.org",
                   full_name=DOPPEL, enabled=True))
        # Ein Konto mit EINEM Wort als Anzeigename (N-1: nie als Nadel suchen).
        s.add(User(name="orgel@example.org", email="orgel@example.org",
                   full_name="Orgel", enabled=True))
        s.flush()
        s.add(Mitglied(
            name=ELVIRA["name"], vorname=ELVIRA["vorname"],
            nachname=ELVIRA["nachname"], email=ELVIRA["email"],
            telefonnummer=ELVIRA["telefon"], wohnort="Beispieldorf",
            status="Mitglied", user=ELVIRA["email"],
            datenschutz_einwilligung=True, mitglied_seit=date(2020, 1, 1),
        ))
        s.add(Mitglied(
            name=HENDRIK["name"], vorname=HENDRIK["vorname"],
            nachname=HENDRIK["nachname"], email=HENDRIK["email"],
            wohnort="Beispieldorf", status="Mitglied", user=HENDRIK["email"],
            notiz="Hendrik Dorn leitet, Elvira hilft beim Aufbau.",
        ))
        s.add(Mitglied(
            name="Tim Waldmann", vorname="Timo", nachname="Keller",
            status="Mitglied",
            notiz="Hendrik Dorn leitet, Elvira hilft. Dorn ist ein häufiger Name.",
        ))
        s.flush()
        # N-1: die Anmeldung liefert vorname/nachname EINZELN.
        s.add(Anmeldung(
            name="ANM-1", mitglied=ELVIRA["name"], vorname=ELVIRA["vorname"],
            nachname=ELVIRA["nachname"], email=ELVIRA["email"],
            status="Angemeldet", dsgvo_zustimmung=True,
            kommentar="Elvira Dorn kommt mit dem Auto.",
        ))
    set_user(ADMIN)
    return patched_db


def _antrag_und_loeschen(client, welt, mitglied=ELVIRA["name"]):
    set_user(ELVIRA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user(ADMIN)
    return post(client, "loeschung_bestaetigen", mitglied_id=mitglied, bestaetigt=True)


def _snapshot(engine) -> dict:
    """Jede Zeile jeder Metadaten-Tabelle als (tabelle, pk) -> dict."""
    from diakronos_app.models.base import Base

    ergebnis = {}
    with engine.connect() as c:
        for tabelle in Base.metadata.sorted_tables:
            spalten = list(tabelle.c)
            pk = [x.name for x in tabelle.primary_key.columns]
            for zeile in c.execute(select(*spalten)).all():
                d = {sp.name: wert for sp, wert in zip(spalten, zeile)}
                schluessel = d.get(pk[0]) if len(pk) == 1 else tuple(d.get(p) for p in pk)
                ergebnis[(tabelle.name, str(schluessel))] = d
    return ergebnis


def _durchsuchen(welt, nadeln) -> list[tuple[str, str, str]]:
    from diakronos_app.models.base import Base

    treffer = []
    with welt() as s:
        for mapper in Base.registry.mappers:
            tabelle = mapper.local_table
            for spalte in tabelle.c:
                if not isinstance(spalte.type, (String, Text)):
                    continue
                for wert in s.scalars(select(spalte)).all():
                    text = str(wert or "").lower()
                    for nadel in nadeln:
                        if str(nadel).lower() in text:
                            treffer.append((tabelle.name, spalte.name, str(wert)[:80]))
                            break
    return treffer


# ── N-1: nur VOLLE Namen werden in fremden Texten gesucht ──────────────────


def test_n1_einzelner_nachname_zerstoert_keine_fremden_daten(client, welt, smtp):
    """N-1 KRITISCH: „Dorn“ allein ist keine Nadel — Hendrik Dorn bleibt Hendrik Dorn.

    Die Probe des Reviewers hat genau hier zugeschlagen: die Anmeldung lieferte
    „Elvira“ und „Dorn“ einzeln, und `fremd_nadeln` ersetzte danach JEDES
    „Dorn“ in fremden Texten — inklusive `user.full_name` von Hendrik.
    """
    vorher = _snapshot(welt.kw["bind"])
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    nachher = _snapshot(welt.kw["bind"])
    with welt() as s:
        assert s.get(User, HENDRIK["email"]).full_name == "Hendrik Dorn"
        assert s.get(Mitglied, HENDRIK["name"]).nachname == "Dorn"
        assert s.get(Mitglied, HENDRIK["name"]).notiz == \
            "Hendrik Dorn leitet, Elvira hilft beim Aufbau."
        assert s.get(Mitglied, "Tim Waldmann").notiz == \
            "Hendrik Dorn leitet, Elvira hilft. Dorn ist ein häufiger Name."
    # Und die eigene Anmeldung ist trotzdem geleert (die Person selbst).
    with welt() as s:
        anm = s.get(Anmeldung, "ANM-1")
        assert anm.vorname is None and anm.nachname is None
        assert anm.email is None and anm.kommentar is None
    # Kein fremder Zeilen-Diff außer den Feldern, die die Person nennen.
    erlaubt_spalten = {("mitglied", "Hendrik Dorn", "notiz"),
                       ("mitglied", "Tim Waldmann", "notiz"),
                       ("anmeldung", "ANM-1", None)}
    fremde = []
    for schluessel, zeile in nachher.items():
        alt = vorher.get(schluessel)
        if alt is None or alt == zeile:
            continue
        tabelle, pk = schluessel
        geaenderte = {k for k in zeile if alt.get(k) != zeile.get(k)}
        if not any((tabelle, pk, sp) in erlaubt_spalten or (tabelle, pk, None) in erlaubt_spalten
                   for sp in geaenderte):
            fremde.append((tabelle, pk, {k: [alt.get(k), zeile.get(k)] for k in geaenderte}))
    assert fremde == [], f"Fremde Zeilen verändert: {fremde[:5]}"


def test_n1_voller_name_wird_weiter_ersetzt(client, welt, smtp):
    """Die Gegenprobe: der VOLLE Name der Person verschwindet aus fremden Texten."""
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        # Nur die VOLLE Nennung („Elvira Dorn“) wird ersetzt; der einzelne
        # Vorname bleibt stehen (N-1: keine Einzelteile als Nadel).
        assert s.get(Mitglied, HENDRIK["name"]).notiz == \
            "Hendrik Dorn leitet, Elvira hilft beim Aufbau."
        # Einzelner Vorname bleibt stehen (N-1: keine Einzelteile als Nadel) —
        # der VOLLE Name in Timos Notiz ist nicht vorhanden, dort bleibt alles.
        assert s.get(Mitglied, "Tim Waldmann").notiz == \
            "Hendrik Dorn leitet, Elvira hilft. Dorn ist ein häufiger Name."


def test_n1_einwortiger_kontoname_ist_keine_nadel(client, welt, smtp):
    """N-1: ein Konto mit EINEM Wort als Anzeigename darf nichts ersetzen.

    In der Probe war es „Hendrik Dorn“, das über `user.full_name` zur Nadel
    wurde. Hier hängt ein FREMDES Mitglied am einwortigen Konto.
    """
    with welt.begin() as s:
        s.add(Mitglied(name="Orgel Freund", vorname="Orgel", nachname="Freund",
                       email="orgel@example.org", status="Mitglied",
                       user="orgel@example.org",
                       notiz="Orgel spielt am Sonntag."))
        # Die Person selbst hat zusätzlich ein einwortiges Konto.
        # ACHTUNG: eigenes Konto (andere Kennung), nicht das der Person --
        # `user.name` ist eindeutig, zweimal dieselbe Kennung ist ein
        # IntegrityError und wuerde den Test verfaelschen.
        s.add(User(name="elvira@example.org", email="elvira@example.org",
                   full_name="Elvira", password_hash="hash", enabled=True))
        s.execute(update(Mitglied).where(Mitglied.name == ELVIRA["name"])
                  .values(user="elvira@example.org"))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(Mitglied, "Orgel Freund").vorname == "Orgel"
        assert s.get(Mitglied, "Orgel Freund").notiz == "Orgel spielt am Sonntag."


# ── N-6: fremdes `user.full_name` ist keine Fremdtextspalte ────────────────


def test_n6_namensvetter_behaelt_seinen_vollen_namen(client, welt, smtp):
    """N-6: ein ANDERES Konto mit exakt demselben Vollnamen bleibt unverändert."""
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(User, "namensvetter@example.org").full_name == DOPPEL


# ── N-2: Spalten ohne FK ───────────────────────────────────────────────────


def test_n2_ressourcenbuchung_und_autorenspalten_ohne_fk(client, welt, smtp):
    """N-2: Kennung/Name in Spalten OHNE FK verschwinden (nicht nur Rechte)."""
    from diakronos_app.models.diakonos import BeitragKommentar, WikiArtikel

    with welt.begin() as s:
        s.add(RessourcenBuchung(name="buchung-1", gebucht_von=ELVIRA["email"],
                                gebucht_von_name=ELVIRA["name"], status="Angefragt",
                                notizen="Geburtstag am Samstag"))
        s.add(Beitrag(name="beitrag-1", titel="Gruss", autor=ELVIRA["name"],
                      autor_email=ELVIRA["email"], inhalt="Tel. 0711 55501-22",
                      veroeffentlicht=False))
        s.add(BeitragKommentar(name="kommentar-1", parent="beitrag-1", autor=ELVIRA["name"],
                               autor_email=ELVIRA["email"], text="Danke!"))
        s.add(WikiArtikel(name="wiki-1", titel="Orgel", autor=ELVIRA["name"],
                          autor_email=ELVIRA["email"], inhalt="Register"))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        b = s.get(RessourcenBuchung, "buchung-1")
        assert b.gebucht_von is None
        assert b.gebucht_von_name == "Gelöschte Person"
        assert b.notizen == "Geburtstag am Samstag"  # Inhalt des Fachvorgangs bleibt
        for zeile in (s.get(Beitrag, "beitrag-1"), s.get(BeitragKommentar, "kommentar-1"),
                      s.get(WikiArtikel, "wiki-1")):
            assert zeile.autor == "Gelöschte Person", type(zeile).__name__
            assert zeile.autor_email is None, type(zeile).__name__
        assert s.get(Beitrag, "beitrag-1").inhalt == "Tel. [gelöscht]"
        assert s.get(WikiArtikel, "wiki-1").inhalt == "Register"
    treffer = _durchsuchen(welt, [ELVIRA["name"], ELVIRA["email"], "elvira.dorn",
                                  ELVIRA["telefon"], "07115550122"])
    assert treffer == [], treffer


def test_n2_planrahmen_konto_ohne_fk_und_konto_mail_im_json(client, welt, smtp):
    """N-2: `pr_verlauf.benutzer` / `pr_plantyp_version.erstellt_von` sind nicht nullbar
    über die FK-Schleife — und die Konto-Mail steht in den JSON-Spalten."""
    from diakronos_app.models.planrahmen import PlantypVersion, Verlauf

    with welt.begin() as s:
        s.add(Verlauf(id="verlauf-1", aktion="merkmal", benutzer=ELVIRA["email"],
                      nachher=[{"ziel": "person", "konto": ELVIRA["email"]}]))
        from diakronos_app.models.planrahmen import Plantyp

        s.add(Plantyp(id="pt-1", schluessel="chor", name="Chor"))
        s.add(PlantypVersion(id="version-1", plantyp="pt-1", versionsnummer=1,
                             gueltig_ab=date(2026, 1, 1), definition={},
                             erstellt_von=ELVIRA["email"]))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        v = s.get(Verlauf, "verlauf-1")
        assert v.benutzer is None
        assert json.dumps(v.nachher) .count(ELVIRA["email"]) == 0, v.nachher
        assert s.get(PlantypVersion, "version-1").erstellt_von is None


def test_n2_audit_zielname_bei_kontoeingriff(client, welt, smtp):
    """N-2: `audit_log.target_name` trägt bei Konto-Eingriffen die Mail."""
    from diakronos_app.models.diakonos import AuditLog

    with welt.begin() as s:
        s.add(AuditLog(name="a-konto", actor=ADMIN, target_doctype="User",
                       target_name=ELVIRA["email"], target_user=ELVIRA["email"],
                       action_typ="Konto gesperrt", old_value="aktiv",
                       new_value="gesperrt"))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        zeile = s.get(AuditLog, "a-konto")
        assert zeile.target_name != ELVIRA["email"]
        assert ELVIRA["email"] not in str(zeile.target_name)
    treffer = _durchsuchen(welt, [ELVIRA["email"]])
    assert treffer == [], treffer


# ── N-3: Zeilen ohne `parent`/Konto-Spalte wirklich löschen ────────────────


def test_n3_abwesenheit_und_sicherer_anhang_verschwinden(client, welt, smtp):
    """N-3: `pr_abwesenheit` (Gesundheitsfreitext) und `sicherer_anhang` fallen weg."""
    with welt.begin() as s:
        s.add(Abwesenheit(id="abw-1", mitglied=ELVIRA["name"], von=date(2026, 1, 1),
                          bis=date(2026, 1, 5), grund="Reha nach Bandscheiben-OP"))
        s.add(SichererAnhang(name="anhang-1", mitglied=ELVIRA["name"],
                             datei="/private/files/attest-n3.pdf",
                             dateiname="Attest_Dorn.pdf",
                             beschreibung="Attest Kur"))
    (smtp.dir / "attest-n3.pdf").write_bytes(b"x")
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(Abwesenheit, "abw-1") is None
        assert s.get(SichererAnhang, "anhang-1") is None
    assert "Bandscheiben" not in str(_snapshot(welt.kw["bind"]))
    assert not (smtp.dir / "attest-n3.pdf").exists()


def test_n3_file_zeile_der_person_verschwindet(client, welt, smtp):
    """N-3: der Dateiname steht in `file.file_name` — die Zeile muss weg."""
    with welt.begin() as s:
        s.add(FileModel(name="file-1", file_name="Ausweis Elvira Dorn.pdf",
                   file_url="/private/files/ausweis-n3.pdf", is_private=True,
                   attached_to_doctype="Mitglied", attached_to_name=ELVIRA["name"]))
    (smtp.dir / "ausweis-n3.pdf").write_bytes(b"x")
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(FileModel, "file-1") is None
    assert not (smtp.dir / "ausweis-n3.pdf").exists()


# ── N-4: Kollateral-Prüfung nimmt keine Tabellen mehr aus ──────────────────


def test_n4_kollateral_ohne_tabellenausnahme(client, welt, smtp):
    """N-4: KEINE Ausnahme ganzer Tabellen — nur exakt erwartete Ersetzungen."""
    from diakronos_app.models.diakonos import AuditLog

    with welt.begin() as s:
        s.add(AuditLog(name="a-fremd", actor=HENDRIK["email"], target_doctype="Dienstplan",
                       target_name="DP-X", action_typ="Aenderung",
                       ip_address="198.51.100.7", user_agent="Hendrik-Agent/1.0"))
        s.add(NotificationLog(name="n-fremd", for_user=ADMIN, subject="Diensttausch",
                              email_content="Elvira Dorn moechte mit dir tauschen.",
                              from_user=ELVIRA["email"]))
        s.add(NotificationLog(name="n-bleibt", for_user=ADMIN, subject="Orgel",
                              email_content="Die neue Orgel klingt gut.",
                              from_user=HENDRIK["email"]))
    vorher = _snapshot(welt.kw["bind"])
    assert _antrag_und_loeschen(client, welt).status_code == 200
    nachher = _snapshot(welt.kw["bind"])
    assert nachher[("audit_log", "a-fremd")] == vorher[("audit_log", "a-fremd")]
    assert nachher[("notification_log", "n-bleibt")] == vorher[("notification_log", "n-bleibt")]
    n = nachher[("notification_log", "n-fremd")]
    assert n["for_user"] == ADMIN and n["email_content"] == \
        "[gelöscht] moechte mit dir tauschen."


# ── N-5: Bestandsweg nur mit bestätigtem Antrag + Mail ─────────────────────


def test_n5_anonymisieren_ohne_antrag_wird_abgelehnt(client, welt, smtp):
    """N-5: der alte Weg darf NICHT ohne Antrag löschen (D4: Mail vor Löschung)."""
    set_user(ADMIN)
    r = post(client, "anonymisieren", mitglied_id=ELVIRA["name"],
             bestaetigt=True, bestaetigung="ANONYMISIEREN")
    assert r.status_code >= 400, r.text
    with welt() as s:
        assert s.get(Mitglied, ELVIRA["name"]) is not None
        assert s.get(Mitglied, ELVIRA["name"]).email == ELVIRA["email"]


def test_n5_anonymisieren_mit_offenem_antrag_verweist_auf_bestaetigen(client, welt, smtp):
    """N-5: offener Antrag → nur `loeschung_bestaetigen` (Mail + Löschung)."""
    set_user(ELVIRA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user(ADMIN)
    r = post(client, "anonymisieren", mitglied_id=ELVIRA["name"],
             bestaetigt=True, bestaetigung="ANONYMISIEREN", nur_antrag=True)
    # Mit offenem Antrag führt der Weg HART auf `loeschung_bestaetigen`: die
    # Mail geht raus, DANN wird gelöscht (D4) — genau ein Mal.
    assert r.status_code == 200, r.text
    assert len(smtp.nachrichten) == 1
    with welt() as s:
        assert s.get(Mitglied, ELVIRA["name"]) is None


def test_n5_mail_wartet_nicht_hinter_aller_konten_sperre(client, welt, smtp, monkeypatch):
    """N5: FOR UPDATE gilt nur den betroffenen Zeilen, nicht allen Konten."""
    from sqlalchemy.sql import Select

    gesehen: list[str] = []
    echt = Select.with_for_update

    def spion(self, *args, **kwargs):
        gesehen.append(str(self))
        return echt(self, *args, **kwargs)

    monkeypatch.setattr(Select, "with_for_update", spion)
    assert _antrag_und_loeschen(client, welt).status_code == 200
    gesperrt = gesehen
    assert gesperrt, "es muss überhaupt gesperrt werden"
    konten = [a for a in gesperrt if '"user"' in a]
    assert konten, gesperrt
    for anweisung in konten:
        assert "WHERE" in anweisung.upper(), anweisung


# ── Austritt: anonymisierte Zeile übernimmt NUR technische Felder ──────────


def test_austritt_freitext_landet_nicht_in_der_neutralen_zeile(client, welt, smtp):
    """Merge-Folge (B): `austritt_grund` und die Vor-Austritts-Spalten bleiben nicht."""
    with welt.begin() as s:
        m = s.get(Mitglied, ELVIRA["name"])
        m.austritt_grund = "Umzug nach Beispieldorf, kein Auto mehr"
        m.austritt_datum = date(2026, 9, 30)
        m.vor_austritt_status = "Mitglied"
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    kennung = r.json().get("message", r.json())["mitglied"]
    with welt() as s:
        neu = s.get(Mitglied, kennung)
        assert neu.austritt_grund is None
        assert neu.austritt_datum is None
        assert neu.vor_austritt_status is None
    treffer = _durchsuchen(welt, ["Umzug nach Beispieldorf"])
    assert treffer == [], treffer


# ── NACHWEIS: Vollscan 0 Treffer (R-DSGVO-1b, Restliste 7) ─────────────────
#
# Die Reviewer-Probe lief für drei Probanden (Personen A-C); ein VOLLSCAN der
# ganzen DB (inkl. JSON) nach den echten Personen fordert der Kartentext
# ausdrücklich. Zwei Stellen blieben dabei offen, weil ihre Spalte bisher
# ausser Sicht war: der SCHLÜSSEL der Einwilligungs-Nachweiszeile und
# JSON-Langtexte (die Ersetzung dort lief nur für GENAU gleiche Werte, N-2).


def test_n1_nachweiszeile_traegt_keinen_namen_im_schluessel(client, welt, smtp):
    """NACHWEIS: `dsgvo_einwilligung.name` ist im Betrieb „DSGVO-<Klarname>-0114“.

    Die Zeile bleibt der Einwilligungs-Nachweis (Art. 7) — ihr SCHLÜSSEL darf
    den Namen der Person nicht tragen: ein Namensvetter im Schlüssel, und der
    Vollscan nach dem Löschen meldet ihn als Rest.
    """
    with welt.begin() as s:
        s.add(DSGVOEinwilligung(name=f"DSGVO-{ELVIRA['name']}-0114",
                                mitglied=ELVIRA["name"], typ="foto", aktion="erteilt"))
        s.add(DSGVOEinwilligung(name=f"EINW-{ELVIRA['name']}-0292",
                                mitglied=ELVIRA["name"], typ="datenschutz",
                                aktion="erteilt"))
        # Gegenprobe: die Nachweiszeile EINER ANDEREN Person trägt deren
        # Namen und bleibt, was sie ist.
        s.add(DSGVOEinwilligung(name="DSGVO-Hendrik Dorn-0002",
                                mitglied=HENDRIK["name"], typ="foto", aktion="erteilt"))
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    kennung = r.json()["message"]["mitglied"]
    with welt() as s:
        eigene = s.scalars(
            select(DSGVOEinwilligung).where(DSGVOEinwilligung.mitglied == kennung)
        ).all()
        # Die beiden Nachweise bleiben (Art. 7); die dritte Zeile ist die
        # Widerrufs-Urkunde, die `loeschung_bestaetigen` selbst anlegt.
        nachweise = [z for z in eigene if z.name.startswith(("DSGVO-", "EINW-"))]
        assert len(nachweise) == 2, [z.name for z in eigene]
        for zeile in eigene:
            assert ELVIRA["name"].lower() not in zeile.name.lower(), zeile.name
        for zeile in nachweise:
            # ID-1f: der Namensanteil ist die NEUTRALE KENNUNG der Person —
            # dieselbe Form, die auch die Migration `id1_mitglied_kennungen`
            # schreibt („DSGVO-<Kennung>-0114“). Früher stand dort der
            # Platzhalter `[gelöscht]`; nach der Umstellung auf technische
            # Kennungen (ID-1) wäre das ein Fremdkörper im Schlüsselformat.
            # Die laufende Nummer bleibt, der Bezug ist die Kennung.
            assert zeile.name.split("-")[-1].isdigit(), zeile.name
            assert kennung in zeile.name, zeile.name
        fremd = s.get(DSGVOEinwilligung, "DSGVO-Hendrik Dorn-0002")
        assert fremd is not None and fremd.mitglied == HENDRIK["name"]
    treffer = _durchsuchen(welt, [ELVIRA["name"], ELVIRA["email"]])
    assert treffer == [], treffer


def test_n1_voller_name_in_json_langtext_wird_ersetzt(client, welt, smtp):
    """NACHWEIS: `dm_befund.element` ist ein JSON-Bildschirmtext der Verwaltung.

    Da steht die Anmeldungsliste als Fließtext („27.04.2026 Elvira Dorn …“).
    Die JSON-Ersetzung lief bisher nur für GENAU gleiche Werte (N-2), ein
    Langtext mit dem Namen als Teilstring blieb stehen — der Vollscan meldet
    ihn. Fremde Personen im selben Text bleiben unverändert (ganzes Wort).
    """
    text_eigene = ("DATUM NAME TYP STATUS "
                   f"27.04.2026 {ELVIRA['name']} Mitglied-Registrierung Bestätigt "
                   "20.04.2026 Hendrik Dorn Mitglied-Registrierung Bestätigt")
    with welt.begin() as s:
        s.add(DevBefund(name="dm-langtext", benutzer=ADMIN, art="wunsch",
                        element={"text": text_eigene},
                        fehlerumfeld=[{"feld": "name", "wert": ELVIRA["name"]}]))
        s.add(DevBefund(name="dm-langtext-fremd", benutzer=ADMIN, art="wunsch",
                        element={"text": "20.04.2026 Hendrik Dorn Mitglied-Registrierung"}))
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    with welt() as s:
        langtext = s.get(DevBefund, "dm-langtext")
        assert langtext is not None
        assert ELVIRA["name"] not in langtext.element["text"], langtext.element
        assert "[gelöscht]" in langtext.element["text"], langtext.element
        # Der GENAU gleiche Wert läuft weiter über die Kennung (N-2/K1).
        assert langtext.fehlerumfeld[0]["wert"].startswith("geloescht-"), langtext.fehlerumfeld
        fremd = s.get(DevBefund, "dm-langtext-fremd")
        assert "Hendrik Dorn" in fremd.element["text"], fremd.element
    treffer = _durchsuchen(welt, [ELVIRA["name"], ELVIRA["email"]])
    assert treffer == [], treffer
