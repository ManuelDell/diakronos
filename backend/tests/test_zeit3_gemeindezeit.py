"""ZEIT-3: „Heute“ ist der Kalendertag in ``CALENDAR_TIMEZONE`` (nicht UTC).

Der Container laeuft in UTC. Zwischen 0 und 2 Uhr Ortszeit liefert
``date.today()`` deshalb den VORTAG. Die Tests nageln genau dieses Fenster
fest: 23:30 UTC am 09.11. ist in Berlin schon der 10.11.
"""

from datetime import date, datetime, timezone

import pytest

from diakronos_app import zeit
from diakronos_app.settings import settings


class _FesteUhr:
    """Ersatz fuer ``datetime.datetime`` in ``diakronos_app.zeit``.

    Gefroren wird nur ``now()`` — wie bei ``freezegun``. Die Klasse wird als
    ``zeit._dt.datetime`` gesetzt; ``isinstance``-Pruefungen im Testcode
    laufen weiter gegen das echte ``datetime``.
    """

    def __init__(self, fest: datetime):
        self.fest = fest

    def now(self, tz=None):
        return self.fest if tz is None else self.fest.astimezone(tz)


@pytest.fixture
def berlin(monkeypatch):
    monkeypatch.setattr(settings, "calendar_timezone", "Europe/Berlin", raising=False)
    return settings


def _friere(monkeypatch, iso_utc: str):
    fest = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
    monkeypatch.setattr(zeit._dt, "datetime", _FesteUhr(fest))
    return fest


def test_heute_ist_in_der_nacht_schon_der_naechste_tag(berlin, monkeypatch):
    """23:30 UTC = 00:30 Berlin -> „heute“ ist der 10.11., nicht der 09.11."""
    _friere(monkeypatch, "2026-11-09T23:30:00")
    assert zeit.heute_gemeinde() == date(2026, 11, 10)
    assert zeit.heute_iso() == "2026-11-10"
    # Gegenprobe: genau das liefert der Container (UTC) — und ist falsch.
    assert date(2026, 11, 9) != zeit.heute_gemeinde()


def test_heute_vor_mitternacht_utc_ist_noch_der_gleiche_tag(berlin, monkeypatch):
    """22:00 UTC = 23:00 Berlin -> derselbe Kalendertag."""
    _friere(monkeypatch, "2026-11-09T22:00:00")
    assert zeit.heute_gemeinde() == date(2026, 11, 9)


def test_heute_folgt_der_eingestellten_zeitzone(monkeypatch):
    """Eine Gemeinde in einer anderen Zone bekommt ihren eigenen Tag."""
    monkeypatch.setattr(settings, "calendar_timezone", "Pacific/Kiritimati", raising=False)
    _friere(monkeypatch, "2026-11-09T12:00:00")  # UTC+14 -> 10.11., 02:00
    assert zeit.heute_gemeinde() == date(2026, 11, 10)


def test_kaputte_zeitzone_faellt_auf_utc_zurueck(monkeypatch):
    """Eine unbrauchbare Einstellung darf keinen Endpunkt toeten."""
    monkeypatch.setattr(settings, "calendar_timezone", "Nirgendwo/Atlantis", raising=False)
    _friere(monkeypatch, "2026-11-09T23:30:00")
    assert zeit.zeitzone().key == "UTC"
    assert zeit.heute_gemeinde() == date(2026, 11, 9)


def test_jetzt_gemeinde_traegt_die_zeitzone(berlin, monkeypatch):
    _friere(monkeypatch, "2026-11-09T23:30:00")
    jetzt = zeit.jetzt_gemeinde()
    assert jetzt.tzinfo is not None
    assert jetzt.utcoffset().total_seconds() == 3600  # MEZ im November


def test_zeit_text_rechnet_utc_zeitstempel_um(berlin):
    """Anzeige technischer Zeitstempel: UTC gespeichert, Ortszeit gezeigt."""
    assert zeit.zeit_text("2026-11-09 23:30:00") == "2026-11-10 00:30"
    assert zeit.zeit_text("2026-11-09T23:30:00") == "2026-11-10 00:30"
    assert zeit.zeit_text("2026-11-09T23:30:00Z") == "2026-11-10 00:30"
    assert zeit.zeit_text(datetime(2026, 11, 9, 22, 15)) == "2026-11-09 23:15"


def test_zeit_text_verschiebt_reine_datumsangaben_nicht(berlin):
    """``date``/``"JJJJ-MM-TT"`` tragen keine Uhrzeit — nichts umzurechnen."""
    assert zeit.zeit_text("2026-11-09") == "2026-11-09"
    assert zeit.zeit_text(date(2026, 11, 9)) == "2026-11-09"


def test_zeit_text_leer_und_unlesbar(berlin):
    assert zeit.zeit_text(None) is None
    assert zeit.zeit_text("") is None
    assert zeit.zeit_text("keine Zeit") == "keine Zeit"


def test_zeit_text_mit_sekunden(berlin):
    assert zeit.zeit_text("2026-11-09 23:30:45", mit_sekunden=True) == "2026-11-10 00:30:45"


# ── Stichproben der umgestellten Stellen ───────────────────────────────────


def test_admin_hub_erster_des_monats_nutzt_die_gemeindezeit(berlin, monkeypatch):
    """Monatsanfang „1. des Monats“ darf nicht vom UTC-Vortag abhaengen."""
    from diakronos_app.api import admin_hub

    _friere(monkeypatch, "2026-11-30T23:30:00")  # Berlin: 01.12. 00:30
    assert admin_hub._erster_des_monats() == "2026-12-01"


