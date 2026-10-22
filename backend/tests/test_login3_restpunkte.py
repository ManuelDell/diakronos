"""LOGIN-3 / N-2 und N-3 — Kommentar zur Bremse und toter `hinweis_block`.

N-2 (Befund R-LOGIN-2): Der Kommentar an der Herkunftspruefung in
`api/auth.py` behauptete, die Bremse habe „oben schon gezaehlt" und die
Ablehnung sei deshalb kein Fehlversuch. Das stimmt nicht: `pruefe_und_merke`
laeuft NACH der Herkunftspruefung. Eine abgewiesene Herkunft zaehlt also gar
nicht — und das ist auch richtig so (ein fremder Origin ist ein Hinweis auf
einen Angreifer, nicht auf einen vertippten Menschen; ihn mitzuzaehlen wuerde
den IP-Zaehler mit Angriffsverkehr fluten und damit den Kontoschutz
aushebeln). Der Kommentar muss den Code beschreiben, nicht eine Absicht.

N-3: `hinweis_block` in `anmeldung/routen.py` ist toter Code. Die Bedingung
`not lokal and not oidc_an` kann nie wahr werden:

  * `_lokales_login_erlaubt()` gibt `True` zurueck, sobald OIDC aus ist
    (`if not konf.oidc_aktiv(): return True`) — bei `not oidc_an` ist `lokal`
    also immer True.
  * Bei aktivem OIDC ist `lokal` genau dann False, wenn `AUTH_LOCAL_LOGIN=aus`;
    dann ist aber `oidc_an` True.

Der Block hat also seit LOGIN-2 nie etwas gerendert. Er wird ENTFERNT (nicht
„sichtbar gemacht"): die Aussage, die er treffen wollte, ist bereits an der
Stelle, an der sie hingehoert — `api/auth.py::_lokaler_login_erlaubt` sperrt
Konten ohne Anbieter nicht aus, und der Docstring der Anmeldeseite nennt das
ausdruecklich (Bestandsschutz). Eine zusaetzliche Meldung „Anmeldung
ausgeschaltet, kein Dienst eingerichtet" waere damit eine Aussage ueber einen
Zustand, den es nicht gibt.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _quelle(relativ: str) -> str:
    """Quelltext einer Datei des Pakets (kein Import, keine Seiteneffekte)."""
    pfad = Path(__file__).resolve().parents[1] / "src" / "diakronos_app" / relativ
    return pfad.read_text(encoding="utf-8")


# ── N-2: Der Kommentar beschreibt den Code ────────────────────────────────


def test_kommentar_sagt_nicht_dass_die_bremse_schon_gezaehlt_hat():
    """Die Behauptung „sie hat oben schon gezaehlt" ist falsch — sie raus.

    Geprueft am Quelltext, weil es eine Aussage UEBER den Code ist: der
    Ablauf ist Herkunftspruefung -> `pruefe_und_merke` -> Passwort.
    """
    quelle = _quelle("api/auth.py")
    assert "schon gezaehlt" not in quelle
    assert "hat oben bereits gezaehlt" not in quelle


def test_herkunftspruefung_steht_vor_der_bremse():
    """Beleg fuer die Aussage im Kommentar: Reihenfolge im Quelltext.

    `_herkunft_ist_eigen` MUSS vor `pruefe_und_merke` stehen — sonst waere
    ein abgewiesener fremder Origin ein gezaehlter Fehlversuch und der
    IP-Zaehler mit Angriffsverkehr flutbar.
    """
    quelle = _quelle("api/auth.py")
    pos_herkunft = quelle.index("if request is not None and not _herkunft_ist_eigen(request):")
    pos_bremse = quelle.index("loginversuche.pruefe_und_merke(")
    assert pos_herkunft < pos_bremse


# ── N-3: kein toter Block mehr in der Anmeldeseite ────────────────────────


def test_anmeldeseite_hat_keinen_toten_hinweis_block():
    quelle = _quelle("anmeldung/routen.py")
    # Nur Code/HTML pruefen, nicht die Kommentare (die den Befund erklaeren).
    code = "\n".join(z for z in quelle.splitlines() if not z.lstrip().startswith("#"))
    assert "hinweis_block" not in code, (
        "`hinweis_block` ist toter Code (Bedingung nie wahr) — er gehoert entfernt, "
        "nicht sichtbar gemacht (Begruendung im Modulkopf von test_login3_restpunkte.py)"
    )


def test_anmeldeseite_zeigt_bei_aktivem_oidc_weiter_den_anbieter_knopf():
    """Was der Block haette leisten sollen, leistet der Anbieter-Knopf."""
    quelle = _quelle("anmeldung/routen.py")
    assert "sso_block" in quelle
    assert "_anbieter_knopf_html()" in quelle


@pytest.mark.parametrize("zustand", ["aus", "nur-admin", "an"])
def test_lokales_login_ohne_anbieter_bleibt_immer_erlaubt(monkeypatch, zustand):
    """Der Zustand, den der tote Block beschreiben wollte, existiert nicht.

    Ohne OIDC ist `_lokales_login_erlaubt()` immer True — unabhaengig von
    `AUTH_LOCAL_LOGIN`. Damit ist `not lokal and not oidc_an` unerreichbar.
    """
    from diakronos_app.anmeldung import konfiguration as konf
    from diakronos_app.anmeldung import routen

    monkeypatch.setattr(konf, "oidc_aktiv", lambda: False)
    monkeypatch.setattr(konf, "oidc_konfiguration", lambda: type("K", (), {"local_login": zustand})())
    assert routen._lokales_login_erlaubt() is True


def test_anmeldeseite_rendert_ohne_hinweis_aber_mit_formular(monkeypatch):
    """Gerendert: kein toter Hinweis, dafuer das Passwortformular."""
    from diakronos_app.anmeldung import konfiguration as konf
    from diakronos_app.anmeldung import routen

    monkeypatch.setattr(konf, "oidc_aktiv", lambda: False)
    seite = routen.erstelle_anmeldeseite(request=None)

    assert "dk-hinweis-block" not in seite
    # Der feste Fliesstext unten nennt die Gemeindeleitung weiterhin — nur die
    # Aussage „Anmeldung abgeschaltet, kein Dienst eingerichtet" darf fehlen.
    assert "ausgeschaltet" not in seite
    assert 'action="/api/method/login"' in seite
