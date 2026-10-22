"""Operator-Nachtrag P1-14b: 403 vor Kontextfehler, Historie ohne Planbindung."""
from datetime import date

import pytest

from test_p1_14b_plaene_archiv import (
    PFAD, _progdefinition, _chorplan_historien_test, _liedslot_und_quelle,
    anmelden, aufruf, stammdaten,
)


@pytest.mark.parametrize('weg,extra', [
    ('bedarf', {}), ('stammdaten_holen', {}),
    ('merkmal_kandidaten', {'schluessel': 'dirigent'}), ('lied_rechte', {}),
])
@pytest.mark.parametrize('fremder_typ', [False, True])
def test_mitglied_ohne_rolle_bekommt_403_vor_zuordnungsfehler(client, patched_db, weg, extra, fremder_typ):
    stammdaten(patched_db, 'planer', 'mitglied')
    anmelden(client, 'planer')
    for key in ['prog-p114b', 'anderer-typ']:
        aufruf(client, 'plantyp_speichern', definition=_progdefinition(key), gueltig_ab='2026-01-01')
    p = aufruf(client, 'plan_anlegen', plantyp='prog-p114b', titel='Plan',
               von='2026-12-01', bis='2026-12-31', parameter={'uhrzeit': '17:00'})['id']
    aufruf(client, 'veroeffentlichen', plan=p)
    anmelden(client, 'mitglied')
    r = client.post(PFAD + weg, json={'plantyp': 'anderer-typ' if fremder_typ else 'prog-p114b',
                                    'plan': p, **extra})
    assert r.status_code == 403, r.text


def test_trockenlauf_ohne_planbindung_zaehlt_fremde_zukunft_nicht_beidseitig():
    from diakronos_app.planrahmen.engine.datenquelle import Historieneintrag
    from diakronos_app.planrahmen.engine.modell import Termin
    from diakronos_app.planrahmen.regeln.auswertung import Kontext, bewerte_alle, index_aufbauen
    chor = _chorplan_historien_test()
    slot, quelle = _liedslot_und_quelle()
    historie = [Historieneintrag(datum=date(2026, 12, 13), plantyp='chorplan',
                                feld_pfad='lieder[0]', wert='l1', plan='FREMD')]
    k = Kontext(chor, Termin(date(2026, 12, 6), 'standard'), quelle, {}, [], historie)
    index_aufbauen(k)
    regel = next(r for r in chor['regeln'] if r['baustein'] == 'mindestabstand')
    assert not bewerte_alle('l1', slot, k, [regel]).meldungen


def test_archivierter_plan_zaehlt_weiter_als_generator_historie(client, patched_db):
    from diakronos_app.models.planrahmen import Eintrag
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle
    stammdaten(patched_db, 'planer', 'mitglied')
    anmelden(client, 'planer')
    aufruf(client, 'plantyp_speichern', definition=_progdefinition(), gueltig_ab='2026-01-01')
    p = aufruf(client, 'plan_anlegen', plantyp='prog-p114b', titel='Plan',
               von='2026-12-01', bis='2026-12-31', parameter={'uhrzeit': '17:00'})['id']
    termin = aufruf(client, 'plan_holen', plan=p)['termine'][0]['id']
    with patched_db.begin() as s:
        s.add(Eintrag(id='HISTORIE', termin=termin, feld_pfad='ablauf/0.lied', wert='Lied', quelle='manuell'))
    aufruf(client, 'veroeffentlichen', plan=p)
    aufruf(client, 'plan_archivieren', plan=p)
    with patched_db() as s:
        quelle = DBDatenquelle(s)
        assert any(h.plan == p and h.wert == 'Lied' for h in quelle.historie('*', date(2027, 1, 1)))
