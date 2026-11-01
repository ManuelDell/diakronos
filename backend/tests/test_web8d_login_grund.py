"""WEB-8d (N7) — Anmeldeseite zeigt nur FESTE Hinweise zu `?grund=…`.

BEFUND (Opus-Review zu WEB-8c R4): Der Client meldet ein Sitzungsende über die
feste Kennung `?grund=csrf`; die Maske bildet sie über `GRUND_HINWEISE` auf
einen festen Satz ab. Ein Pytest dafür fehlte — also war nicht belegt, dass

  * `grund=csrf` den festen Text zeigt,
  * ein FREMDER Wert (`grund=<script>alert(1)</script>`, ein Satz, eine
    erfundene Kennung) NICHTS zeigt und NICHTS übernimmt (kein Freitext aus
    der Adresse → keine Einschleusung, kein „Reflected XSS“),

mit UND ohne Betriebs-Präfix (`DIAKRONOS_BASE_PATH`).
"""

from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from diakronos_app import base_path
from diakronos_app.main import erstelle_app
from diakronos_app.settings import settings as echte_settings

PRAEFIX = "/diakronos"

#: Der feste Satz zu `grund=csrf` — textgleich mit `SITZUNG_HINWEIS` in
#: `frontend/src/shared/csrf-heilung.js`.
CSRF_HINWEIS = "Sitzung abgelaufen — bitte neu anmelden."

_BROWSER = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@pytest.fixture(params=["", PRAEFIX])
def praefix(request, monkeypatch):
    """Anmeldeseite MIT und OHNE Betriebs-Präfix (danach zurücksetzen)."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", request.param)
    base_path.setze_praefix(request.param)
    try:
        yield request.param
    finally:
        base_path.setze_praefix("")


def _seite(praefix: str, **parameter) -> str:
    """HTML der Anmeldeseite mit den übergebenen Query-Parametern."""
    with TestClient(erstelle_app()) as client:
        antwort = client.get(
            f"{praefix}/login",
            params=parameter,
            headers=_BROWSER,
            follow_redirects=False,
        )
    assert antwort.status_code == 200, antwort.text[:300]
    return antwort.text


def _sichtbarer_text(seite: str) -> str:
    """Fließtext der Seite (Tags entfernt, Entities aufgelöst)."""
    ohne_skript = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", seite, flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", ohne_skript))


# ── grund=csrf -> fester Text ─────────────────────────────────────────────


def test_grund_csrf_zeigt_den_festen_hinweis(praefix):
    """Die feste Kennung `csrf` erscheint als fester Satz auf der Maske."""
    seite = _seite(praefix, grund="csrf")
    assert CSRF_HINWEIS in _sichtbarer_text(seite), (
        f"grund=csrf ohne Hinweis (Präfix {praefix!r})"
    )


def test_ohne_grund_kein_hinweis(praefix):
    """Ohne `grund` bleibt die Maske ohne Sitzungshinweis."""
    seite = _seite(praefix)
    assert CSRF_HINWEIS not in _sichtbarer_text(seite)


# ── fremder/erfundener Grund -> NICHTS ────────────────────────────────────


@pytest.mark.parametrize(
    "grund",
    [
        "<script>alert(1)</script>",
        "<EM>kaputt</EM>",
        "Sitzung abgelaufen",
        "gibtsnicht",
        "csrf2",
        "CSRF ",
        "{{ 7 * 7 }}",
        "grund=csrf",
    ],
)
def test_unbekannter_grund_zeigt_nichts(praefix, grund):
    """Nur die feste Kennung `csrf` zählt. Jeder andere Wert wird verworfen —
    er darf weder als Hinweis erscheinen noch ungefiltert in die Seite.
    """
    seite = _seite(praefix, grund=grund)
    text = _sichtbarer_text(seite)

    assert CSRF_HINWEIS not in text, f"fremder Grund {grund!r} zeigt den CSRF-Hinweis"
    # Der Rohwert darf nicht im HINWEISBEREICH auftauchen. (`"0"` steht
    # zwangsläufig irgendwo im Seitenquelltext — deshalb gezielt der Bereich,
    # in dem ein Hinweis stehen dürfte.)
    assert grund not in _hinweisbereich(seite), (
        f"fremder Grund {grund!r} steht im Hinweisbereich der Seite"
    )
    if "<" in grund:
        # Ein durchgereichtes Markup wäre als TAG sichtbar. Geprüft wird nur
        # der Hinweisbereich der Maske (die Seite selbst enthält echtes
        # `<script>` — das ist kein Beleg für Einschleusung).
        assert grund not in _sichtbarer_text(_hinweisbereich(seite))
        assert f"<{grund.strip('<>').split('>')[0].lower()}" not in _hinweisbereich(seite).lower()

    # Gegenprobe: es ist weiterhin die echte Anmeldemaske.
    assert "name=\"pwd\"" in seite or "type=\"password\"" in seite


def _hinweisbereich(seite: str) -> str:
    """Der obere Teil der Maske (dort steht der Hinweis) — ohne Seitenkopf."""
    # `erstelle_anmeldeseite` setzt den Hinweis vor das Formular; alles bis
    # zum Formularbeginn ist der Bereich, in dem ein Hinweis stehen dürfte.
    # ON-0a: der Seitenkopf traegt ein eigenes Theme-Skript — erst ab <body>.
    anfang = max(seite.find("<body"), 0)
    stelle = seite.find("<form", anfang)
    return seite[anfang:stelle] if stelle > 0 else seite[anfang:]


def test_html_sonderzeichen_werden_nie_als_markup_ausgegeben(praefix):
    """Selbst wenn ein Wert durchkäme, bliebe er Text: kein `<script>`-Tag."""
    seite = _seite(praefix, grund="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in seite


# ── der Hinweis kommt aus EINER Tabelle (kein Freitext) ───────────────────


def test_grund_hinweis_ist_eine_allowlist():
    """`grund_hinweis` liefert nur für bekannte Kennungen einen Satz."""
    from diakronos_app.anmeldung.routen import GRUND_HINWEISE, grund_hinweis

    assert grund_hinweis("csrf") == CSRF_HINWEIS
    for fremd in ("", None, "csrf ", "<b>", "Sitzung abgelaufen", "x"):
        if fremd is None or str(fremd).strip() in GRUND_HINWEISE:
            continue
        assert grund_hinweis(fremd) == "", f"{fremd!r} liefert einen Hinweis"
    # Der Text ist FEST — er trägt keine Adresse, keinen Nutzernamen, nichts.
    assert "%" not in CSRF_HINWEIS and "{{" not in CSRF_HINWEIS
