"""N12 / N-1 (R-N10): Einwilligungsbeleg mit Fassungsnummer und Kennung.

DER BEFUND (N-1)
-------------------------------
Der Beleg (`Anmeldung.dsgvo_text_snapshot`) trug nur den Wortlaut, aber keine
Angabe, WELCHE Fassung die Person angezeigt bekam. Wurde der Text zwischen
Anzeige und Absenden geaendert, belegte das stille Speichern den neuen Text —
die Person haette etwas anderes zugestimmt (Art. 7 DSGVO: angezeigt = belegt).

Die Behebung:
  * ``gemeinde.wirksame_fassung()`` liefert Fassungsnummer, Text und eine
    Kennung (SHA-256, 16 Stellen) der geltenden Veroeffentlichung.
  * ``submit_registrierung``/``submit_gast`` nehmen ``dsgvo_fassung`` (die
    angezeigte Fassung) entgegen. Weicht sie ab, wird die Abgabe abgelehnt.
  * Der Beleg traegt den Kopf ``Fassung <nr> (<kennung>)``.

Die Tests sind Reproduktionstests: ohne die Aenderung sind sie rot.
"""

from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte

MODUL = "diakronos.diakonos.api.registrierung"
SLUG = "abc123slug"
LINK = "RL-1"


def _link(**werte):
    from diakronos_app.models.diakonos import Registrierungslink

    daten = {
        "name": LINK, "bezeichnung": "Einladung", "typ": "Mitglied-Registrierung",
        "aktiv": True, "slug": SLUG, "max_anmeldungen": 0,
        "anmeldungen_count": 0, "docstatus": 0, "idx": 0,
    }
    daten.update(werte)
    return Registrierungslink(**daten)


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    yield sess
    sess.close()


def _veroeffentliche(text: str):
    """Schreibt eine VEROEFFENTLICHTE Einwilligungsfassung in die DB."""
    from datetime import datetime

    from diakronos_app.models.gemeinde import (
        DATENSCHUTZ_VEROEFFENTLICHT_NAME,
        DatenschutzTextVeroeffentlicht,
    )
    from diakronos_app.db import SessionLocal

    with SessionLocal() as sess:
        zeile = sess.get(DatenschutzTextVeroeffentlicht, DATENSCHUTZ_VEROEFFENTLICHT_NAME)
        if zeile is None:
            zeile = DatenschutzTextVeroeffentlicht(
                name=DATENSCHUTZ_VEROEFFENTLICHT_NAME, version=1, created=datetime.now()
            )
            sess.add(zeile)
        zeile.einwilligung = text
        sess.commit()


def _post(client, **extra):
    daten = {"token": SLUG, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": True}
    daten.update(extra)
    return client.post(f"/api/method/{MODUL}.submit_registrierung", data=daten)


# ── wirksame_fassung ────────────────────────────────────────────────────────


def test_wirksame_fassung_liefert_nummer_text_kennung(patched_db) -> None:
    """Die Fassung traegt Nummer, Text und stabile Kennung."""
    from diakronos_app.api.gemeinde import wirksame_fassung

    _veroeffentliche("Neuer Einwilligungstext der Gemeinde.")
    fassung = wirksame_fassung()

    assert fassung["text"] == "Neuer Einwilligungstext der Gemeinde."
    assert isinstance(fassung["version"], int) and fassung["version"] >= 1
    assert fassung["kennung"], "Kennung fehlt"
    assert len(fassung["kennung"]) == 16


def test_kennung_haengt_am_text_nicht_an_der_nummer(patched_db) -> None:
    """Zwei verschiedene Wortlaute haben verschiedene Kennungen (N-1)."""
    from diakronos_app.api.gemeinde import _text_kennung

    assert _text_kennung("A") != _text_kennung("B")
    # Leerer Text darf nicht abstuerzen und liefert eine Kennung.
    assert len(_text_kennung("")) == 16


# ── Beleg traegt die Fassung ────────────────────────────────────────────────


def test_beleg_traegt_fassungsnummer_und_kennung(welt, client, patched_db) -> None:
    """Der Einwilligungsbeleg nennt Fassung samt Kennung (Kopfzeile)."""
    from sqlalchemy import select

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldung

    _veroeffentliche("Bestaetigter Wortlaut.")
    r = _post(client, dsgvo_fassung=1)
    assert r.status_code == 200, r.text

    with SessionLocal() as sess:
        anm = sess.scalars(select(Anmeldung)).one()
    beleg = anm.dsgvo_text_snapshot or ""
    assert beleg.startswith("Fassung 1 ("), beleg
    assert "Bestaetigter Wortlaut." in beleg


# ── Veraltete Fassung wird abgelehnt ────────────────────────────────────────


def test_veraltete_fassung_wird_abgelehnt(welt, client, patched_db) -> None:
    """Wer eine alte Fassung angezeigt bekam, darf nicht still bestaetigen."""
    from sqlalchemy import select

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Anmeldung

    # Die Person hat Fassung 1 gesehen; die Gemeinde hat inzwischen die Fassung
    # gewechselt (version=2).
    _veroeffentliche("Erster Wortlaut.")
    from datetime import datetime

    from diakronos_app.models.gemeinde import (
        DATENSCHUTZ_VEROEFFENTLICHT_NAME,
        DatenschutzTextVeroeffentlicht,
    )

    with SessionLocal() as sess:
        zeile = sess.get(DatenschutzTextVeroeffentlicht, DATENSCHUTZ_VEROEFFENTLICHT_NAME)
        zeile.einwilligung = "Zweiter Wortlaut."
        zeile.version = 2
        zeile.modified = datetime.now()
        sess.commit()

    r = _post(client, dsgvo_fassung=1)
    assert r.status_code >= 400, r.text
    assert "zwischenzeitlich" in r.text

    with SessionLocal() as sess:
        assert sess.scalars(select(Anmeldung)).all() == [], "veraltete Fassung wurde gespeichert"


def test_passende_fassung_wird_angenommen(welt, client, patched_db) -> None:
    """Mit der geltenden Fassungsnummer laeuft die Abgabe durch."""
    _veroeffentliche("Gueltiger Wortlaut.")
    r = _post(client, dsgvo_fassung=1)
    assert r.status_code == 200, r.text


def test_ohne_fassungsangabe_bleibt_erlaubt(welt, client, patched_db) -> None:
    """Altaufrufer ohne Fassung werden nicht blockiert (Rueckwaertskompatibilitaet)."""
    _veroeffentliche("Irgendein Wortlaut.")
    r = _post(client)  # ohne dsgvo_fassung
    assert r.status_code == 200, r.text


def test_ungueltige_fassungsangabe_wird_abgelehnt(welt, client, patched_db) -> None:
    """Ein nicht-numerischer Wert ist ein Eingabefehler."""
    _veroeffentliche("Wortlaut.")
    r = _post(client, dsgvo_fassung="abc")
    assert r.status_code >= 400, r.text
