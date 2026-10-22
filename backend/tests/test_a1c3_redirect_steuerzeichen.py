"""A1c3, Punkt 2: `_redirect_ziel()` muss Steuerzeichen aus `redirect-to` werfen.

Warum das mehr ist als Kosmetik (Karte A1c3, Notiz 2): `_redirect_ziel()` ist
die **einzige** Stelle, die `redirect-to` nach dem Formular-Login prueft. Der
ASGI-Server weist CR/LF in Kopfzeilen heute zurueck — darauf zu vertrauen ist
aber eine Zusage ueber den Codebestand hinaus: sobald eine zweite
Auth-Implementierung die Funktion erbt, ist dieser Schutz weg und ein
`Location`-Header mit eingebautem Zeilenumbruch steht im Raum (Response
Splitting, Cache-Poisoning, je nach Proxy ein Header-Smuggling-Vektor).

Deshalb wird **vor** dem Bauen des Redirects gefiltert, nicht danach.

Gemessen am alten Stand: jeder der folgenden Faelle liefert den
Steuerzeichen-Zielpfad unveraendert zurueck (`\r\n` im `Location`-Header,
`\x00` mitten im Pfad). Der Test unten faellt deshalb am alten Code um.
"""

from __future__ import annotations

from urllib.parse import unquote

import pytest

from diakronos_app.api.auth import SPA_ZIEL, _redirect_ziel


# ── Fall 1: die Steuerzeichen selbst (kern der Karte) ───────────────────────
#
# Werte als Python-Literale, weil `_redirect_ziel` den Kandidaten selbst
# `unquote()`t: was der Browser sendet, ist die **unkodierte** Zeile. Fuer den
# kodierten Weg siehe die zweite Gruppe.
_STEUERZEICHEN_FAELLE = [
    pytest.param("\r", id="CR"),
    pytest.param("\n", id="LF"),
    pytest.param("\r\n", id="CRLF"),
    pytest.param("\x00", id="NUL"),
    pytest.param("\t", id="TAB"),
    pytest.param("\x0b", id="VT"),
    pytest.param("\x0c", id="FF"),
    pytest.param("\x1b", id="ESC"),
    pytest.param("\x7f", id="DEL"),
    # Ueber dem C0-Bereich, aber genauso unsichtbar in einem Kopfzeilenwert.
    pytest.param("\u0085", id="NEL"),
    pytest.param("\u2028", id="LINE-SEP"),
    pytest.param("\u2029", id="PARA-SEP"),
]


_VERBOTEN = "\r\n\x00\t\x0b\x0c\x1b\x7f\u0085\u2028\u2029"


def _steuerzeichen_drin(ziel: str) -> list[str]:
    """Welche Steuerzeichen stehen noch im Ziel? (leer = sauber)"""
    return [c for c in ziel if c in _VERBOTEN]


@pytest.mark.parametrize("zeichen", _STEUERZEICHEN_FAELLE)
def test_steuerzeichen_im_ziel_verlassen_keine_anfrage(zeichen: str) -> None:
    """Kein Steuerzeichen verlaesst `_redirect_ziel` — in keiner Zulausform.

    Geprueft wird in zwei Formen, weil ein Angriffsversuch nicht weiss, ob der
    vorgeschaltete Proxy Prozentzeichen dekodiert oder nicht:
      * `"/mitglieder" + z` — das Zeichen **unkodiert**, mitten im Pfad
      * `"/mitglieder%" + hex(z)` — der **kodierte** Weg (die Funktion macht
        selbst `unquote()`)

    Die Erwartung ist bewusst NICHT ueberall `SPA_ZIEL`. `_redirect_ziel`
    macht seit jeher `.strip()`, und `str.strip()` entfernt fuehrende und
    **angehaengte** Leerzeichen einschliesslich `\\r`, `\\n` und `\\t`:
    `"/mitglieder\\r"` wird dadurch zu dem völlig unbedenklichen
    `/mitglieder`. Das ist kein Fehler, sondern das gewuenschte Ergebnis — der
    Fall ist damit harmlos, und ein Test, der hier `SPA_ZIEL` verlangt,
    wuerde eine Verschärfung erzwingen, die es nicht braucht.

    Die Karte will genau eine Zusage: **kein Steuerzeichen verlaesst die
    Funktion**. Deshalb wird das geprueft, und zusaetzlich die Reaktion:
    was zurueckkommt, ist entweder der bereinigte Pfad oder `SPA_ZIEL` —
    beides zulaessig, ein fremder Pfad oder ein weitergereichtes Steuerzeichen
    nicht.
    """
    # Jedes Zeichen einzeln kodieren: bei CRLF ist `f"%{ord(z):02x}"` falsch,
    # das ergaebe die Zahl von "CR" (0x0d0a) statt zweier Bytes.
    kodiert = "".join(f"%{ord(c):02x}" for c in zeichen)

    for kandidat in (f"/mitglieder{zeichen}", f"/mitglieder{kodiert}"):
        ziel = _redirect_ziel(kandidat)

        # 1. Das Kernversprechen: das Zeichen ist nicht mehr da.
        assert not _steuerzeichen_drin(ziel), (
            f"Steuerzeichen {zeichen!r} (0x{ord(zeichen):02x}) durchgelassen: "
            f"{kandidat!r} -> {ziel!r}"
        )
        # 2. Was zurueckkommt, ist ein lokaler Pfad oder der Fallback.
        assert ziel == SPA_ZIEL or ziel.startswith("/"), f"{kandidat!r} -> {ziel!r}"
        assert not ziel.startswith("//") and "\\" not in ziel


