"""P1-10 — Lieder & Material (Backend-Anteile der Nachtbefunde).

Reproduktionstests zu den Befunden des Gesamtberichts (Abschnitt 3.5):

  UXM-R1   Lied speichern mit unbekannter Kategorie/Anlass: kein roher
           SQL-Fehler, keine Teilspeicherung — Kategorien/Anlaesse werden
           vorab gegen den Katalog geprueft (fehlende werden angelegt).
  UXM-R5   Material (Noten/Audio) haengt an der Liedfassung und ist damit
           fuer jede angemeldete Person lesbar (nicht nur Hochlader/Admin).
  UXM-R7   `lied_material_hinzufuegen/-loeschen` funktionieren OHNE Plantyp
           (Aufruf aus dem Lied-Detail) mit der Psalmos-Regel.
  UXM-R8   Die Materialliste liefert die Kennung der Kind-Zeile (`material`),
           die `lied_material_loeschen` erwartet.
  UXM-R10  `get_liedgruppe_detail` liefert je Zeile den Titel (keine rohe ID).
  UXM-R11  Liedersuche findet Nummer/Buch/CCLI; '%' ist kein Platzhalter mehr.
  UXM-R9   Liedgruppen anlegen/aendern/loeschen.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

MUSIK = "diakronos.psalmos.api.musik"
PLANRAHMEN = "diakronos.planrahmen.api"

ANNA = "anna@example.org"       # eingeloggt, KEIN Schreibrecht
BRUNO = "bruno@example.org"     # Musikverantwortlicher
ADMIN = "admin@example.org"     # Mitgliederadministrator


@pytest.fixture()
def welt(patched_db):
    """Minimaler Liederbestand + Rechte (Musik und Worship)."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Dienstbereich,
        Gruppe,
        GruppeVerantwortlicher,
    )
    from diakronos_app.models.psalmos import (
        Lied,
        LiedGruppenzuordnung,
        LiedMaterial,
        Liedfassung,
        Liedgruppe,
        LiedgruppeLied,
        Liedstrophe,
        Liedanlass,
        Liedkategorie,
    )
    sess = patched_db()
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=1),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=1),
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
        Dienstbereich(name="Musik und Worship", ministry="Musik und Worship",
                      docstatus=0, idx=0),
        Gruppe(name="GRP-WORSHIP", gruppenname="Worship-Band",
               dienstbereich="Musik und Worship", docstatus=0, idx=0),
        GruppeVerantwortlicher(name="GV-1", parent="GRP-WORSHIP",
                               parenttype="Gruppe", parentfield="verantwortliche",
                               user=BRUNO, docstatus=0, idx=1),
        # Katalog: nur "Lobpreis" als Kategorie, "Gottesdienst" als Anlass.
        Liedkategorie(name="Lobpreis", kategoriename="Lobpreis", docstatus=0, idx=0),
        Liedanlass(name="Gottesdienst", anlassname="Gottesdienst", docstatus=0, idx=0),
    ])
    sess.add_all([
        Lied(name="LIED-1", titel="Grosser Gott", gesangbuch_nummer="1",
             buch="JN", ccli_nummer="12345", quelle="buch", aktiv=1,
             rechte_status="gemeinfrei", docstatus=0, idx=0),
        Lied(name="LIED-2", titel="Amazing Grace", gesangbuch_nummer="1297",
             buch="JN", ccli_nummer=None, quelle="buch", aktiv=0,
             rechte_status="geschuetzt", docstatus=0, idx=0),
    ])
    sess.add_all([
        Liedstrophe(name="ST-1", parent="LIED-1", parenttype="Lied",
                    parentfield="strophen", nummer=1, typ="Strophe",
                    text="Grosser Gott wir loben dich", sprache="de",
                    nur_chor=0, docstatus=0, idx=1),
        Liedfassung(name="FAS-1", lied="LIED-1", fassungsname="Chorsatz",
                    ist_standard=1, besetzung="Chor", docstatus=0, idx=0),
    ])
    sess.add_all([
        LiedMaterial(name="MAT-1", parent="FAS-1", parenttype="Liedfassung",
                     parentfield="material", art="noten_pdf", stimme="Sopran",
                     anhang="/files/s.pdf", beschreibung="Partitur",
                     docstatus=0, idx=1),
    ])
    sess.add_all([
        LiedGruppenzuordnung(name="LGZ-1", parent="LIED-1", parenttype="Lied",
                             parentfield="gruppen", gruppe="GRP-WORSHIP",
                             docstatus=0, idx=1),
    ])
    sess.add_all([
        Liedgruppe(name="LGRP-1", gruppenname="Oster-Set", typ="Sammlung",
                   status="Aktiv", docstatus=0, idx=0),
    ])
    sess.add_all([
        LiedgruppeLied(name="LGL-1", parent="LGRP-1", parenttype="Liedgruppe",
                       parentfield="lieder", lied="LIED-1", fassung="FAS-1",
                       reihenfolge=1, nummer=1, szene="Einzug",
                       notiz="Auftakt", docstatus=0, idx=1),
    ])
    sess.add_all([
        HasRole(name="HR-1", parent=ADMIN, parenttype="User",
                parentfield="roles", role="Mitgliederadministrator",
                docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_anna(welt):
    set_user(ANNA)
    yield ANNA
    set_user("Administrator")


@pytest.fixture()
def als_bruno(welt):
    set_user(BRUNO)
    yield BRUNO
    set_user("Administrator")


@pytest.fixture()
def als_admin(welt):
    set_user(ADMIN)
    yield ADMIN
    set_user("Administrator")


def welt_direct():
    from diakronos_app.db import SessionLocal
    return SessionLocal()


# ── Endpunkte registriert ───────────────────────────────────────────────────

@pytest.mark.parametrize("fn", ["save_liedgruppe", "delete_liedgruppe"])
def test_neue_liedgruppen_endpunkte_registriert(fn):
    import diakronos_app.api.psalmos.musik  # noqa: F401 — registriert die Endpunkte
    assert lookup(f"{MUSIK}.{fn}") is not None


# ── UXM-R1 ──────────────────────────────────────────────────────────────────

def test_save_lied_unbekannte_kategorie_legt_katalog_an(client, als_bruno):
    """Unbekannte Kategorie/Anlass fuehren NICHT zum rohen Fremdschluessel-Fehler.

    Vorher: 417 mit SQL-Text der FK-Verletzung, Lied+Strophen aber gespeichert.
    Jetzt: sauberer Erfolg; die neuen Katalogeintraege werden mit angelegt.
    """
    from diakronos_app.models.psalmos import LiedKategorie, Liedkategorie, Liedanlass

    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "JN 1297", "quelle": "buch", "buch": "JN",
        "gesangbuch_nummer": "1297",
        "strophen": [{"nummer": 1, "typ": "Strophe", "text": "Neu"}],
        "kategorien": ["Lob"], "anlaesse": ["Chorprobe"],
        # P1-10b Befund 7: der Bestand kennt JN 1297 schon (LIED-2); hier wird
        # das bewusste Doppel bestaetigt, damit der Test weiterhin nur die
        # Katalog-Anlage prueft.
        "dublette_bestaetigt": 1,
    }})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["success"] is True

    sess = welt_direct()
    kats = {k.name for k in sess.query(Liedkategorie).all()}
    anl = {a.name for a in sess.query(Liedanlass).all()}
    assert "Lob" in kats, "unbekannte Kategorie wurde angelegt"
    assert "Chorprobe" in anl, "unbekannter Anlass wurde angelegt"
    # Die Zuordnungen verweisen auf die Katalogeintraege (kein FK-Verstoss).
    kind = sess.query(LiedKategorie).filter(LiedKategorie.kategorie == "Lob").all()
    assert kind, "Kind-Zeile zeigt auf den neuen Katalogeintrag"
    sess.close()


