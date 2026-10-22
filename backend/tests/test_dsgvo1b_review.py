"""DSGVO-1b: Regression der Review-Befunde K1–K3, H1–H3, M1–M3, N1–N5.

DER GRUND, WARUM DIESE DATEI ANDERS AUSSIEHT
--------------------------------------------
Die Tests aus DSGVO-1 liefen mit TECHNISCHEN Kennungen („D1-anna“). Im Betrieb
ist `mitglied.name` der KLARNAME („Hans Beispiel“) — genau darum blieb dort der
Name als Primärschlüssel stehen und alle Verweise darauf zeigten weiter auf ihn
(R-DSGVO-1, K1). Jeder Test hier benutzt deshalb eine Person mit Klarname als
Kennung, wie sie der Betrieb hat.

Die Probe des Reviewers (`R-DSGVO-1-probe/test_zz_review_probe.py`) ist hier
als `test_zz_review_probe_*` übernommen: dieselben Fälle, aber mit SICHERER
Erwartung (die Probe schrieb nur Messwerte in eine JSON-Datei, geprüft wurde
von Hand). Sie muss vollständig grün sein.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from test_ma1_mailversand import _smtp_einrichten
from sqlalchemy import String, Text, delete, select

from diakronos_app.db import SessionLocal

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, NotificationLog, User
from diakronos_app.models.diakonos import AuditLog, Mitglied

PFAD = "/api/method/diakronos.diakonos.api.datenschutz."
ADMIN = "admin@example.org"

HANS = {
    "name": "Hans Beispiel",          # Klarname als Kennung — wie im Betrieb
    "vorname": "Hans",
    "nachname": "Beispiel",
    "email": "hans.beispiel@example.org",
    "telefon": "0711 98765-43",
    "wohnort": "Stuttgart",
    "plz": "70174",
}


def post(client, fn, **kw):
    return client.post(PFAD + fn, json=kw)


@pytest.fixture()
def smtp(monkeypatch, tmp_path, patched_db):
    """Fake-SMTP an der Naht; `smtp.fehler` macht den Versand kaputt."""
    from diakronos_app import files, mailversand
    from diakronos_app.settings import get_settings

    class Fake:
        def __init__(self):
            self.nachrichten = []
            self.fehler = None

        def ehlo(self):
            pass

        def has_extn(self, name):
            return True

        def starttls(self):
            pass

        def login(self, *_a):
            pass

        def send_message(self, nachricht):
            if self.fehler is not None:
                raise self.fehler
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
    """Hans Beispiel (Klarname als Kennung) mit vollem Bezugswerk + Fremddaten."""
    with patched_db.begin() as s:
        for konto, rolle in (
            (ADMIN, "System Manager"),
            ("admin2@example.org", "System Manager"),
            ("verwaltung@example.org", "Mitgliederadministrator"),
        ):
            s.add(User(name=konto, email=konto, full_name="Verwaltung " + konto,
                       enabled=True))
            s.add(HasRole(name=f"role-{konto}", parent=konto, parenttype="User",
                          role=rolle))
        s.add(User(name=HANS["email"], email=HANS["email"],
                   full_name=f"{HANS['vorname']} {HANS['nachname']}",
                   password_hash="hash", enabled=True))
        s.add(HasRole(name="role-hans", parent=HANS["email"], parenttype="User",
                      role="Mitglied"))
        s.flush()
        s.add(Mitglied(
            name=HANS["name"], vorname=HANS["vorname"], nachname=HANS["nachname"],
            email=HANS["email"], telefonnummer=HANS["telefon"],
            geburtstag=date(1977, 7, 7), wohnort=HANS["wohnort"],
            straße="Müllerweg", nummer="3", postleitzahl=HANS["plz"],
            notiz="Hans mag Orgel", user=HANS["email"], status="Mitglied",
            datenschutz_einwilligung=True, foto_einwilligung=False,
            mitglied_seit=date(2020, 1, 1),
        ))
        # Fremde Personen — ihre Daten dürfen NICHT angefasst werden.
        s.add(Mitglied(name="Konrad Waldmann", vorname="Konrad", nachname="Waldmann",
                       email="konrad.waldmann@example.org", wohnort="Stuttgart",
                       postleitzahl="70176", status="Mitglied",
                       notiz="Bringt Johannes und Hans-Peter mit. Wohnt in Stuttgart-Mitte."))
        s.add(Mitglied(name="Eva Evangelisch", vorname="Eva",
                       nachname="Evangelisch", status="Mitglied"))
        s.add(Mitglied(name="Ben Utzer", vorname="Ben", nachname="Utzer",
                       status="Mitglied", notiz="Benutzername: ben; Evangelisch geprägt"))
        s.flush()
        # Protokoll: Handlung der Person an einem FREMDEN Objekt, mit IP.
        s.add(AuditLog(name="a-fremd", actor=HANS["email"], target_doctype="Dienstplan",
                       target_name="DP-X", action_typ="Aenderung",
                       ip_address="198.51.100.23", user_agent="Hans-Agent/1.0"))
        # Benachrichtigung an eine ANDERE Person, die den Namen nennt.
        s.add(NotificationLog(name="n-fremd", for_user=ADMIN, subject="Diensttausch",
                              email_content="Hans Beispiel moechte mit dir tauschen.",
                              from_user=HANS["email"]))
        # Eigene Benachrichtigung (an die Person).
        s.add(NotificationLog(name="n-eigen", for_user=HANS["email"],
                              from_user=ADMIN, subject="Hallo Hans Beispiel",
                              email_content="Hans Beispiel, dein Antrag ist da."))
    set_user(ADMIN)
    return patched_db


def _antrag_und_loeschen(client, welt, mitglied=HANS["name"]):
    set_user(HANS["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user(ADMIN)
    return post(client, "loeschung_bestaetigen", mitglied_id=mitglied, bestaetigt=True)


def _antwort(r) -> dict:
    """Der Frappe-Router verpackt den Rückgabewert in ``{"message": …}``."""
    daten = r.json()
    return daten.get("message", daten) if isinstance(daten, dict) else daten


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
    """Ganze DB (auch JSON-Spalten) nach Nadeln durchsuchen, Groß/klein egal."""
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
                            treffer.append((tabelle.name, spalte.name,
                                            str(wert)[:80]))
                            break
    return treffer


# ── K1: neutrale Kennung ────────────────────────────────────────────────────


def test_k1_klarname_ist_nach_der_loeschung_verschwunden(client, welt, smtp):
    """K1: `mitglied.name` war der Klarname — er bleibt es NICHT."""
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    kennung = _antwort(r)["mitglied"]
    assert re.fullmatch(r"geloescht-[0-9a-f]{32}", kennung), kennung
    with welt() as s:
        assert s.get(Mitglied, HANS["name"]) is None
        neu = s.get(Mitglied, kennung)
        assert neu is not None
        assert (neu.vorname, neu.nachname, neu.status) == ("Gelöschte", "Person", "geloescht")
    # Nur der VOLLE Name, die Mail und die Telefonnummer sind Bezug DIESER
    # Person. „Hans-Peter“ in einer fremden Notiz ist ein anderer Mensch und
    # bleibt stehen (Fachentscheidung K2: einzelne Vornamen werden nicht
    # angetastet) — der Scan darf ihn also nicht als Rest melden.
    treffer = _durchsuchen(welt, [HANS["name"], f"{HANS['nachname']}, {HANS['vorname']}",
                                  HANS["email"], HANS["telefon"]])
    assert treffer == [], f"Personendaten stehen noch in: {treffer}"


def test_k1_verweise_zeigen_auf_die_neue_kennung(client, welt, smtp):
    """K1: `loeschantrag.mitglied` und `audit_log.target_name` = neue Kennung."""
    from diakronos_app.models.datenschutz import Loeschantrag

    r = _antrag_und_loeschen(client, welt)
    kennung = _antwort(r)["mitglied"]
    with welt() as s:
        a = s.get(Loeschantrag, kennung)
        assert a is not None and a.status == "ausgefuehrt"
        assert s.get(Loeschantrag, HANS["name"]) is None
        protokolle = s.scalars(select(AuditLog).where(
            AuditLog.action_typ == "Loeschung auf Antrag")).all()
        assert [p.target_name for p in protokolle] == [kennung]


def test_k1_wert_spalten_und_json_umgehaengt(client, welt, smtp):
    """K1: Spalten OHNE FK und JSON-Werte, die genau die Kennung tragen."""
    import json

    from diakronos_app.models.planrahmen import Eintrag as PREintrag
    from diakronos_app.models.planrahmen import MerkmalWert as PRMerkmalWert
    from diakronos_app.models.planrahmen import Verlauf as PRVerlauf

    with welt.begin() as s:
        s.add(PREintrag(id="e-hans", termin="t-1", feld_pfad="lieder[0].solo",
                        wert=HANS["name"], fixiert=False, quelle="optimieren",
                        meldungen=[]))
        s.add(PREintrag(id="e-fremd", termin="t-2", feld_pfad="lieder[0].solo",
                        wert="Konrad Waldmann", fixiert=False, quelle="optimieren",
                        meldungen=[]))
        s.add(PRMerkmalWert(id="m-hans", merkmal="M-1", ziel_id=HANS["name"],
                            wert=True))
        s.add(PRVerlauf(id="v-hans", aktion="merkmal", benutzer=HANS["email"],
                        nachher=[{"ziel": "person", "ziel_id": HANS["name"],
                                  "anzeige": HANS["name"]}]))
    r = _antrag_und_loeschen(client, welt)
    kennung = _antwort(r)["mitglied"]
    with welt() as s:
        assert s.get(PREintrag, "e-hans").wert == kennung
        assert s.get(PREintrag, "e-fremd").wert == "Konrad Waldmann"  # fremd bleibt
        assert s.get(PRMerkmalWert, "m-hans").ziel_id == kennung
        verlauf = s.get(PRVerlauf, "v-hans")
        assert json.dumps(verlauf.nachher) == json.dumps(
            [{"ziel": "person", "ziel_id": kennung, "anzeige": kennung}]
        )


# ── K2: keine blinde Freitext-Ersetzung ─────────────────────────────────────


def test_k2_fremde_wohnorte_bleiben_stehen(client, welt, smtp):
    """K2: „Stuttgart“ bei ANDEREN Mitgliedern wurde zu `[gelöscht]`."""
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    with welt() as s:
        fremd = s.get(Mitglied, "Konrad Waldmann")
        assert fremd.wohnort == "Stuttgart" and fremd.postleitzahl == "70176"


def test_k2_fremde_notiz_bleibt_unveraendert(client, welt, smtp):
    """K2: fremder Text mit „Hans-Peter“, „Johannes“, „Stuttgart-Mitte“."""
    vorher = "Bringt Johannes und Hans-Peter mit. Wohnt in Stuttgart-Mitte."
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(Mitglied, "Konrad Waldmann").notiz == vorher


def test_k2_vorname_trifft_keine_fremden_woerter(client, welt, smtp):
    """K2: „Eva“ darf „Evangelisch“ nicht treffen, „Ben“ nicht „Benutzer“."""
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(Mitglied, "Ben Utzer").notiz == (
            "Benutzername: ben; Evangelisch geprägt")
        assert s.get(Mitglied, "Eva Evangelisch").nachname == "Evangelisch"


def test_k2_voller_name_in_fremdem_text_wird_ersetzt(client, welt, smtp):
    """K2: der VOLLE Name in einem fremden Text wird ersetzt — als ganzes Wort,
    in der Schreibweise des Textes (kein `lower()` über den ganzen Text)."""
    with welt.begin() as s:
        s.get(Mitglied, "Konrad Waldmann").notiz = (
            "Notiz: HANS BEISPIEL kommt später, sonst alles beim Alten")
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        notiz = s.get(Mitglied, "Konrad Waldmann").notiz
    assert "[gelöscht]" in notiz
    assert "kommt später, sonst alles beim Alten" in notiz
    # Originalschreibung des übrigen Textes: „Notiz:“ bleibt groß.
    assert notiz.startswith("Notiz:")


def test_k2_eigene_zeilen_werden_geleert(client, welt, smtp):
    """K2 (a): Zeilen der Person selbst werden genullt/gelöscht, nicht
    teilstring-ersetzt."""
    from diakronos_app.models.diakonos import Anmeldung

    with welt.begin() as s:
        s.add(Anmeldung(name="a-1", mitglied=HANS["name"],
                        vorname=HANS["vorname"], nachname=HANS["nachname"],
                        email=HANS["email"], telefon=HANS["telefon"],
                        email_freitext=f"kontakt: {HANS['email']}",
                        name_freitext=HANS["name"],
                        kommentar=f"{HANS['vorname']} fragt nach dem Bus",
                        status="angemeldet"))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        a = s.get(Anmeldung, "a-1")
        assert a is not None
        for feld in ("vorname", "nachname", "email", "telefon",
                     "email_freitext", "name_freitext", "kommentar"):
            assert getattr(a, feld) is None, feld


# ── K3: Reihenfolge ────────────────────────────────────────────────────────


def test_k3_fk_fehler_vor_dem_mailversand(client, welt, smtp, monkeypatch):
    """K3: ein FK-Fehler in der Anonymisierung darf KEINE Mail auslösen."""
    from diakronos_app import dsgvo_anonymisierung

    aufrufe = {"mail": 0}
    echt = dsgvo_anonymisierung._pruefe_konsistenz

    def platzen(s):
        raise RuntimeError("Erzwungener FK-Fehler beim Flush")

    set_user(HANS["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user(ADMIN)
    monkeypatch.setattr(dsgvo_anonymisierung, "_pruefe_konsistenz", platzen)
    try:
        with pytest.raises(Exception):
            post(client, "loeschung_bestaetigen", mitglied_id=HANS["name"],
                 bestaetigt=True)
    finally:
        monkeypatch.setattr(dsgvo_anonymisierung, "_pruefe_konsistenz", echt)
    aufrufe["mail"] = len(smtp.nachrichten)
    assert aufrufe["mail"] == 0, "Mail ging raus, obwohl die Löschung scheiterte"
    with welt() as s:
        assert s.get(Mitglied, HANS["name"]).vorname == HANS["vorname"]


def test_k3_mailfehler_rollt_zurueck_und_zweiter_versuch_gelingt(client, welt, smtp):
    """K3/N2: Mailfehler -> nichts gelöscht; zweiter Versuch gelingt (200)."""
    from diakronos_app.models.datenschutz import STATUS_OFFEN, Loeschantrag

    smtp.fehler = RuntimeError("550 mailbox unavailable")
    set_user(HANS["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user(ADMIN)
    r = post(client, "loeschung_bestaetigen", mitglied_id=HANS["name"],
             bestaetigt=True)
    assert r.status_code == 417, r.text
    with welt() as s:
        assert s.get(Mitglied, HANS["name"]).vorname == HANS["vorname"]
        assert s.get(User, HANS["email"]) is not None
        assert s.get(Loeschantrag, HANS["name"]).status == STATUS_OFFEN
    # Zweiter Versuch — diesmal mit funktionierendem Versand. MUSS 200 sein.
    smtp.fehler = None
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    assert len(smtp.nachrichten) == 1


# ── H2: Status „geloescht“ ist endgültig ───────────────────────────────────


def test_h2_geloeschte_person_ist_ueber_keinen_weg_aenderbar(client, welt, smtp, patched_db):
    """H2: update_mitglied, PUT /api/resource, frappe.client, Austritt."""
    r = _antrag_und_loeschen(client, welt)
    kennung = _antwort(r)["mitglied"]
    set_user(ADMIN)
    # (a) eigener Endpunkt
    r = client.post("/api/method/mitglieder.update_mitglied",
                    json={"mitglied_id": kennung,
                          "data": {"status": "Mitglied", "vorname": "Wieder"}})
    assert r.status_code in (403, 417), r.text
    # (b) generische Resource-API
    r = client.put(f"/api/resource/Mitglied/{kennung}", json={"status": "Mitglied"})
    assert r.status_code in (403, 417), r.text
    # (c) frappe.client.insert (Neuanlage unter der Kennung) und
    #     Document.db_set (der Frappe-Dokumentweg)
    #
    # ID-1d: Eine NEUE Person traegt nie eine vom Client gewaehlte Kennung —
    # auch nicht die einer geloeschten. Sie entsteht deshalb unter einer
    # FRISCHEN Server-Kennung; die geloeschte Zeile bleibt unberuehrt und
    # unveraendert (kein „Wieder“).
    from diakronos_app.models.diakonos import Mitglied as _Mitglied

    r = client.post("/api/method/frappe.client.insert",
                    json={"doc": {"doctype": "Mitglied", "name": kennung,
                                  "vorname": "Wieder", "status": "Mitglied"}})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["name"] != kennung
    _s = patched_db()
    try:
        geloescht = _s.get(_Mitglied, kennung)
        assert geloescht is not None
        assert geloescht.vorname != "Wieder"
        assert geloescht.status == "geloescht"
    finally:
        _s.close()
    from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
    from diakronos_app.frappe_compat.query import get_doc

    with pytest.raises(FrappePermissionError):
        get_doc("Mitglied", kennung).db_set("vorname", "Wieder")
    # (d) Status-Endpunkt und Ausschluss
    for pfad, nutzlast in (
        ("mitglieder.set_mitglied_status",
         {"mitglied_id": kennung, "status": "Mitglied"}),
        ("mitglieder.schliesse_mitglied_aus", {"mitglied_id": kennung}),
    ):
        r = client.post(f"/api/method/{pfad}", json=nutzlast)
        assert r.status_code in (403, 417), (pfad, r.text)
    with welt() as s:
        neu = s.get(Mitglied, kennung)
        assert (neu.vorname, neu.status, neu.ausgeschlossen) == (
            "Gelöschte", "geloescht", True)


def test_h2_import_aendert_kein_geloeschtes_mitglied(client, welt, smtp):
    """H2: der Importweg läuft durch dieselbe Schranke."""
    r = _antrag_und_loeschen(client, welt)
    kennung = _antwort(r)["mitglied"]
    set_user(ADMIN)
    from diakronos_app.frappe_compat.api_helpers import _pruefe_mitglied_schreibzugriff

    with pytest.raises(Exception):
        _pruefe_mitglied_schreibzugriff({"vorname": "Wieder"}, kennung)


# ── H3: Reste und Dateien ──────────────────────────────────────────────────


def test_h3_geraeteangaben_der_person_sind_weg(client, welt, smtp):
    """H3: `audit_log.ip_address/user_agent` eigener Handlungen an FREMDEN
    Objekten — die Reihenfolge (erst filtern, dann nullen) war falsch."""
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        eintrag = s.get(AuditLog, "a-fremd")
        assert eintrag is not None
        assert eintrag.ip_address is None and eintrag.user_agent is None
        assert eintrag.actor is None


def test_h3_bug_report_user_agent_und_screenshot(client, welt, smtp):
    """H3: `bug_report.user_agent` der Person + Bildschirmfoto physisch weg."""
    from diakronos_app.models.diakonos import BugReport

    (smtp.dir / "shot.png").write_bytes(b"x")
    with welt.begin() as s:
        s.add(BugReport(name="b-1", benutzer=HANS["email"], mitglied=HANS["name"],
                        beschreibung="Fehler", user_agent="Hans-Agent/1.0",
                        screenshot="/files/shot.png"))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        b = s.get(BugReport, "b-1")
        assert b.user_agent is None and b.screenshot is None
    assert not (smtp.dir / "shot.png").exists(), "Screenshot liegt noch auf der Platte"


def test_h3_dateien_werden_physisch_geloescht(client, welt, smtp):
    """H3: `sicherer_anhang.datei`, `file`-Anhänge am Mitglied, Profilbild."""
    from diakronos_app.models.core import FileModel as File
    from diakronos_app.models.diakonos import SichererAnhang

    for name in ("anhang.pdf", "ausweis.pdf", "foto.jpg", "avatar.png"):
        (smtp.dir / name).write_bytes(b"x")
    with welt.begin() as s:
        hans = s.get(Mitglied, HANS["name"])
        hans.foto = "/files/foto.jpg"
        s.get(User, HANS["email"]).user_image = "/files/avatar.png"
        s.add(SichererAnhang(name="an-1", mitglied=HANS["name"],
                             datei="/files/anhang.pdf", dateiname="attest.pdf"))
        s.add(File(name="f-1", file_name="ausweis.pdf",
                   file_url="/files/ausweis.pdf", is_private=True,
                   attached_to_doctype="Mitglied", attached_to_name=HANS["name"]))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    uebrig = sorted(p.name for p in smtp.dir.iterdir())
    assert uebrig == [], f"Dateien liegen noch auf der Platte: {uebrig}"


def test_h3_fremde_benachrichtigung_nennt_die_person_nicht_mehr(client, welt, smtp):
    """H3: Meldung an ein ANDERES Konto, die die Person im Text nennt."""
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        fremd = s.get(NotificationLog, "n-fremd")
        assert fremd is not None
        assert HANS["name"] not in str(fremd.email_content)
        assert "[gelöscht]" in str(fremd.email_content)
        eigen = s.get(NotificationLog, "n-eigen")
        assert eigen.email_content == "[Benachrichtigung zu einer gelöschten Person]"


# ── M1/M2/M3 ───────────────────────────────────────────────────────────────


def test_m1_antwort_enthaelt_keine_personendaten(client, welt, smtp):
    """M1: die Antwort von `loeschung_bestaetigen` nennt keine Werte der Person."""
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    antwort = r.text
    for wert in (HANS["name"], HANS["email"], HANS["telefon"], HANS["wohnort"],
                 HANS["plz"], "1977-07-07", "07.07.1977"):
        assert wert not in antwort, f"{wert} steht in der HTTP-Antwort"
    assert "geprueft" not in antwort


def test_m2_tls_mit_zertifikatspruefung(client, welt, patched_db, monkeypatch):
    """M2: STARTTLS/SSL bekommen `ssl.create_default_context()`."""
    import smtplib
    import ssl

    from diakronos_app import mailversand

    gesehen = {}

    class FakeSSL:
        """Nimmt die Verbindung an und bricht beim Senden ab (kein Netz)."""

        def __init__(self, host, port, timeout=None, context=None):
            gesehen["ssl"] = context

        def ehlo(self):
            pass

        def has_extn(self, name):
            return True

        def starttls(self, context=None):
            gesehen["starttls"] = context

        def login(self, *_a):
            pass

        def send_message(self, nachricht):
            raise RuntimeError("kein Netz im Test")

        def quit(self):
            pass

    class FakeSMTP(FakeSSL):
        def __init__(self, host, port, timeout=None):
            gesehen.setdefault("smtp", True)

    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSSL)
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    # Der echte Verbindungsaufbau ist der Prüfgegenstand — die Testnaht muss weg.
    monkeypatch.setattr(mailversand, "VERBINDUNG", None)
    from diakronos_app.models.smtp import SMTP_EINSTELLUNGEN_NAME, SmtpEinstellungen

    # MAIL-1: die Sicherheitsart steht in der DB-Zeile (nicht mehr in der ENV).
    for ssl_an in (True, False):
        gesehen.clear()
        with patched_db.begin() as s:
            s.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME).sicherheit = (
                "ssl" if ssl_an else "starttls")
        with pytest.raises(mailversand.MailVersandFehler):
            mailversand.sende(mailversand.Mail(an="a@b.de", betreff="x", text="y"))
        schluessel = "ssl" if ssl_an else "starttls"
        context = gesehen.get(schluessel)
        assert isinstance(context, ssl.SSLContext), (schluessel, gesehen)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True


def test_m3_einwilligung_ohne_ip_und_browserkennung(client, welt, smtp):
    """M3: `dsgvo_einwilligung.ip_adresse/user_agent` der Person werden genullt."""
    from diakronos_app.models.diakonos import DSGVOEinwilligung

    with welt.begin() as s:
        s.add(DSGVOEinwilligung(name="e-1", mitglied=HANS["name"],
                                typ="datenschutz", aktion="erteilt",
                                ip_adresse="198.51.100.0",
                                user_agent="Hans-Agent/1.0", widerrufen=False))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    treffer = _durchsuchen(welt, ["198.51.100.0", "Hans-Agent"])
    assert treffer == [], treffer


# ── N1/N3/N5 ───────────────────────────────────────────────────────────────


def test_n1_login_der_geloeschten_person_wirklich_abgelehnt(client, welt, smtp):
    """N1: Login-Versuch mit dem RICHTIGEN Parameter (`usr`)."""
    from diakronos_app.frappe_compat import sitzungen

    sid, _ = sitzungen.anlegen(HANS["email"])
    assert _antrag_und_loeschen(client, welt).status_code == 200
    assert sitzungen.lesen(sid) is None
    r = client.post("/api/method/login",
                    json={"usr": HANS["email"], "pwd": "irgendwas"})
    assert r.status_code >= 400, r.text


def test_n3_inventar_ohne_doppelte_schluessel():
    """N3: `SPALTEN["notification_log"]` hatte `subject`/`email_content` zweimal."""
    import inspect

    from diakronos_app import dsgvo_anonymisierung as modul

    quelle = inspect.getsource(modul)
    block = quelle.split('"notification_log": {', 1)[1].split("}", 1)[0]
    schluessel = re.findall(r'"([a-z_]+)":', block)
    assert len(schluessel) == len(set(schluessel)), schluessel


# ── Die Reviewer-Probe (R-DSGVO-1), mit sicherer Erwartung ─────────────────


def test_zz_review_probe_a_ressourcenmoderation(client, welt, smtp):
    """Probe A: `ressourcen_buchung.moderiert_von` (FK user) blockierte die
    Löschung — die Spalte ist jetzt im Inventar (user_null)."""
    from diakronos_app.models.diakonos import RessourcenBuchung

    with welt.begin() as s:
        s.add(RessourcenBuchung(name="buchung-1", moderiert_von=HANS["email"],
                                status="Genehmigt"))
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    assert len(smtp.nachrichten) == 1
    with welt() as s:
        assert s.get(RessourcenBuchung, "buchung-1").moderiert_von is None


def test_zz_review_probe_b_klarname_kollateral(client, welt, smtp):
    """Probe B: Klarname-ID + voller Bestand — keine Reste, kein Kollateral."""
    from diakronos_app.models.diakonos import DienstplanTeilnehmer
    from diakronos_app.models.kronos import AblaufplanPosition

    with welt.begin() as s:
        s.add(DienstplanTeilnehmer(name="teiln-1", mitglied=HANS["name"],
                                   notiz_intern="Nur morgens da"))
        s.add(AblaufplanPosition(name="abl-1", verantwortlicher=HANS["name"],
                                 bezeichnung="Lesung"))
    vorher = _snapshot(welt.kw["bind"])
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    treffer = _durchsuchen(welt, [HANS["name"], HANS["email"],
                                  HANS["email"].split("@")[0],
                                  HANS["telefon"], "07119876543"])
    assert treffer == [], treffer
    nachher = _snapshot(welt.kw["bind"])
    # Zeilen ANDERER Mitglieder unverändert (außer exakt ersetzten Nennungen).
    geaendert = []
    for schluessel, zeile in nachher.items():
        tabelle, pk = schluessel
        alt = vorher.get(schluessel)
        if alt is None or alt == zeile:
            continue
        geaendert.append((tabelle, pk, {k: [alt.get(k), zeile.get(k)]
                                        for k in zeile if alt.get(k) != zeile.get(k)}))
    erlaubt = {"mitglied_bereich", "mitglied_beziehung", "audit_log",
               "notification_log", "ablaufplan_position", "dienstplan_teilnehmer",
               "dsgvo_einwilligung", "loeschantrag"}
    fremde = [g for g in geaendert
              if g[0] not in erlaubt and not _gehoert_zur_person(g)]
    assert fremde == [], f"Fremde Zeilen verändert: {fremde[:5]}"


def _gehoert_zur_person(aenderung) -> bool:
    """Gehört die geänderte Zeile zur gelöschten Person (nach der Umhängung)?"""
    tabelle, _pk, diff = aenderung
    return tabelle in {"mitglied", "anmeldung", "user", "has_role", "file",
                       "sicherer_anhang", "bug_report", "pr_eintrag",
                       "pr_merkmal_wert", "pr_verlauf", "rollenbesetzung"}
