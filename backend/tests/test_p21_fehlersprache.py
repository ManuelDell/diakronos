"""OP-UI-15: verständliche Rückmeldungen statt interner Objekt-/Feldnamen."""
import pytest
from diakronos_app.planrahmen.dienste import Dienste, DienstFehler, fehler
from test_p1_10_lieder_material import welt, BRUNO


def test_fehlende_planvorlage_erklaert_naechsten_schritt(welt):
    with pytest.raises(DienstFehler) as exc:
        Dienste(welt, BRUNO)._typ('nicht-vorhanden')
    meldung = exc.value.meldungen[0]
    assert 'Planvorlage' in meldung['meldung']
    assert 'Übersicht' in meldung['hinweis']
    assert 'Schema' not in meldung['hinweis']


def test_default_hinweis_ist_fuer_planer_verstaendlich():
    with pytest.raises(DienstFehler) as exc:
        fehler('/titel', 'Bitte einen Titel eintragen.')
    assert 'Eingaben' in exc.value.meldungen[0]['hinweis']
    assert 'API' not in exc.value.meldungen[0]['hinweis']
