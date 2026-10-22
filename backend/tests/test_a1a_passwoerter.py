"""Tests der Passwort-Datenschicht (Karte A1a).

Die Referenz-Hashes sind mit ECHTEM `passlib` verifiziert worden (das Image
hat kein passlib) und hier fest hinterlegt — nicht zur Laufzeit erzeugt.
Bestaetigt: `pbkdf2_sha256.using(rounds=29000, salt=...).hash(...)` erzeugt
denselben String; die Verifikation gegen echte Hashes ist True.

Geprueft wird die FALLE aus der Karte: das passlib-"adapted base64"-Alphabet
ist NICHT vollstaendig permutiert — nur '+' -> '.', Padding entfaellt. Eine
"vollstaendige" Uebersetzungstabelle wuerde das RICHTIGE Passwort ablehnen.
Deshalb ein Referenzhash, dessen angepasstes Base64 ein '.' enthaelt.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat import passwoerter

# Referenzhashes (echtes passlib, Format $pbkdf2-sha256$29000$<salt>$<digest>).
REF_ASCII = "$pbkdf2-sha256$29000$MDEyMzQ1Njc4OWFiY2RlZg$yCYgGEkfzH1mGdCyqZoxo.uJ83VVmN6RoZFHlFhu5Jg"
REF_UMLAUT = "$pbkdf2-sha256$29000$ZmVkY2JhOTg3NjU0MzIxMA$dB01gYvP7dPpkpjSbAXOJqHMQh6GGQDsKyX57iaAnOY"
REF_LEER = "$pbkdf2-sha256$29000$MDAwMDAwMDAwMDAwMDAwMA$4IwECB8CzTzIij1s0ymeMcb8SmattcNelHt1SjIvRf8"
REF_LANG = "$pbkdf2-sha256$29000$YWJjZGVmZ2hpamtsbW5vcA$OOEH4ZGSTMNp5UKpsVRrhx1fSqDi5Bo3RoEYwW2oUbE"


def test_digest_enthaelt_angepasstes_base64_zeichen():
    """Stellt sicher, dass der Testfall die FALLE wirklich trifft.

    Ohne '.' im Digest prueft der Test die Konvention nicht.
    """
    assert "." in REF_ASCII.split("$")[-1]


def test_ascii_richtig_und_falsch():
    assert passwoerter.pruefe_frappe_hash("geheim123", REF_ASCII) is True
    assert passwoerter.pruefe_frappe_hash("geheim124", REF_ASCII) is False
    assert passwoerter.pruefe_frappe_hash("", REF_ASCII) is False


def test_umlaut_und_leerstring():
    assert passwoerter.pruefe_frappe_hash("Grüße-Öl-Ähre-ß", REF_UMLAUT) is True
    assert passwoerter.pruefe_frappe_hash("Gruse-Oel-Aehre-ss", REF_UMLAUT) is False
    # Leerstring als Passwort: der Hash eines Leerstrings ist gueltig.
    assert passwoerter.pruefe_frappe_hash("", REF_LEER) is True
    assert passwoerter.pruefe_frappe_hash("x", REF_LEER) is False


def test_langes_passwort_200_zeichen():
    assert passwoerter.pruefe_frappe_hash("x" * 200, REF_LANG) is True
    assert passwoerter.pruefe_frappe_hash("x" * 199, REF_LANG) is False


def test_kaputter_hash_und_nullartiges():
    assert passwoerter.pruefe_frappe_hash("egal", "nonsense") is False
    assert passwoerter.pruefe_frappe_hash("egal", "$pbkdf2-sha256$29000$a") is False
    assert passwoerter.pruefe_frappe_hash("egal", "") is False
    # Falsches Schema -> abgelehnt, nicht Exception.
    assert passwoerter.pruefe_frappe_hash("egal", "$argon2id$v=19$m=1,t=1,p=1$x$y") is False


def test_argon2_round_trip():
    h = passwoerter.neuer_hash("neuesGeheimnis!42")
    assert h.startswith("$argon2")
    assert passwoerter.pruefe("neuesGeheimnis!42", h) is True
    assert passwoerter.pruefe("falsch", h) is False


def test_pruefe_erkennt_beide_formate_am_praefix():
    # Frappe-Format
    assert passwoerter.pruefe("geheim123", REF_ASCII) is True
    assert passwoerter.pruefe("geheim124", REF_ASCII) is False
    # Argon2-Format
    h = passwoerter.neuer_hash("anders")
    assert passwoerter.pruefe("anders", h) is True
    # Unbekanntes / leeres Format
    assert passwoerter.pruefe("egal", "") is False
    assert passwoerter.pruefe("egal", "$sha1$deadbeef") is False


def test_muss_neu_gehasht_werden():
    assert passwoerter.muss_neu_gehasht_werden(REF_ASCII) is True
    h = passwoerter.neuer_hash("x")
    assert passwoerter.muss_neu_gehasht_werden(h) is False
    assert passwoerter.muss_neu_gehasht_werden("") is False


@pytest.mark.parametrize("hash_str", ["$pbkdf2-sha256$29000$", "$$$$", "abc"])
def test_pruefe_faellt_bei_muell_nicht_um(hash_str):
    assert passwoerter.pruefe("irgendwas", hash_str) is False