@pytest.mark.parametrize("zeichen", _STEUERZEICHEN_FAELLE)
def test_angehaengte_steuerzeichen_werden_nicht_durchgereicht(zeichen: str) -> None:
    """Der harte Fall: das Zeichen steckt **mitten** im Pfad.

    Hier hilft kein `.strip()` mehr, weil der Rest des Pfads stehen bleibt.
    Genau dieser Fall landete am alten Code unveraendert im `Location`-Header
    (`/mitglieder%0d%0aSet-Cookie: …` ist pfadrelativ, hat kein `//` und
    keinen `\` — nur die Header-Injektion faellt auf) und MUSS auf `SPA_ZIEL`
    gehen. Das ist der Test, der am alten Code umfaellt.
    """
    ziel = _redirect_ziel(f"/mitglieder/{zeichen}Set-Cookie: sid=gestohlen")
    assert ziel == SPA_ZIEL, f"Steuerzeichen mitten im Pfad: -> {ziel!r}"

    # Und die Form ohne fuehrenden Slash-Zwischenstueck: der Zeilenumbruch
    # direkt hinter dem Pfadpraefix, danach ein Header-Name.
    ziel = _redirect_ziel(f"/mitglieder{zeichen}Set-Cookie: sid=gestohlen")
    assert not _steuerzeichen_drin(ziel)


# ── Fall 2: was weiterhin funktionieren MUSS (Gegenrichtung) ────────────────
#
# Ein Filter, der alles zurueckwirft, waere ebenfalls "gruen". Diese Faelle
# sichern die Reaktion: geprueft wird an der **unveraenderten** Nutzlast, an
# gueltigen Pfaden, die kein Steuerzeichen enthalten.


@pytest.mark.parametrize(
    "gut",
    [
        "/diakonos",
        "/diakonos/mitglieder",
        "/mitglieder?email=anna%40example.org",
        "/mitglieder/M-0001",
        "/mitglieder/M-0001?x=1&y=2#anker",
        "/diakonos%20mitglieder",
    ],
)
def test_gueltige_ziele_bleiben_unveraendert(gut: str) -> None:
    """Kein Leer-Nein: gueltige lokale Ziele kommen an.

    Erwartet wird bewusst der **dekodierte** Pfad: `_redirect_ziel` macht
    seit jeher `unquote()` (damit `%2f%2fevil.de` nicht durchrutscht), also
    steht im `Location` die dekodierte Fassung. Das ist bestehendes Verhalten
    und wird hier festgeschrieben, nicht geaendert — `%20` ist dabei der
    Beweis, dass der neue Steuerzeichen-Filter nicht alles pauschal ablehnt,
    denn Space ist kein Steuerzeichen.
    """
    erwartet = unquote(gut)
    assert _redirect_ziel(gut) == erwartet
    assert not _steuerzeichen_drin(erwartet)
    # Und weiterhin ein lokaler Pfad ohne Backslash.
    assert erwartet.startswith("/") and not erwartet.startswith("//")
    assert "\\" not in erwartet


# ── Fall 3: die Altfaelle duerfen nicht kaputtgehen ────────────────────────
#
# Der bestehende Parameterblock in `test_a1b2_rest_boot_login.py` deckt die
# offene Weiterleitung auf HTTP-Ebene ab. Diese Liste haelt die Reinheit der
# Funktion auch ohne HTTP-Roundtrip fest.


@pytest.mark.parametrize(
    "bose",
    [
        "https://evil.example.net",
        "//evil.example.net",
        "\\\\evil.example.net",
        "/\\evil.example.net",
        "javascript:alert(1)",
        "",
        None,
        "   ",
    ],
)
def test_offene_und_leere_ziele_fallen_auf_spa_zurueck(bose) -> None:
    """Unveraendertes Verhalten der Altfaelle (Regression der Korrektheit)."""
    assert _redirect_ziel(bose) == SPA_ZIEL


def test_kein_steuerzeichen_erreicht_den_location_header() -> None:
    """Gegenprobe am echten Objekt: `Location` traegt kein Steuerzeichen.

    `RedirectResponse` schreibt den Wert **unveraendert** in den Header — der
    Header-Validator des ASGI-Servers ist also die einzige Verteidigung, und
    genau darauf soll sich der Code nicht verlassen. Der Test baut die
    Antwort wie in `login()` und liest sie wie ein Client.
    """
    from starlette.responses import RedirectResponse

    for kandidat in (
        "/mitglieder\r\nSet-Cookie: sid=gestohlen",
        "/mitglieder%0d%0aSet-Cookie: sid=gestohlen",
        "/mitglieder\x00/admin",
        "/mitglieder\nX-Injected: 1",
    ):
        antwort = RedirectResponse(_redirect_ziel(kandidat), status_code=303)
        location = antwort.headers["location"]
        assert location == SPA_ZIEL, f"{kandidat!r} -> Location: {location!r}"
        for c in "\r\n\x00\t":
            assert c not in location, f"{c!r} im Location-Header: {location!r}"
