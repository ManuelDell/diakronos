"""DEP-3: Geheimtexte aus der VORIGEN cryptography-Version bleiben lesbar.

WARUM DIESER TEST
-----------------
``cryptography`` wurde von 46.0.7 auf >= 50 angehoben (pip-audit: 7 Meldungen
in 46.0.7, Fixes in 48.0.1/49/50). Im Betrieb liegen verschluesselte Werte in
der Datenbank: das Mailpasswort (``smtp_einstellungen``) und die
Google-Zugangsdaten/Tokens (``google_secrets``). Ein Wechsel der Bibliothek
darf diese Werte NICHT unlesbar machen — der Administrator muesste sonst
Passwort und Google-Freigabe neu einrichten.

Die Geheimtexte unten sind ECHTE Ausgaben, erzeugt mit ``cryptography 46.0.7``
(dem Stand im Betriebs-Image vor dieser Karte), nicht von Hand geschrieben:
das Skript hat mit derselben Schluesselableitung der Module
(SHA-256 ueber ``ABLEITUNGS_KONTEXT + SECRET_KEY``) verschluesselt. Sie sind
damit ein Beleg ueber die Versionsgrenze hinweg — ein selbst erzeugter
Rundlauf (encrypt -> decrypt in derselben Version) wuerde diesen Fall NICHT
abdecken.

Das Klartext-Passwort steht hier absichtlich im Quelltext: es ist ein
Testwert ohne Bezug zu einem echten Postfach, und der Test soll ohne
Datenbank und ohne Netz pruefen, dass die Entschluesselung aufgeht.
"""

from __future__ import annotations

import pytest

#: SECRET_KEY, mit dem die Vektoren verschluesselt wurden (Testwert).
ALTE_VEKTOREN_SECRET = "dep3-testvektor-schluessel-nicht-verwenden"

#: cryptography-Version, mit der die Geheimtexte erzeugt wurden.
ALTE_VEKTOREN_VERSION = "46.0.7"

#: google_secrets: Kontext b"diakronos/google/v1\0" (Modulkonstante, hier
#: nachgebildet, weil der Test die Ableitung selbst nachvollziehen koennen soll).
GOOGLE_TOKEN_DATA = (
    "fernet:v1:"
    "gAAAAABq2yfdBVS45GPZdJh4L0hsCQZ7wqJ_eeMZs3fetkyj89WzxRLBpVI_oj9Awu4m"
    "FmOb9XfaT0LWeffQLjLfaQDYOdFQoFQSDkJMMVd2_FAkkEZdmk1k6yybQZ9hTwylVRct"
    "OmunQpQ-vN84zRtzJSqq9WsoQg=="
)
GOOGLE_TOKEN_DATA_KLARTEXT = '{"access_token":"altes-token","refresh_token":"altes-refresh"}'

GOOGLE_CLIENT_SECRET = (
    "fernet:v1:"
    "gAAAAABq2yfdp5hZ11QHw2Epf9h--cT7cEloGyW4z1LWy3Av4d6VXzH2IucHcEG-1n7P"
    "mqawfx8SnV1b_2tHS4mQbNhE9GvjKX7yLUCAde4POQueyiGopA1FK9AfXcubh9oLEYr2"
    "UgOQ"
)
GOOGLE_CLIENT_SECRET_KLARTEXT = "GOCSPX-alter-client-secret-\u00e4\u00f6\u00fc\u00df"

#: smtp_einstellungen: Kontext b"diakronos/smtp/v1\0".
SMTP_PASSWORT = (
    "fernet:v1:"
    "gAAAAABq2yfdFOlIVUlRQ37vlwotfsfICfZ5vH8HFvtby6F2tefJSvf3eCcL_1-Q2oNL"
    "RZrO7oBKxlvgYahAsJqF-M7XOJLUJdFrdldQ_NCm4nFMoMbXZVpqTHSEdr-2Fayzvjkp"
    "GGGl"
)
SMTP_PASSWORT_KLARTEXT = "Postfach-Passwort-\u00e4\u00f6\u00fc\u00df-2026!"


@pytest.fixture()
def alter_schluessel(monkeypatch):
    """Setzt SECRET_KEY auf den Wert der Vektoren (nur waehrend des Tests)."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "secret_key", ALTE_VEKTOREN_SECRET)


def test_google_geheimtexte_aus_46_0_7_bleiben_lesbar(alter_schluessel):
    from diakronos_app.google_secrets import decrypt_secret

    assert decrypt_secret(GOOGLE_TOKEN_DATA) == GOOGLE_TOKEN_DATA_KLARTEXT
    assert decrypt_secret(GOOGLE_CLIENT_SECRET) == GOOGLE_CLIENT_SECRET_KLARTEXT


def test_mailpasswort_aus_46_0_7_bleibt_lesbar(alter_schluessel):
    from diakronos_app.smtp_einstellungen import entschluessle, verschluessle

    assert entschluessle(SMTP_PASSWORT) == SMTP_PASSWORT_KLARTEXT
    # Gegenrichtung: neu Verschluesseltes ist mit demselben Modul wieder lesbar
    # und traegt weiter dasselbe Praefix wie die Altwerte.
    neu = verschluessle(SMTP_PASSWORT_KLARTEXT)
    assert neu.startswith("fernet:v1:")
    assert entschluessle(neu) == SMTP_PASSWORT_KLARTEXT


def test_google_gegenrichtung_und_kontexte_getrennt(alter_schluessel):
    """Neu Verschluesseltes ist lesbar; SMTP- und Google-Kontext bleiben getrennt."""
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.google_secrets import decrypt_secret, encrypt_secret

    assert decrypt_secret(encrypt_secret(GOOGLE_CLIENT_SECRET_KLARTEXT)) == \
        GOOGLE_CLIENT_SECRET_KLARTEXT
    # Ein SMTP-Geheimtext im Google-Kontext ist wertlos (getrennte Ableitung).
    with pytest.raises(ValidationError):
        decrypt_secret(SMTP_PASSWORT)