def test_save_lied_ist_eine_transaktion_bei_fehler(client, als_bruno, monkeypatch):
    """Scheitert das Schreiben, entsteht KEIN Teilstueck (keine Teilspeicherung).

    Vorher (UXM-R1): Jeder Kind-Schritt committete einzeln. Ein Fehler beim
    Schreiben einer Kind-Zeile liess das bereits angelegte Lied in der DB
    zurueck — der Nutzer sah einen Fehler, das halbe Lied blieb aber bestehen.

    Hier wird der Kind-Schreibvorgang gezielt zum Scheitern gebracht; die
    Aussage ist: das zuvor angelegte Lied ist NICHT mehr da.
    """
    from diakronos_app.frappe_compat import api_helpers as _sh
    from diakronos_app.models.psalmos import Lied

    sess = welt_direct()
    vorher = sess.query(Lied).count()
    sess.close()

    echt = _sh._child_insert

    def platzt_bei_strophen(child_doctype, *a, **kw):
        if child_doctype == "Liedstrophe":
            from diakronos_app.frappe_compat.exceptions import ValidationError
            raise ValidationError("Kind-Schreiben fehlgeschlagen (Test)")
        return echt(child_doctype, *a, **kw)

    monkeypatch.setattr(_sh, "_child_insert", platzt_bei_strophen)

    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "Haelfte",
        "strophen": [{"nummer": 1, "typ": "Strophe", "text": "X"}],
    }})
    assert r.status_code == 417, r.text

    sess = welt_direct()
    assert sess.query(Lied).filter(Lied.titel == "Haelfte").count() == 0, \
        "kein halbes Lied in der DB (Transaktion zurueckgerollt)"
    assert sess.query(Lied).count() == vorher
    sess.close()


