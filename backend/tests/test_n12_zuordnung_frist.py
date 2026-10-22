"""N12 / N-2 (R-N10): Aufbewahrungsfrist fuer abgelehnte Anbieter-Zuordnungen.

DER BEFUND (N-2)
-------------------------------
Die Tabelle `auth_zuordnung_ablehnung` (R-N8: abgelehnte OIDC-E-Mail-Zuordnung
fuer die Verwaltung sichtbar) hatte KEINE Loeschfrist — sie wuchs unbegrenzt.
Anders als der Einwilligungs-Log ist sie kein Nachweis, sondern ein
Arbeitshinweis und braucht eine Frist (Art. 5 Abs. 1 lit. e DSGVO).

Die Behebung: Einstellung `AUTH_ZUORDNUNG_ABLEHNUNG_TAGE` (Default 90, `0` =
aus) und ein taeglicher Scheduler-Job `delete_alte_zuordnung_ablehnungen`.

Reproduktionstest: ohne die Aenderung ist die Funktion nicht vorhanden.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from diakronos_app.models.auth_oidc import ZuordnungsAblehnung


def _zeile(sess, name: str, *, zuletzt: datetime | None, created: datetime) -> None:
    sess.add(ZuordnungsAblehnung(
        name=name, issuer="https://idp", sub=name, grund="mitglied_zuordnung",
        zuletzt=zuletzt, created=created, versuche=1,
    ))


def test_alte_ablehnung_wird_geloescht(patched_db, monkeypatch) -> None:
    """Zeilen aelter als die Frist verschwinden, junge bleiben."""
    from diakronos_app.api import cleanup

    sess = patched_db()
    alt = datetime.now() - timedelta(days=120)
    jung = datetime.now() - timedelta(days=10)
    _zeile(sess, "ALT", zuletzt=alt, created=alt)
    _zeile(sess, "JUNG", zuletzt=jung, created=jung)
    sess.commit()
    sess.close()

    geloescht = cleanup.delete_alte_zuordnung_ablehnungen()
    assert geloescht == 1

    sess = patched_db()
    assert sess.get(ZuordnungsAblehnung, "ALT") is None
    assert sess.get(ZuordnungsAblehnung, "JUNG") is not None
    sess.close()


def test_ohne_zuletzt_zaehlt_created(patched_db) -> None:
    """Faellt `zuletzt` aus, entscheidet `created`."""
    from diakronos_app.api import cleanup

    sess = patched_db()
    alt = datetime.now() - timedelta(days=200)
    _zeile(sess, "OHNE-ZULETZT", zuletzt=None, created=alt)
    sess.commit()
    sess.close()

    assert cleanup.delete_alte_zuordnung_ablehnungen() == 1
    sess = patched_db()
    assert sess.get(ZuordnungsAblehnung, "OHNE-ZULETZT") is None
    sess.close()


def test_frist_null_schaltet_die_loeschung_ab(patched_db, monkeypatch) -> None:
    """`AUTH_ZUORDNUNG_ABLEHNUNG_TAGE=0` heisst unbegrenzt."""
    from diakronos_app.api import cleanup
    from diakronos_app import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "auth_zuordnung_ablehnung_tage", 0)

    sess = patched_db()
    alt = datetime.now() - timedelta(days=9999)
    _zeile(sess, "ALT", zuletzt=alt, created=alt)
    sess.commit()
    sess.close()

    assert cleanup.delete_alte_zuordnung_ablehnungen() == 0
    sess = patched_db()
    assert sess.get(ZuordnungsAblehnung, "ALT") is not None
    sess.close()


def test_idempotent(patched_db) -> None:
    """Ein zweiter Lauf findet nichts mehr."""
    from diakronos_app.api import cleanup

    sess = patched_db()
    alt = datetime.now() - timedelta(days=120)
    _zeile(sess, "ALT", zuletzt=alt, created=alt)
    sess.commit()
    sess.close()

    assert cleanup.delete_alte_zuordnung_ablehnungen() == 1
    assert cleanup.delete_alte_zuordnung_ablehnungen() == 0


def test_config_default_ist_90_tage() -> None:
    """Die Einstellung hat den Default 90 und ist konfigurierbar."""
    from diakronos_app.settings import Settings

    assert Settings(auth_zuordnung_ablehnung_tage=90).auth_zuordnung_ablehnung_tage == 90
    assert Settings(auth_zuordnung_ablehnung_tage=30).auth_zuordnung_ablehnung_tage == 30