def test_frappe_today_nutzt_die_gemeindezeit(berlin, monkeypatch):
    """``frappe.utils.today()`` — die Compat-Naht aller Portierungen."""
    from diakronos_app.frappe_compat import api_helpers

    _friere(monkeypatch, "2026-11-09T23:30:00")
    assert api_helpers._today() == "2026-11-10"


def test_gruppen_today_nutzt_die_gemeindezeit(berlin, monkeypatch):
    from diakronos_app.api import gruppen

    _friere(monkeypatch, "2026-11-09T23:30:00")
    assert gruppen._today() == "2026-11-10"


def test_wiki_updated_at_ist_ein_zeitpunkt_der_gemeinde(berlin, monkeypatch):
    """Wiki „Zuletzt bearbeitet“ kam als ``str(modified)[:10]`` (UTC-Datum)."""
    from diakronos_app.api import wiki

    _friere(monkeypatch, "2026-11-10T00:30:00")  # Berlin 01:30 -> 10.11.
    artikel = {
        "name": "A", "titel": "T", "auszug": "", "kategorie": "technik", "tags": "",
        "autor": "X", "modified": datetime(2026, 11, 9, 23, 30), "ist_neu": 0,
    }
    assert wiki._artikel_to_dict(artikel)["updatedAt"] == "2026-11-10"


def test_sicherung_zeitpunkt_laeuft_in_ortszeit(berlin, monkeypatch):
    """Der Sicherungszeitpunkt (Name/Beginn) ist Ortszeit — der Merker auch."""
    from diakronos_app.api import sicherung
    from diakronos_app.sicherung import dump

    _friere(monkeypatch, "2026-11-09T23:30:00")  # Berlin: 10.11., 00:30
    assert dump.jetzt_ortszeit() == datetime(2026, 11, 10, 0, 30)
    assert sicherung._jetzt() == datetime(2026, 11, 10, 0, 30)


def test_sicherung_faellig_vergleicht_mit_ortszeit(berlin, monkeypatch):
    """03:00 eingestellt heisst 03:00 Ortszeit — nicht 03:00 UTC (05:00)."""
    import diakronos_app.scheduler as scheduler
    from diakronos_app.sicherung import einstellungen as einstellungen_modul

    monkeypatch.setattr(scheduler, "_merker_client", lambda: _Merker(None))
    # 02:30 UTC = 03:30 Berlin -> faellig; in UTC waere es 02:30 < 03:00.
    monkeypatch.setattr(scheduler, "_jetzt_ortszeit", _ortszeit_0330)
    monkeypatch.setattr(
        einstellungen_modul, "holen_oder_anlegen",
        lambda sess, jetzt=None, benutzer=None: _EinfachZeile(
            automatisch=True, uhrzeit="03:00", aufbewahrung_tage=30),
    )
    # 03:30 Ortszeit >= 03:00 -> faellig. Mit UTC waere es 02:30 < 03:00,
    # die Sicherung liefe also erst um 05:00 Ortszeit.
    assert scheduler.sicherung_faellig() is True


def _ortszeit_0330():
    """Ortszeit 03:30 am 10.11. (in UTC noch der 10.11., 02:30)."""
    return datetime(2026, 11, 10, 3, 30)


class _Merker:
    """Redis-Merker der Sicherung: ``get`` liefert den gespeicherten Tag."""

    def __init__(self, wert):
        self.wert = wert

    def get(self, schluessel):
        return self.wert

    def set(self, schluessel, wert, ex=None):
        self.wert = wert


class _EinfachZeile:
    """Zeilen-Attrappe der Sicherungseinstellungen."""

    def __init__(self, **werte):
        self.__dict__.update(werte)


# ── Review-Kleinfix ────────────────────────────────────────────────────────


def test_sommerzeit_heute_und_wanduhr(berlin, monkeypatch):
    """MESZ (+2): 22:30 UTC am 01.07. ist in Berlin 00:30 am 02.07."""
    _friere(monkeypatch, "2026-07-01T22:30:00")
    assert zeit.heute_gemeinde() == date(2026, 7, 2)
    assert zeit.jetzt_wanduhr() == datetime(2026, 7, 2, 0, 30)
    assert zeit.jetzt_wanduhr().tzinfo is None
    # 21:30 UTC = 23:30 MESZ -> noch derselbe Tag.
    _friere(monkeypatch, "2026-07-01T21:30:00")
    assert zeit.heute_gemeinde() == date(2026, 7, 1)


def test_kommende_termine_vergleichen_gegen_die_wanduhr():
    """„ab jetzt“ gegen ``element_start`` (Wandzeit) -> ``jetzt_wanduhr``."""
    import inspect

    from diakronos_app.api import dashboard, planung

    assert "jetzt_wanduhr()" in inspect.getsource(dashboard.get_upcoming_events)
    assert "jetzt_wanduhr()" in inspect.getsource(planung.get_abgeleitete_positionen)


def test_aufbewahrungsfrist_bleibt_utc(berlin, monkeypatch):
    """Fristen gegen UTC-Zeitstempel (``creation``) rechnen im UTC-Tag."""
    from diakronos_app.api import cleanup

    class _Uhr:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 11, 9, 23, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(cleanup, "datetime", _Uhr)
    # Berlin waere schon der 10.11. — die Frist bleibt am UTC-Tag 09.11.
    assert cleanup._cutoff_date() == date(2026, 10, 26)