# ── UXM-R11 ─────────────────────────────────────────────────────────────────

def test_suche_findet_nummer_und_buch(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "1297"})
    assert r.status_code == 200, r.text
    assert [x["titel"] for x in r.json()["message"]] == ["Amazing Grace"]


def test_suche_buch_und_nummer_getrennt(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "JN 1297"})
    assert r.status_code == 200, r.text
    assert [x["titel"] for x in r.json()["message"]] == ["Amazing Grace"]


def test_suche_prozent_ist_kein_platzhalter(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "%"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == [], "'%' darf nicht alle Lieder liefern"


def test_suche_ignoriert_gross_klein(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lieder", params={"suche": "grosser"})
    assert r.status_code == 200, r.text
    assert [x["titel"] for x in r.json()["message"]] == ["Grosser Gott"]


# ── UXM-R10 ─────────────────────────────────────────────────────────────────

def test_liedgruppe_detail_liefert_titel(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_liedgruppe_detail",
                   params={"liedgruppe": "LGRP-1"})
    assert r.status_code == 200, r.text
    zeile = r.json()["message"]["lieder"][0]
    assert zeile["titel"] == "Grosser Gott", "Titel statt roher Kennung"
    assert zeile["anzeige"] == "JN 1"
    assert zeile["lied"] == "LIED-1"


# ── UXM-R8 ──────────────────────────────────────────────────────────────────

def test_lied_detail_material_liefert_zeilenkennung(client, als_anna):
    r = client.get(f"/api/method/{MUSIK}.get_lied_detail", params={"lied": "LIED-1"})
    assert r.status_code == 200, r.text
    mat = r.json()["message"]["fassungen"][0]["material"][0]
    assert mat["material"] == "MAT-1", "Kind-Zeilen-Kennung mitgeliefert"
    assert mat["datei"]["datei_url"] == "/files/s.pdf"


# ── UXM-R7: Material ohne Plantyp ───────────────────────────────────────────

def test_material_hinzufuegen_ohne_plantyp_als_musikverantwortlicher(client, als_bruno):
    """Ohne Plantyp gilt die Psalmos-Regel — Bruno darf, Anna nicht."""
    r = client.post(f"/api/method/{PLANRAHMEN}.lied_material_hinzufuegen", json={
        "lied": "LIED-1", "art": "noten_pdf", "dateiname": "test.pdf",
        "datei_url": "/files/abc-test.pdf",
    })
    assert r.status_code == 200, r.text
    assert r.json()["message"]["success"] is True


def test_material_hinzufuegen_ohne_plantyp_ohne_recht_ist_verweigert(client, als_anna):
    r = client.post(f"/api/method/{PLANRAHMEN}.lied_material_hinzufuegen", json={
        "lied": "LIED-1", "art": "noten_pdf", "dateiname": "test.pdf",
        "datei_url": "/files/abc-test.pdf",
    })
    assert r.status_code == 417, r.text
    assert "Berechtigung" in r.text


# ── UXM-R5: Material-ACL ────────────────────────────────────────────────────

def test_material_an_liedfassung_ist_fuer_angemeldete_lesbar(client, als_anna):
    """Eine an die Liedfassung gebundene Datei darf jede angemeldete Person lesen."""
    from diakronos_app.models.core import FileModel
    from diakronos_app.db import SessionLocal

    sess = SessionLocal()
    sess.add(FileModel(name="F1", file_name="noten.pdf", file_url="/files/f1-noten.pdf",
                       is_private=True, attached_to_doctype="Liedfassung",
                       attached_to_name="FAS-1", file_size=10, content_hash="x",
                       owner="jemand@example.org", modified_by="jemand@example.org"))
    sess.commit()
    sess.close()

    # Anna ist NICHT der Hochlader — trotzdem erlaubt (Lieder-Leserecht).
    from diakronos_app.files import attachment_allowed
    assert attachment_allowed("Liedfassung", "FAS-1", "read") is True


# ── UXM-R9: Liedgruppen pflegen ─────────────────────────────────────────────

def test_liedgruppe_anlegen_und_loeschen(client, als_admin):
    r = client.post(f"/api/method/{MUSIK}.save_liedgruppe", json={"daten": {
        "gruppenname": "Neue Sammlung", "typ": "Sammlung", "status": "Aktiv",
        "lieder": [{"lied": "LIED-1"}, {"lied": "LIED-2", "nummer": 2}],
    }})
    assert r.status_code == 200, r.text
    name = r.json()["message"]["liedgruppe"]
    assert name

    d = client.get(f"/api/method/{MUSIK}.get_liedgruppe_detail",
                   params={"liedgruppe": name})
    assert d.status_code == 200, d.text
    lieder = d.json()["message"]["lieder"]
    assert [z["lied"] for z in lieder] == ["LIED-1", "LIED-2"]
    assert [z["reihenfolge"] for z in lieder] == [1, 2]

    x = client.post(f"/api/method/{MUSIK}.delete_liedgruppe",
                    json={"liedgruppe": name})
    assert x.status_code == 200, x.text
    nach = client.get(f"/api/method/{MUSIK}.get_liedgruppe_detail",
                      params={"liedgruppe": name})
    assert nach.status_code == 404, "geloeschte Liedgruppe nicht mehr auffindbar"


def test_liedgruppe_ohne_namen_fehler(client, als_admin):
    r = client.post(f"/api/method/{MUSIK}.save_liedgruppe",
                    json={"daten": {"gruppenname": "  "}})
    assert r.status_code == 417, r.text


def test_liedgruppe_anlegen_ohne_recht_ist_verweigert(client, als_anna):
    r = client.post(f"/api/method/{MUSIK}.save_liedgruppe",
                    json={"daten": {"gruppenname": "X", "typ": "Sammlung"}})
    assert r.status_code == 403, r.text


# ── Review-Nacharbeit P1-10b: M1 Material-Bindung ───────────────────────────

def _file(sess, name, url, owner, attached=None):
    from diakronos_app.models.core import FileModel
    sess.add(FileModel(name=name, file_name=url.rsplit("/", 1)[-1], file_url=url,
                       is_private=True, attached_to_doctype=attached,
                       file_size=10, content_hash="x", owner=owner, modified_by=owner))
    sess.commit()


def test_material_bindet_nur_eigene_datei(client, als_bruno):
    """M1: Eine fremde private Datei darf NICHT gebunden werden (417)."""
    from diakronos_app.db import SessionLocal
    sess = SessionLocal()
    _file(sess, "FREMD-1", "/files/fremd.pdf", ANNA)  # gehoert Anna
    sess.close()

    r = client.post(f"/api/method/{PLANRAHMEN}.lied_material_hinzufuegen", json={
        "lied": "LIED-1", "art": "noten_pdf", "dateiname": "fremd.pdf",
        "datei_url": "/files/fremd.pdf",
    })
    assert r.status_code == 417, r.text
    assert "gehört nicht dir" in r.text

    # Die fremde Datei bleibt ungebunden (kein Rechte-Leck).
    from diakronos_app.models.core import FileModel
    from diakronos_app.db import SessionLocal as S2
    s2 = S2()
    zeile = s2.query(FileModel).filter(FileModel.name == "FREMD-1").one()
    assert zeile.attached_to_doctype is None, "fremde Datei wurde gebunden!"
    s2.close()


def test_material_bindet_eigene_datei(client, als_bruno):
    """M1: Die eigene (im selben Vorgang hochgeladene) Datei wird gebunden."""
    from diakronos_app.db import SessionLocal
    sess = SessionLocal()
    _file(sess, "EIGEN-1", "/files/eigen.pdf", BRUNO)
    sess.close()

    r = client.post(f"/api/method/{PLANRAHMEN}.lied_material_hinzufuegen", json={
        "lied": "LIED-1", "art": "noten_pdf", "dateiname": "eigen.pdf",
        "datei_url": "/files/eigen.pdf",
    })
    assert r.status_code == 200, r.text

    from diakronos_app.models.core import FileModel
    from diakronos_app.db import SessionLocal as S2
    s2 = S2()
    zeile = s2.query(FileModel).filter(FileModel.name == "EIGEN-1").one()
    assert zeile.attached_to_doctype == "Liedfassung"
    assert zeile.attached_to_name == "FAS-1"
    s2.close()


def test_material_bindet_keine_anderweitig_gebundene_datei(client, als_bruno):
    """M1: Eine bereits anderweitig gebundene Datei wird nicht umgehaengt."""
    from diakronos_app.db import SessionLocal
    sess = SessionLocal()
    _file(sess, "GEB-1", "/files/geb.pdf", BRUNO, attached="Mitglied")
    sess.close()

    r = client.post(f"/api/method/{PLANRAHMEN}.lied_material_hinzufuegen", json={
        "lied": "LIED-1", "art": "noten_pdf", "dateiname": "geb.pdf",
        "datei_url": "/files/geb.pdf",
    })
    assert r.status_code == 417, r.text
    assert "anderweitig zugeordnet" in r.text


def test_material_altbestand_ohne_zeile_bindet_nichts(client, als_bruno):
    """M1: Fehlt die Datei-Zeile (toter Verweis), bleibt der Vorgang erfolgreich."""
    r = client.post(f"/api/method/{PLANRAHMEN}.lied_material_hinzufuegen", json={
        "lied": "LIED-1", "art": "noten_pdf", "dateiname": "unbekannt.pdf",
        "datei_url": "/files/gibt-es-nicht.pdf",
    })
    assert r.status_code == 200, r.text


# ── Review-Nacharbeit P1-10b: M2 Liedgruppe mit Plan-Verwendung ─────────────

def test_delete_liedgruppe_mit_verwendung_klartext(client, als_admin, welt):
    """M2: Verweise aus Plan-Vorlagen -> Klartext statt roher FK-Fehler."""
    from diakronos_app.models.diakonos import (
        DienstplanVorlage,
        DienstplanVorlageSlot,
    )
    sess = welt
    sess.add_all([
        DienstplanVorlage(name="VOR-1", vorlagenname="Chorplan",
                          dienstbereich="Musik und Worship", docstatus=0, idx=0),
        DienstplanVorlageSlot(name="VOR-1-S1", parent="VOR-1",
                              parenttype="DienstplanVorlage", parentfield="slots",
                              inhalt_sammlung="LGRP-1", docstatus=0, idx=1),
    ])
    sess.commit()

    r = client.post(f"/api/method/{MUSIK}.delete_liedgruppe",
                    json={"liedgruppe": "LGRP-1"})
    assert r.status_code == 417, r.text
    assert "verwendet" in r.text
    assert "1 Plan-Vorlage" in r.text
    # Kein roher SQL-/FK-Text.
    assert "violates foreign key" not in r.text.lower()
    assert "IntegrityError" not in r.text

    # Die Liedgruppe ist unangetastet.
    d = client.get(f"/api/method/{MUSIK}.get_liedgruppe_detail",
                   params={"liedgruppe": "LGRP-1"})
    assert d.status_code == 200


# ── Review-Nacharbeit P1-10b: kleine Befunde 4, 5, 6 ────────────────────────

def test_kategorie_name_zu_lang_klartext(client, als_bruno):
    """Befund 4: >140 Zeichen -> Klartext statt roher DB-Fehler."""
    lang = "K" * 141
    r = client.post(f"/api/method/{MUSIK}.save_lied", json={"daten": {
        "titel": "Zu lang", "kategorien": [lang],
    }})
    assert r.status_code == 417, r.text
    assert "140" in r.text
    assert "value too long" not in r.text.lower()


def test_liedgruppe_unbekanntes_lied_klartext(client, als_admin):
    """Befund 5: toter Lied-Verweis -> Klartext statt DoesNotExistError."""
    r = client.post(f"/api/method/{MUSIK}.save_liedgruppe", json={"daten": {
        "gruppenname": "Mit totem Lied", "typ": "Sammlung",
        "lieder": [{"lied": "GIBT-ES-NICHT"}],
    }})
    assert r.status_code == 417, r.text
    assert "nicht gefunden" in r.text
    assert "existiert nicht" not in r.text


def test_liedgruppe_unbekannte_gruppe_klartext(client, als_admin):
    """Befund 5: unbekannte uebergeordnete Gruppe -> Klartext."""
    r = client.post(f"/api/method/{MUSIK}.save_liedgruppe", json={"daten": {
        "gruppenname": "Falsche Obergruppe", "typ": "Sammlung",
        "gruppe": "GRP-GIBT-ES-NICHT",
    }})
    assert r.status_code == 417, r.text
    assert "nicht gefunden" in r.text


def test_liedgruppe_altwert_typ_bleibt_speicherbar(client, als_admin, welt):
    """Befund 6: unveraenderter Altwert beim Typ blockiert das Speichern nicht."""
    sess = welt
    from diakronos_app.models.psalmos import Liedgruppe
    sess.add(Liedgruppe(name="LGRP-ALT", gruppenname="Alte Gruppe",
                        typ="Liedersammlung (alt)", status="Aktiv",
                        docstatus=0, idx=0))
    sess.commit()

    # Altwert unveraendert mitsenden -> ok.
    r = client.post(f"/api/method/{MUSIK}.save_liedgruppe", json={"daten": {
        "name": "LGRP-ALT", "gruppenname": "Alte Gruppe neu",
        "typ": "Liedersammlung (alt)",
    }})
    assert r.status_code == 200, r.text

    # NEUER unbekannter Wert bleibt verboten.
    r2 = client.post(f"/api/method/{MUSIK}.save_liedgruppe", json={"daten": {
        "name": "LGRP-ALT", "typ": "Erfunden",
    }})
    assert r2.status_code == 417, r2.text
    assert "Unbekannter Typ" in r2.text


# ── Review-Nacharbeit P1-10b: Befund 3 Urheberrecht bei Audio ────────────────

def test_audio_gesperrtes_lied_nur_fuer_musikverantwortliche(client, als_anna):
    """Befund 3: Audio zu gesperrtem Lied wird fuer normale Nutzer verweigert."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.files import attachment_allowed
    from diakronos_app.models.psalmos import Lied
    from diakronos_app.frappe_compat.session import set_user

    sess = SessionLocal()
    sess.query(Lied).filter(Lied.name == "LIED-1").update(
        {"rechte_status": "gesperrt", "streaming_erlaubt": False})
    sess.commit()
    sess.close()

    set_user(ANNA)
    try:
        assert attachment_allowed("Liedfassung", "FAS-1", "read",
                                  dateiname="aufnahme.mp3") is False
        # Noten (PDF) bleiben trotz gesperrtem Status lesbar.
        assert attachment_allowed("Liedfassung", "FAS-1", "read",
                                  dateiname="noten.pdf") is True
    finally:
        set_user("Administrator")

    set_user(BRUNO)
    try:
        assert attachment_allowed("Liedfassung", "FAS-1", "read",
                                  dateiname="aufnahme.mp3") is True
    finally:
        set_user("Administrator")
